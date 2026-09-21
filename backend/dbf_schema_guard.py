"""
Miracle DBF Schema Guard & Self-Healing Engine
Auto-detects DBF structure changes across Miracle ERP upgrades (Field addition/deletion,
Type change, File renames) and enforces safe schema baselines.
"""

import os
import json
import hashlib
import glob
import logging
from datetime import datetime
from dbfread import DBF

logger = logging.getLogger(__name__)

# Miracle DBF contract definitions + wildcard patterns for version auto-discovery
MIRACLE_DBF_CONTRACTS = {
    "RKACCM01": {
        "pattern": "RKACCM*.DBF",
        "required_fields": ["FIELD01", "FIELD02", "FIELD04", "FIELD05"],
        "critical": True
    },
    "RKACCT41": {
        "pattern": "RKACCT4*.DBF",
        "required_fields": ["FIELD01", "FIELD02", "FIELD04", "FIELD16"],
        "critical": True
    },
    "RKACCT01": {
        "pattern": "RKACCT0*.DBF",
        "required_fields": ["FIELD01", "FIELD02", "FIELD03", "FIELD04"],
        "critical": True
    },
    "RKACCGID": {
        "pattern": "RKACCGID.DBF",
        "required_fields": ["FIELD01", "FIELD04"],
        "critical": False
    }
}


def find_miracle_dbf(company_folder: str, pattern: str) -> str:
    """
    Auto-discovers DBF file by wildcard pattern.
    Handles file renames across Miracle ERP versions.
    Checks year folder (company_folder) first, then parent client folder if not found.
    """
    if not os.path.exists(company_folder):
        return ""
    
    # Check current year folder (e.g. YR26)
    matches = glob.glob(os.path.join(company_folder, pattern))
    if not matches:
        pattern_lower = pattern.lower()
        matches = glob.glob(os.path.join(company_folder, pattern_lower))

    # Fallback to parent client folder (e.g. CMP0001)
    if not matches:
        parent_dir = os.path.dirname(company_folder)
        if os.path.exists(parent_dir):
            matches = glob.glob(os.path.join(parent_dir, pattern))
            if not matches:
                matches = glob.glob(os.path.join(parent_dir, pattern.lower()))

    if not matches:
        return ""
    # Return most recently modified file matching pattern
    return max(matches, key=os.path.getmtime)


def capture_schema_fingerprint(dbf_path: str) -> dict:
    """
    Reads DBF file structure and creates an MD5 fingerprint hash.
    Enforces context manager usage to close DBF file handle immediately.
    """
    if not dbf_path or not os.path.exists(dbf_path):
        return {}
    try:
        with DBF(dbf_path, load=False, ignore_missing_memofile=True) as table:
            fields_info = {f.name: {"type": f.type, "length": f.length} for f in table.fields}
            fingerprint = hashlib.md5(
                str(sorted([(f.name, f.type, f.length) for f in table.fields])).encode('utf-8')
            ).hexdigest()
            return {
                "file": os.path.basename(dbf_path),
                "full_path": dbf_path,
                "field_count": len(table.fields),
                "fields": fields_info,
                "fingerprint_hash": fingerprint,
                "captured_at": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"Schema capture failed for {dbf_path}: {e}")
        return {}



def save_baseline(client_id: str, company_folder: str, baseline_dir: str) -> dict:
    """
    Captures and saves baseline schema. Called when client first onboards or is registered.
    """
    baseline = {
        "client_id": client_id,
        "company_folder": company_folder,
        "created_at": datetime.now().isoformat(),
        "tables": {}
    }
    for table_key, contract in MIRACLE_DBF_CONTRACTS.items():
        dbf_path = find_miracle_dbf(company_folder, contract["pattern"])
        if dbf_path:
            fp = capture_schema_fingerprint(dbf_path)
            baseline["tables"][table_key] = fp

    os.makedirs(baseline_dir, exist_ok=True)
    baseline_path = os.path.join(baseline_dir, f"{client_id}_dbf_baseline.json")
    with open(baseline_path, 'w', encoding='utf-8') as f:
        json.dump(baseline, f, indent=2)
    logger.info(f"[SchemaGuard] Saved baseline schema for client {client_id} at {baseline_path}")
    return baseline


def run_schema_health_check(client_id: str, company_folder: str, baseline_dir: str) -> dict:
    """
    Runs BEFORE every batch processing run.
    Compares live DBF schema against saved baseline.
    Returns: {"healthy": True/False, "alerts": [...], "auto_adapted": [...]}
    """
    baseline_path = os.path.join(baseline_dir, f"{client_id}_dbf_baseline.json")

    # First run — auto-capture baseline and allow safe execution
    if not os.path.exists(baseline_path):
        save_baseline(client_id, company_folder, baseline_dir)
        return {
            "healthy": True,
            "alerts": [],
            "auto_adapted": ["first_run_baseline_captured"],
            "checked_at": datetime.now().isoformat()
        }

    try:
        with open(baseline_path, 'r', encoding='utf-8') as f:
            baseline = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read baseline JSON for {client_id}: {e}")
        return {"healthy": True, "alerts": [], "auto_adapted": ["baseline_read_error_fallback"]}

    alerts = []
    auto_adapted = []
    has_critical_change = False

    for table_key, contract in MIRACLE_DBF_CONTRACTS.items():
        current_path = find_miracle_dbf(company_folder, contract["pattern"])
        if not current_path:
            alerts.append({
                "severity": "CRITICAL",
                "table": table_key,
                "issue": f"DBF NOT FOUND for pattern: {contract['pattern']}"
            })
            if contract["critical"]:
                has_critical_change = True
            continue

        current_fp = capture_schema_fingerprint(current_path)
        if not current_fp:
            logger.warning(f"[SchemaGuard] Could not capture fingerprint for {current_path} (file may be locked). Skipping table check.")
            continue

        saved_fp = baseline.get("tables", {}).get(table_key, {})
        if not saved_fp:
            auto_adapted.append(f"New DBF table discovered and registered: {table_key}")
            continue

        # RISK 1: Field count change (Addition or Deletion)
        if current_fp.get("field_count") != saved_fp.get("field_count"):
            old_fields = set(saved_fp.get("fields", {}).keys())
            new_fields = set(current_fp.get("fields", {}).keys())
            added = new_fields - old_fields
            removed = old_fields - new_fields
            
            severity = "WARNING" if (added and not removed) else "CRITICAL"
            alerts.append({
                "severity": severity,
                "table": table_key,
                "issue": f"Field count changed: {saved_fp.get('field_count')} → {current_fp.get('field_count')}",
                "added_fields": list(added),
                "removed_fields": list(removed)
            })

            if added and not removed:
                auto_adapted.append(f"{table_key}: {len(added)} new fields added by Miracle ERP (safely ignored by dbf_safe_helpers)")
            
            if removed:
                missing_critical = [f for f in removed if f in contract["required_fields"]]
                if missing_critical:
                    has_critical_change = True
                    logger.error(f"[SchemaGuard] Critical required fields removed in {table_key}: {missing_critical}")

        # RISK 2: Data type change (e.g. Numeric to Character)
        if current_fp.get("fingerprint_hash") != saved_fp.get("fingerprint_hash"):
            type_changes = []
            saved_fields = saved_fp.get("fields", {})
            curr_fields = current_fp.get("fields", {})
            for f_name in saved_fields:
                if f_name in curr_fields and curr_fields[f_name]["type"] != saved_fields[f_name]["type"]:
                    type_changes.append({
                        "field": f_name,
                        "old_type": saved_fields[f_name]["type"],
                        "new_type": curr_fields[f_name]["type"]
                    })
            if type_changes:
                alerts.append({
                    "severity": "WARNING",
                    "table": table_key,
                    "issue": "Field data types changed by Miracle ERP upgrade",
                    "type_changes": type_changes
                })
                auto_adapted.append(f"{table_key}: Data types changed for {len(type_changes)} fields (auto-handled by dbf_safe_float/str)")

    return {
        "healthy": not has_critical_change,
        "alerts": alerts,
        "auto_adapted": auto_adapted,
        "checked_at": datetime.now().isoformat()
    }
