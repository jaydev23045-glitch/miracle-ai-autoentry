import os
import shutil
import re
import time
import datetime
import tempfile
import zipfile
import subprocess
import difflib
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from pydantic import BaseModel

from core.config import (
    get_client_lock,
    SystemSettings,
    load_settings,
    save_settings_to_file,
    clean_api_key,
    get_company_name,
    discover_clients,
    validate_vouchers_pre_push,
    resolve_year_folder_for_date,
    resolve_year_folder_for_date_fast
)
from dbf_handler import MiracleDBFHandler
from ai_memory import AIMemoryVault
from gemini_service import GeminiService
from core.tax_compliance import allocate_landed_costs, calculate_section_194q_tds, classify_gstr2b_match

router = APIRouter()

def get_handler() -> MiracleDBFHandler:
    """
    FastAPI dependency: returns a MiracleDBFHandler for the currently active client.
    Raises HTTP 404 if the client folder does not exist.
    """
    settings = load_settings()
    client_id = settings.get("active_client_id", "")
    if not client_id:
        raise HTTPException(status_code=400, detail="No active client selected.")
    client_path = os.path.join(settings.get("miracle_base_path", ""), client_id)
    if not os.path.exists(client_path):
        raise HTTPException(status_code=404, detail=f"Client folder not found at {client_path}")
    return MiracleDBFHandler(client_path)

# Ledger cache with TTL: {client_id: (timestamp, ledgers_list)}
_LEDGER_CACHE: dict = {}
_LEDGER_CACHE_TTL_SECONDS = 60  # Refresh ledger list every 60 seconds

def clean_gemini_error(e: Exception) -> str:
    error_msg = str(e)
    if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
        return "Gemini API Quota Exceeded (429 Resource Exhausted). If you are using the Free Tier key, Google limits it to 20 requests per day. Please check your Gemini API billing details or wait for the quota to reset."
    return error_msg

def copy_file_lock_resilient(src: str, dst: str) -> bool:
    """
    Copies a file from src to dst resiliently, bypassing system/advisory locks if possible.
    Supports macOS, Linux, and Windows.
    """
    import shutil
    import subprocess
    import os
    
    try:
        shutil.copy2(src, dst)
        return True
    except Exception as e:
        print(f"shutil.copy2 failed for {src}: {e}. Trying OS shell copy fallbacks...")
        
    if os.name == 'nt':
        try:
            res = subprocess.run(f'copy /Y "{src}" "{dst}"', shell=True, capture_output=True, text=True)
            if res.returncode == 0:
                return True
        except Exception as win_err:
            print(f"Windows shell copy failed: {win_err}")
    else:
        try:
            res = subprocess.run(["cp", src, dst], capture_output=True)
            if res.returncode == 0:
                return True
        except Exception as unix_err:
            print(f"Unix shell cp failed: {unix_err}")
            
    return False

def zip_dir_resilient(src_dir: str, zip_path: str, base_dir_name: str, active_year_folder: str = ""):
    """
    Creates a ZIP archive resiliently by handling locked files and retrying reads.
    Places all files inside a top-level parent folder matching base_dir_name.
    """
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(base_dir_name + "/", "")
        
        for root, dirs, files in os.walk(src_dir):
            if root == src_dir:
                if active_year_folder:
                    dirs[:] = [d for d in dirs if d.upper() == active_year_folder.upper()]
                else:
                    dirs[:] = [d for d in dirs if d.upper() not in ["BACKUPS", "TEMP", "GSTR2B"]]
            else:
                dirs[:] = [d for d in dirs if d.upper() not in ["BACKUPS", "TEMP", "GSTR2B"]]

            for d in dirs:
                abs_dir = os.path.join(root, d)
                rel_dir = os.path.relpath(abs_dir, src_dir)
                arc_dir = os.path.join(base_dir_name, rel_dir) + "/"
                zf.writestr(arc_dir, "")

            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, src_dir)
                arcname = os.path.join(base_dir_name, rel_path)
                
                success = False
                for attempt in range(5):
                    try:
                        with open(abs_path, 'rb') as f:
                            data = f.read()
                        zf.writestr(arcname, data)
                        success = True
                        break
                    except (IOError, OSError) as e:
                        print(f"⚠️ Warning: File locked on attempt {attempt+1}: {abs_path}. Error: {e}")
                        time.sleep(0.2)
                        
                if not success:
                    temp_copy = os.path.join(tempfile.gettempdir(), f"lock_bypass_{time.time_ns()}")
                    if copy_file_lock_resilient(abs_path, temp_copy):
                        try:
                            with open(temp_copy, 'rb') as f:
                                data = f.read()
                            zf.writestr(arcname, data)
                            success = True
                            print(f"✅ Successfully bypassed file lock for {file} using copy-bypass.")
                        except Exception as read_err:
                            print(f"❌ Failed to read copy-bypass file for {file}: {read_err}")
                        finally:
                            if os.path.exists(temp_copy):
                                try: os.remove(temp_copy)
                                except: pass
                            
                if not success:
                    critical_dbfs = {
                        "RKACCT40.DBF", "RKACCT41.DBF", "RKACCT01.DBF", "RKACCT02.DBF", 
                        "RKACCT52.DBF", "RKACCM01.DBF", "RKACCM02.DBF", "CMPM01.DBF"
                    }
                    file_upper = file.upper()
                    if file_upper in critical_dbfs:
                        raise Exception(f"Backup failed: Critical database file is locked and unreadable: {file}")
                    else:
                        print(f"⚠️ Skipping unreadable non-critical file: {file}")

def backup_full_client_folder(client_id: str, base_path: str, custom_backup_path: str = "", active_year_folder: str = "") -> str:
    """
    Creates a full ZIP backup of the client folder.
    """
    if not client_id or not base_path:
        raise Exception("Client ID or base path is missing.")

    client_path = os.path.join(base_path, client_id)
    if not os.path.exists(client_path):
        raise Exception(f"Client folder not found at {client_path}")

    if custom_backup_path and custom_backup_path.strip():
        backups_dir = custom_backup_path.strip()
    else:
        backups_dir = os.path.join(base_path, client_id, "BACKUPS")
        
    os.makedirs(backups_dir, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"BACKUP_{client_id}_{timestamp}"
    backup_zip_path = os.path.join(backups_dir, backup_filename)
    archive_path = backup_zip_path + ".zip"

    print(f"[backup] Creating full client backup for {client_id} from {client_path} to {backups_dir}...")
    zip_dir_resilient(client_path, archive_path, client_id, active_year_folder)
    
    if not os.path.exists(archive_path) or os.path.getsize(archive_path) == 0:
        raise Exception(f"Backup failed: Output ZIP file is missing or empty at {archive_path}")
        
    try:
        with zipfile.ZipFile(archive_path, 'r') as z:
            corrupted = z.testzip()
            if corrupted is not None:
                raise Exception(f"Corrupted file detected inside backup archive: {corrupted}")
                
            namelist = [name.upper() for name in z.namelist()]
            dbf_files = [f for f in namelist if f.endswith(".DBF")]
            if not dbf_files:
                raise Exception("Backup validation failed: No .DBF files were archived in the ZIP!")
                
    except Exception as zip_err:
        if os.path.exists(archive_path):
            try: os.remove(archive_path)
            except: pass
        raise Exception(f"Backup validation failed: {zip_err}")
        
    print(f"✅ [backup] Full client backup verified & created successfully at: {archive_path} ({os.path.getsize(archive_path)} bytes)")
    return archive_path

def self_heal_sales_purchase_data(extracted_data: dict, module: str, client_memory: dict = None, company_state_code: str = "") -> dict:
    if not isinstance(extracted_data, dict):
        return extracted_data
        
    rows = extracted_data.get("extracted_data", [])
    if not isinstance(rows, list) or not rows:
        return extracted_data

    client_memory = client_memory or {}
    existing_ledgers = client_memory.get("existing_ledgers", [])
    
    if module in ["Sales", "Purchases"]:
        # Auto-sequence bill numbers if missing/blank
        for idx, r in enumerate(rows, start=1):
            b_no = str(r.get("bill_no") or r.get("invoice_no") or r.get("billNo") or "").strip()
            if not b_no or b_no.lower() in ["none", "nan", "null", "undefined"]:
                seq_bill = str(idx)
                r["bill_no"] = seq_bill
                r["billNo"] = seq_bill

    if module in ["Sales", "Purchases"] and len(rows) > 1:
        series_list = []
        for r in rows:
            b_no = str(r.get("bill_no", "")).strip()
            m = re.match(r'^([A-Za-z0-9\-_]{2,8}[\/\-])', b_no)
            if m:
                series_list.append(m.group(1))

        if series_list:
            from collections import Counter
            counts = Counter(series_list)
            most_common_series, freq = counts.most_common(1)[0]
            if freq / len(rows) >= 0.5:
                for r in rows:
                    b_no = str(r.get("bill_no", "")).strip()
                    if b_no and not b_no.startswith(most_common_series) and b_no != "None" and b_no != "nan":
                        healed_bill = most_common_series + b_no
                        r["bill_no"] = healed_bill
                        flags = r.get("flags", [])
                        if not isinstance(flags, list): flags = []
                        if "Auto-Healed Prefix" not in flags:
                            flags.append("Auto-Healed Prefix")
                        r["flags"] = flags
                        print(f"✨ Self-Healing: Auto-prefixed bill_no '{b_no}' -> '{healed_bill}'")

    # Pre-compute ledger lookup structures ONCE before the row loop (BN-8 optimization)
    upper_to_original = {}
    ledger_an_list = []
    if existing_ledgers:
        for leg in existing_ledgers:
            l_str = ""
            if isinstance(leg, dict) and leg.get("name"):
                l_str = str(leg["name"]).strip()
            elif isinstance(leg, str) and leg.strip():
                l_str = leg.strip()
            if l_str:
                u_str = l_str.upper()
                if u_str not in upper_to_original:
                    upper_to_original[u_str] = l_str
                    an_clean = re.sub(r'[^A-Z0-9]', '', u_str)
                    if an_clean:
                        ledger_an_list.append((an_clean, l_str))

    ledger_upper_list = list(upper_to_original.keys())

    for row in rows:
        flags = row.get("flags", [])
        if not isinstance(flags, list):
            flags = []

        def safe_float(val, default=0.0):
            if val is None: return default
            try:
                s = str(val).replace("₹", "").replace(",", "").strip()
                return float(s) if s else default
            except:
                return default

        taxable = safe_float(row.get("taxable_amount") or row.get("taxable"))
        cgst = safe_float(row.get("cgst"))
        sgst = safe_float(row.get("sgst"))
        igst = safe_float(row.get("igst"))
        gst_total = safe_float(row.get("gst"))
        
        if gst_total == 0 and (cgst > 0 or sgst > 0 or igst > 0):
            gst_total = cgst + sgst + igst
            row["gst"] = gst_total
            
        discount = safe_float(row.get("discount"))
        freight = safe_float(row.get("freight"))
        tcs = safe_float(row.get("tcs"))
        tds = safe_float(row.get("tds"))
        total = safe_float(row.get("total"))

        # Compute and normalize effective GST Rate (%)
        if taxable > 0 and gst_total > 0:
            raw_pct = (gst_total / taxable) * 100.0
            slabs = [0.0, 0.25, 1.5, 3.0, 5.0, 12.0, 18.0, 28.0]
            closest_slab = min(slabs, key=lambda x: abs(x - raw_pct))
            row["gst_pct"] = closest_slab
        elif "gst_pct" not in row or row["gst_pct"] is None:
            row["gst_pct"] = 0.0

        # Determine whether 'taxable' is Net Taxable (already minus discount) or Gross Taxable
        exp_total_net = round(taxable + gst_total + freight + tcs - tds, 2)
        exp_total_gross = round(taxable - discount + gst_total + freight + tcs - tds, 2)

        if total > 0:
            diff_net = abs(exp_total_net - total)
            diff_gross = abs(exp_total_gross - total)

            if diff_net <= 2.00:
                expected_total = exp_total_net
            elif diff_gross <= 2.00:
                expected_total = exp_total_gross
            else:
                expected_total = exp_total_net if (diff_net < diff_gross) else exp_total_gross
        else:
            expected_total = exp_total_net if discount == 0 else exp_total_gross

        if total == 0 and taxable > 0:
            row["total"] = expected_total
            if "Auto-Healed Total" not in flags:
                flags.append("Auto-Healed Total")
            print(f"✨ Self-Healing: Calculated missing total = {expected_total}")
        elif taxable == 0 and total > 0 and gst_total == 0:
            row["taxable"] = total
            row["taxable_amount"] = total
            if "Auto-Healed Taxable" not in flags:
                flags.append("Auto-Healed Taxable")
            print(f"✨ Self-Healing: Set missing taxable = {total}")
        elif total > 0 and taxable > 0:
            diff = abs(expected_total - total)
            if 0.001 < diff <= 2.00:
                row["total"] = expected_total
                if "Auto-Healed Rounding" not in flags:
                    flags.append("Auto-Healed Rounding")
                print(f"✨ Self-Healing: Reconciled ₹{diff:.2f} rounding difference. Adjusted total to {expected_total}")
            elif diff > 2.00:
                if "Math Mismatch" not in flags:
                    flags.append("Math Mismatch")
                row["confidence_score"] = min(row.get("confidence_score", 95), 75)

        # Auto-detect state code and classify CGST+SGST vs IGST
        party_gstin = str(row.get("party_gstin") or row.get("gstin") or "").strip()
        party_state = party_gstin[:2] if len(party_gstin) >= 2 and party_gstin[:2].isdigit() else ""
        c_state = company_state_code or "24"
        
        if party_state and gst_total > 0:
            if party_state == c_state:
                if cgst == 0 or sgst == 0:
                    split_tax = round(gst_total / 2.0, 2)
                    row["cgst"] = split_tax
                    row["sgst"] = split_tax
                    row["igst"] = 0.0
                    if "Auto-Healed Tax Split (Intra-State)" not in flags:
                        flags.append("Auto-Healed Tax Split (Intra-State)")
                    print(f"✨ Self-Healing: Auto-split GST ({gst_total}) to CGST ({row['cgst']}) & SGST ({row['sgst']}) for state {party_state}")
            else:
                if (cgst > 0 or sgst > 0) or (igst == 0 and gst_total > 0):
                    row["igst"] = gst_total
                    row["cgst"] = 0.0
                    row["sgst"] = 0.0
                    if "Auto-Healed Tax Split (Inter-State)" not in flags:
                        flags.append("Auto-Healed Tax Split (Inter-State)")
                    print(f"✨ Self-Healing: Auto-mapped GST ({gst_total}) to IGST for inter-state {party_state} vs {c_state}")

        items = row.get("items", [])
        if isinstance(items, list) and items:
            for item in items:
                if isinstance(item, dict):
                    raw_qty = item.get("qty") if item.get("qty") is not None else item.get("quantity")
                    i_qty = safe_float(raw_qty, default=1.0)
                    if i_qty <= 0:
                        i_qty = 1.0
                    item["qty"] = i_qty
                    item["quantity"] = i_qty
                    
                    i_rate = safe_float(item.get("rate"))
                    i_amt = safe_float(item.get("amount"))
                    
                    if i_rate <= 0 and i_amt > 0 and i_qty > 0:
                        item["rate"] = round(i_amt / i_qty, 2)
                    elif i_amt <= 0 and i_rate > 0 and i_qty > 0:
                        item["amount"] = round(i_qty * i_rate, 2)

            # Apply Landed Cost Allocation if freight/handling charges exist
            if module == "Purchases" and freight > 0:
                row["items"] = allocate_landed_costs(items, freight_charges=freight)

        p_name = str(row.get("party_name") or row.get("party") or "").strip()
        if p_name and upper_to_original:
            p_upper = p_name.upper()
            p_first_token = p_upper.split()[0] if p_upper.split() else ""
            
            if p_upper in upper_to_original:
                matched_official = upper_to_original[p_upper]
                row["party_name"] = matched_official
                row["party"] = matched_official
            else:
                matched_official = None
                
                # 1. Space & Punctuation Insensitive Match (e.g. "S S R Footcare" -> "SSRFOOTCARE" -> matches "SSR Footcare")
                p_an = re.sub(r'[^A-Z0-9]', '', p_upper)
                if p_an:
                    for l_an, orig_name in ledger_an_list:
                        if l_an == p_an:
                            matched_official = orig_name
                            print(f"✨ Self-Healing: Space/Punctuation-insensitive matched party '{p_name}' -> '{orig_name}'")
                            break

                # 2. Prefix Match
                if not matched_official:
                    for u_name, orig_name in upper_to_original.items():
                        if (len(p_upper) >= 6 and u_name.startswith(p_upper)) or (len(u_name) >= 6 and p_upper.startswith(u_name)):
                            matched_official = orig_name
                            break
                        
                # 3. Fuzzy match
                if not matched_official:
                    matches = difflib.get_close_matches(p_upper, ledger_upper_list, n=1, cutoff=0.88)
                    if matches:
                        candidate = upper_to_original.get(matches[0])
                        if candidate:
                            cand_first_token = matches[0].split()[0] if matches[0].split() else ""
                            if p_first_token and cand_first_token:
                                first_token_match = difflib.SequenceMatcher(None, p_first_token, cand_first_token).ratio()
                                if first_token_match >= 0.80:
                                    matched_official = candidate
                                else:
                                    print(f"⚠️ Rejecting fuzzy match '{p_name}' -> '{candidate}' (First names '{p_first_token}' vs '{cand_first_token}' do not match)")
                            else:
                                matched_official = candidate

                if matched_official:
                    row["party_name"] = matched_official
                    row["party"] = matched_official
                    if "Auto-Healed Party Name" not in flags:
                        flags.append("Auto-Healed Party Name")
                    print(f"✨ Self-Healing: Fuzzy matched party '{p_name}' -> '{matched_official}'")

        row["flags"] = flags

    return extracted_data

def normalize_confidence_and_flags(extracted_data: dict, module: str, client_memory: dict = None, company_state_code: str = "", year_bounds: dict = None) -> dict:
    if not isinstance(extracted_data, dict):
        return extracted_data
    
    if module in ["Sales", "Purchases"]:
        extracted_data = self_heal_sales_purchase_data(extracted_data, module, client_memory=client_memory, company_state_code=company_state_code)
    
    rows = extracted_data.get("extracted_data", [])
    if not isinstance(rows, list):
        return extracted_data
        
    for row in rows:
        c_val = row.get("confidence_score")
        if c_val is None:
            c_score = 95
        else:
            try:
                c_score = int(float(str(c_val).replace("%", "").strip()))
            except:
                c_score = 95
        row["confidence_score"] = max(0, min(100, c_score))
        
        flags_val = row.get("flags")
        if not isinstance(flags_val, list):
            flags_val = []
        row["flags"] = [str(f).strip() for f in flags_val if f]
        
        if module in ["Bank Statements", "Cash Entries"]:
            m_ledger = str(row.get("mapped_ledger", "")).strip().upper()
            if m_ledger == "SUSPENSE ACCOUNT" or not m_ledger:
                if "Suspense Mapping" not in row["flags"]:
                    row["flags"].append("Suspense Mapping")
                row["confidence_score"] = min(row["confidence_score"], 75)
                
        if module in ["Sales", "Purchases"]:
            gstin = str(row.get("party_gstin", "")).strip()
            if not gstin:
                if "Missing GSTIN" not in row["flags"]:
                    row["flags"].append("Missing GSTIN")
                row["confidence_score"] = min(row["confidence_score"], 90)
            elif len(gstin) != 15:
                if "Invalid GSTIN" not in row["flags"]:
                    row["flags"].append("Invalid GSTIN")
                row["confidence_score"] = min(row["confidence_score"], 80)
                
            dt = str(row.get("date", "")).strip()
            if not dt or dt == "None" or dt == "nan":
                if "Missing Date" not in row["flags"]:
                    row["flags"].append("Missing Date")
                row["confidence_score"] = min(row["confidence_score"], 75)
            else:
                if len(dt) == 10 and dt.count("-") == 2:
                    try:
                        c_id = client_memory.get("client_id", "") if isinstance(client_memory, dict) else ""
                        c_path = os.path.join(settings.get("miracle_base_path", ""), c_id) if c_id else ""
                        if year_bounds is not None:
                            res = resolve_year_folder_for_date_fast(year_bounds, dt, c_path)
                        else:
                            res = resolve_year_folder_for_date(c_path, dt)
                        fy_start = res.get("fy_start")
                        fy_end = res.get("fy_end")
                        res_folder = res.get("resolved_folder")
                        if fy_start and fy_end and not (fy_start <= dt <= fy_end):
                            flag_msg = f"Date Outside FY ({res_folder})"
                            if flag_msg not in row["flags"]:
                                row["flags"].append(flag_msg)
                            row["confidence_score"] = min(row["confidence_score"], 85)
                    except Exception:
                        pass
                
            bill = str(row.get("bill_no", "")).strip()
            if not bill or bill == "None" or bill == "nan":
                if "Missing Invoice No" not in row["flags"]:
                    row["flags"].append("Missing Invoice No")
                row["confidence_score"] = min(row["confidence_score"], 80)
                
    return extracted_data

@router.get("/api/ledgers")
def get_ledgers(year: Optional[str] = None, handler: MiracleDBFHandler = Depends(get_handler)):
    """Reads all accounting ledgers from the active Miracle DBF."""
    try:
        ledgers = handler.read_ledgers_all_years(active_year_folder=year)
        y = year if year else handler.get_latest_year_folder()
        return {"status": "success", "year": y, "count": len(ledgers), "data": ledgers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/groups")
def get_account_groups(year: Optional[str] = None, handler: MiracleDBFHandler = Depends(get_handler)):
    """Reads all account groups from RKACCM11.DBF for the active Miracle client."""
    try:
        groups = handler.read_account_groups(year_folder=year)
        y = year if year else handler.get_latest_year_folder()
        return {"status": "success", "year": y, "count": len(groups), "data": groups}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/create-ledger")
def api_create_ledger(payload: dict):
    """Creates a new Miracle ledger in RKACCM01.DBF with user-selected group and updates AI Memory."""
    settings = load_settings()
    client_id = settings.get("active_client_id", "")
    if not client_id:
        raise HTTPException(status_code=400, detail="No active client selected.")

    client_path = os.path.join(settings["miracle_base_path"], client_id)
    if not os.path.exists(client_path):
        raise HTTPException(status_code=404, detail=f"Client folder not found at {client_path}")

    name = payload.get("name", "").strip()
    print_name = payload.get("print_name", "").strip() or name
    group_code = payload.get("group_code", "").strip()
    gstin = payload.get("gstin", "").strip()
    pan_number = payload.get("pan_number", "").strip()
    state_code = payload.get("state_code", "").strip()
    city = payload.get("city", "").strip()
    module_type = payload.get("module_type", "").strip() or "Bank Statements"
    year = payload.get("year", "")
    save_memory = payload.get("save_memory", True)

    if not name:
        raise HTTPException(status_code=400, detail="Ledger name is required.")

    try:
        handler = MiracleDBFHandler(client_path)
        ledger_code = handler.create_party_ledger(
            name=name,
            module=module_type,
            gstin=gstin,
            city=city,
            year_folder=year,
            explicit_group_code=group_code
        )

        # Update AI Memory Vault if requested
        if save_memory:
            from ai_memory import AIMemoryVault
            vault = AIMemoryVault()
            narration_key = payload.get("narration_key", "").strip()
            key_to_clean = narration_key if narration_key else name
            clean_key = AIMemoryVault.clean_mapping_key(key_to_clean) or AIMemoryVault.clean_mapping_key(name)
            if clean_key:
                mem_data = vault.load_memory(client_id)
                if "expense_mappings" not in mem_data:
                    mem_data["expense_mappings"] = {}
                mem_data["expense_mappings"][clean_key] = name
                vault.save_memory(client_id, mem_data)

        return {
            "status": "success",
            "ledger_code": ledger_code,
            "ledger_name": name,
            "group_code": group_code
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/update-ledger")
def api_update_ledger(payload: dict):
    """Updates an existing Miracle ledger in RKACCM01.DBF and syncs AI Memory Vault."""
    settings = load_settings()
    client_id = settings.get("active_client_id", "")
    if not client_id:
        raise HTTPException(status_code=400, detail="No active client selected.")

    client_path = os.path.join(settings["miracle_base_path"], client_id)
    if not os.path.exists(client_path):
        raise HTTPException(status_code=404, detail=f"Client folder not found at {client_path}")

    old_name = payload.get("old_name", "").strip()
    new_name = payload.get("new_name", "").strip()
    print_name = payload.get("print_name", "").strip() or new_name
    group_code = payload.get("group_code", "").strip()
    gstin = payload.get("gstin", "").strip()
    city = payload.get("city", "").strip()
    sync_dbf = payload.get("sync_dbf", True)
    save_memory = payload.get("save_memory", True)
    year = payload.get("year", "")

    if not old_name or not new_name:
        raise HTTPException(status_code=400, detail="Both old_name and new_name are required.")

    try:
        updated_code = ""
        if sync_dbf:
            handler = MiracleDBFHandler(client_path)
            updated_code = handler.update_party_ledger(
                old_name=old_name,
                new_name=new_name,
                print_name=print_name,
                group_code=group_code,
                gstin=gstin,
                city=city,
                year_folder=year
            )
            if updated_code:
                try:
                    handler._sync_party_to_other_years(new_name, updated_code, year)
                except Exception as sync_err:
                    print(f"⚠️ Warning: Cross-year sync during ledger update failed: {sync_err}")

        if save_memory:
            from ai_memory import AIMemoryVault
            vault = AIMemoryVault()
            clean_old = AIMemoryVault.clean_mapping_key(old_name)
            clean_new = new_name.strip()
            if clean_old:
                mem_data = vault.load_memory(client_id)
                if "expense_mappings" not in mem_data:
                    mem_data["expense_mappings"] = {}
                mem_data["expense_mappings"][clean_old] = clean_new
                vault.save_memory(client_id, mem_data)

        return {
            "status": "success",
            "ledger_code": updated_code,
            "old_name": old_name,
            "new_name": new_name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/debtor-balances")
def get_debtor_balances(year: Optional[str] = None, handler: MiracleDBFHandler = Depends(get_handler)):
    """Reads all Sundry Debtors and calculates their current outstanding balance."""
    try:
        balances = handler.get_debtor_balances(year_folder=year)
        y = year if year else handler.get_latest_year_folder()
        return {"status": "success", "year": y, "count": len(balances), "data": balances}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/refresh-ledgers")
def refresh_ledgers(year: Optional[str] = None, handler: MiracleDBFHandler = Depends(get_handler)):
    """Forces re-reading of Miracle DBF files and returns fresh ledgers."""
    try:
        ledgers = handler.read_ledgers(year_folder=year)
        y = year if year else handler.get_latest_year_folder()
        return {"status": "success", "year": y, "count": len(ledgers), "data": ledgers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/products")
def get_products(year: Optional[str] = None, handler: MiracleDBFHandler = Depends(get_handler)):
    """Reads all products from active Miracle DBFs across all financial years."""
    try:
        products = handler.read_products_all_years()
        y = year if year else handler.get_latest_year_folder()
        return {"status": "success", "year": y, "count": len(products), "data": products}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/refresh-products")
def refresh_products(year: Optional[str] = None, handler: MiracleDBFHandler = Depends(get_handler)):
    """Forces re-reading of Miracle DBF files across all years and returns fresh products."""
    try:
        products = handler.read_products_all_years()
        y = year if year else handler.get_latest_year_folder()
        return {"status": "success", "year": y, "count": len(products), "data": products}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/vouchers")
def get_vouchers(limit: int = 50, year: Optional[str] = None, handler: MiracleDBFHandler = Depends(get_handler)):
    """Fetch sample vouchers directly from the active Miracle DBF for preview."""
    try:
        records = handler.read_vouchers(limit=limit, year_folder=year)
        return {"count": len(records), "data": records}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/extraction-status")
@router.post("/api/extraction-status")
def get_extraction_status_endpoint():
    status_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "extraction_status.json")
    if os.path.exists(status_path):
        try:
            with open(status_path, "r") as f:
                data = json.load(f)
                return data
        except Exception:
            pass
    return {"filename": "", "part": 0, "total": 0, "progress_pct": 0, "percentage": 0, "message": "Idle"}

@router.post("/api/upload")
async def upload_document(module: str = Form(...), instruction: str = Form(""), pdf_password: str = Form(""), file: UploadFile = File(...)):
    """Endpoint for uploading Excels, PDFs, or Images and extracting data using Gemini."""
    settings = load_settings()
    api_key = settings.get("gemini_api_key", "")
    client_id = settings.get("active_client_id", "")
    
    safe_filename = os.path.basename(file.filename)
    temp_file_path = f"temp_{safe_filename}"
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        vault = AIMemoryVault(vault_path=settings.get("memory_path", "../AI_Memory_Vault"))
        client_memory = vault.load_memory(client_id)
        client_memory["client_id"] = client_id
        client_memory["_client_id"] = client_id  # Passed to gemini_service for catalog lookup
        
        gemini = GeminiService(
            api_key=api_key, 
            model_name=settings.get("gemini_model", "gemini-3.1-flash-lite"),
            is_paid_api_key=settings.get("is_paid_api_key", False)
        )
        
        handler = None
        try:
            client_path = os.path.join(settings["miracle_base_path"], client_id)
            handler = MiracleDBFHandler(client_path)
            now = time.time()
            cached = _LEDGER_CACHE.get(client_id)
            if cached and (now - cached[0]) < _LEDGER_CACHE_TTL_SECONDS:
                print(f"⚡ [Ledger Cache HIT] Using cached ledgers for '{client_id}' ({len(cached[1])} ledgers)")
                client_memory["existing_ledgers"] = cached[1]
            else:
                ledgers = handler.read_ledgers()
                ledger_names = [led['name'] for led in ledgers if led.get('name')]
                client_memory["existing_ledgers"] = ledger_names
                _LEDGER_CACHE[client_id] = (now, ledger_names)
                print(f"💾 [Ledger Cache STORE] Cached {len(ledger_names)} ledgers for '{client_id}'")
        except Exception as dbf_err:
            print(f"Warning: Could not read ledgers for Gemini context: {dbf_err}")
            client_memory["existing_ledgers"] = []

            
        if module == "Cash Entries" and temp_file_path.lower().endswith(('.xls', '.xlsx')):
            try:
                import pandas as pd
                xl = pd.ExcelFile(temp_file_path)
                
                for sheet in xl.sheet_names:
                    df = pd.read_excel(temp_file_path, sheet_name=sheet)
                    cols = [str(c).strip().upper() for c in df.columns]
                    
                    if any('AMOUNT' in c for c in cols) and any('DEBTOR' in c for c in cols):
                        print(f"Direct parsing detected for sheet {sheet}")
                        
                        amt_col = next((c for c in df.columns if 'AMOUNT' in str(c).upper()), None)
                        debtor_col = next((c for c in df.columns if 'DEBTOR' in str(c).upper()), None)
                        
                        if amt_col and debtor_col:
                            last_dates = handler.get_all_last_transaction_dates()
                            
                            year_folder_name = handler.get_latest_year_folder() or "YR26"
                            try:
                                year_num = int(year_folder_name[-2:])
                                fallback_date = f"20{year_num}-03-31"
                            except:
                                fallback_date = "2026-03-31"
                                
                            extracted = []
                            
                            for idx, row in df.iterrows():
                                amt = row[amt_col]
                                debtor_name = str(row[debtor_col]).strip()
                                
                                if pd.isna(amt) or debtor_name == 'nan' or not debtor_name:
                                    continue
                                    
                                try:
                                    amt = float(amt)
                                    if amt <= 0: continue
                                except:
                                    continue
                                    
                                matched_code = ""
                                matched_name = debtor_name
                                for led in ledgers:
                                    if led['name'].strip().upper() == debtor_name.upper() or led['print_name'].strip().upper() == debtor_name.upper():
                                        matched_code = led['code']
                                        matched_name = led['name']
                                        break
                                        
                                last_dt = last_dates.get(matched_code)
                                
                                final_date = fallback_date
                                if last_dt:
                                    try:
                                        fy_start = f"20{year_num - 1}-04-01"
                                        if last_dt >= fy_start:
                                            final_date = last_dt
                                    except: pass
                                
                                extracted.append({
                                    "date": final_date,
                                    "narration": "Cash Received",
                                    "mapped_ledger": matched_name,
                                    "transaction_type": "Receipt",
                                    "amount": amt,
                                    "reference_no": "",
                                    "confidence_score": 100,
                                    "flags": []
                                })
                                
                            if extracted:
                                try:
                                    os.remove(temp_file_path)
                                except: pass
                                
                                excel_res = {
                                    "status": "success",
                                    "bank_name": "Cash Account",
                                    "extracted_data": extracted
                                }
                                excel_res = gemini.apply_product_mappings(excel_res, client_memory, module, instruction)
                                excel_res = normalize_confidence_and_flags(excel_res, module)
                                return {
                                    "status": "success", 
                                    "data": excel_res
                                }
            except Exception as direct_err:
                print(f"Direct parsing failed, falling back to Gemini: {direct_err}")

        upload_year_bounds = {}
        try:
            upload_year_bounds = handler.get_all_year_folder_bounds()
        except Exception:
            pass

        if module in ["Sales", "Purchases"] and temp_file_path.lower().endswith(('.xls', '.xlsx')):
            try:
                print(f"{module} Excel detected! Bypassing Gemini LLM and using deterministic pandas parser for 100% math accuracy...")
                company_state = handler.get_company_state_code()
                print(f"Detected company state code: {company_state}")
                from core.excel_parser import parse_excel_to_json as _excel_parser
                direct_result = _excel_parser(temp_file_path, company_state_code=company_state, instruction=instruction)
                if direct_result.get("status") == "success":
                    print("Applying AI Brain product mappings & formatting post-processor...")
                    direct_result = gemini.apply_product_mappings(direct_result, client_memory, module, instruction)
                    direct_result = gemini.apply_ai_formatting(direct_result, client_memory, module)
                    direct_result = normalize_confidence_and_flags(direct_result, module, client_memory=client_memory, company_state_code=company_state, year_bounds=upload_year_bounds)
                    try:
                        os.remove(temp_file_path)
                    except: pass
                    det_yr = None
                    rows = direct_result.get("extracted_data", []) if isinstance(direct_result, dict) else []
                    if rows:
                        from datetime import datetime
                        year_counts = {}
                        for r in rows:
                            date_str = r.get("date", "")
                            if date_str:
                                try:
                                    res = resolve_year_folder_for_date_fast(upload_year_bounds, str(date_str), client_path)
                                    yr_f = res.get("resolved_folder")
                                    if yr_f:
                                        year_counts[yr_f] = year_counts.get(yr_f, 0) + 1
                                except Exception:
                                    pass
                        if year_counts:
                            det_yr = max(year_counts, key=year_counts.get)
                            
                    return {
                        "status": "success",
                        "data": direct_result,
                        "detected_client": None,
                        "detected_year": det_yr
                    }
            except Exception as e:
                print(f"{module} direct parsing failed, falling back to Gemini: {e}")
                
        extracted_data = gemini.extract_invoice_data(temp_file_path, client_memory, module, instruction, pdf_password=pdf_password)
        comp_state = ""
        try:
            comp_state = handler.get_company_state_code()
        except: pass
        if extracted_data.get("status") == "success":
            extracted_data = gemini.apply_product_mappings(extracted_data, client_memory, module, instruction)
        extracted_data = normalize_confidence_and_flags(extracted_data, module, client_memory=client_memory, company_state_code=comp_state, year_bounds=upload_year_bounds)
        
        detected_client = None
        doc_owner = extracted_data.get("document_owner", "").strip() if isinstance(extracted_data, dict) else ""
        if doc_owner:
            import difflib
            clients = discover_clients(settings["miracle_base_path"])
            client_names = [c["name"] for c in clients]
            matches = difflib.get_close_matches(doc_owner.upper(), [name.upper() for name in client_names], n=1, cutoff=0.70)
            if matches:
                matched_name_upper = matches[0]
                for c in clients:
                    if c["name"].upper() == matched_name_upper:
                        detected_client = c["id"]
                        break
        
        detected_year = None
        rows = extracted_data.get("extracted_data", []) if isinstance(extracted_data, dict) else []
        if rows:
            target_client_id = detected_client or client_id
            target_client_path = os.path.join(settings["miracle_base_path"], target_client_id) if target_client_id else client_path
            target_year_bounds = upload_year_bounds
            if target_client_path != client_path:
                try:
                    target_handler = MiracleDBFHandler(target_client_path)
                    target_year_bounds = target_handler.get_all_year_folder_bounds()
                except Exception:
                    pass
            year_counts = {}
            for r in rows:
                date_str = r.get("date", "")
                if date_str:
                    try:
                        res = resolve_year_folder_for_date_fast(target_year_bounds, str(date_str), target_client_path)
                        yr_f = res.get("resolved_folder")
                        if yr_f:
                            year_counts[yr_f] = year_counts.get(yr_f, 0) + 1
                    except Exception:
                        pass
            if year_counts:
                detected_year = max(year_counts, key=year_counts.get)
        
        return {
            "status": "success", 
            "data": extracted_data,
            "detected_client": detected_client,
            "detected_year": detected_year
        }
    except Exception as e:
        print(f"Error extracting data: {e}")
        err_str = str(e)
        if "PDF_PASSWORD_REQUIRED" in err_str:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=400,
                content={
                    "detail": "PDF_PASSWORD_REQUIRED",
                    "requires_password": True,
                    "message": "This PDF is password protected. Please enter the password to process.",
                    "filename": safe_filename
                }
            )
        elif "PDF_PASSWORD_INCORRECT" in err_str:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=400,
                content={
                    "detail": "PDF_PASSWORD_INCORRECT",
                    "requires_password": True,
                    "message": "Incorrect password provided for this PDF file. Please try again.",
                    "filename": safe_filename
                }
            )
        error_detail = clean_gemini_error(e)
        status_code = 429 if "RESOURCE_EXHAUSTED" in err_str or "429" in err_str else 500
        raise HTTPException(status_code=status_code, detail=error_detail)
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

class FindMatchingBillPayload(BaseModel):
    party_name: str
    amount: float

@router.post("/api/find_matching_bill")
def find_matching_bill(payload: FindMatchingBillPayload):
    settings = load_settings()
    client_id = settings.get("active_client_id", "")
    client_path = os.path.join(settings["miracle_base_path"], client_id)
    
    if not os.path.exists(client_path):
        return {"matched": False, "bill_no": ""}
        
    try:
        handler = MiracleDBFHandler(client_path)
        bill_no = handler.find_matching_bill(payload.party_name, payload.amount)
        if bill_no:
            return {"matched": True, "bill_no": bill_no}
        return {"matched": False, "bill_no": ""}
    except Exception as e:
        print(f"Error in find_matching_bill endpoint: {e}")
        return {"matched": False, "bill_no": ""}

class SaveProductMappingsPayload(BaseModel):
    gst_rules: Dict[str, str]
    keyword_rules: Dict[str, str]
    instructions: str = ""

class TeachProductMappingPayload(BaseModel):
    extracted_name: str
    mapped_product: str

@router.get("/api/product_mappings")
def get_product_mappings_endpoint():
    settings = load_settings()
    client_id = settings.get("active_client_id", "")
    try:
        vault = AIMemoryVault(vault_path=settings.get("memory_path", "../AI_Memory_Vault"))
        return vault.get_product_mappings(client_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/save_product_mappings")
def save_product_mappings_endpoint(payload: SaveProductMappingsPayload):
    settings = load_settings()
    client_id = settings.get("active_client_id", "")
    try:
        vault = AIMemoryVault(vault_path=settings.get("memory_path", "../AI_Memory_Vault"))
        mappings = {
            "gst_rules": payload.gst_rules,
            "keyword_rules": payload.keyword_rules,
            "instructions": payload.instructions
        }
        vault.save_product_mappings(client_id, mappings)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/teach_product_mapping")
def teach_product_mapping_endpoint(payload: TeachProductMappingPayload):
    settings = load_settings()
    client_id = settings.get("active_client_id", "")
    try:
        vault = AIMemoryVault(vault_path=settings.get("memory_path", "../AI_Memory_Vault"))
        vault.add_product_keyword_rule(client_id, payload.extracted_name, payload.mapped_product)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/auto_discover")
def auto_discover_prefixes_endpoint(handler: MiracleDBFHandler = Depends(get_handler)):
    settings = load_settings()
    client_id = settings.get("active_client_id", "")
    try:
        discovered = handler.auto_discover_prefixes(force_separate=True)
        vault = AIMemoryVault(vault_path=settings.get("memory_path", "../AI_Memory_Vault"))
        vault.set_company_settings(client_id, discovered)
        return {"status": "success", "discovered": discovered}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class PrefixOverridePayload(BaseModel):
    sales_prefix: str = "SS,SS"
    purchase_prefix: str = "PP,PP"

@router.post("/api/set-prefix")
def set_prefix_override_endpoint(payload: PrefixOverridePayload):
    settings = load_settings()
    client_id = settings.get("active_client_id", "")
    
    override = {
        "sales_prefix": payload.sales_prefix.strip(),
        "purchase_prefix": payload.purchase_prefix.strip()
    }
    
    vault = AIMemoryVault(vault_path=settings.get("memory_path", "../AI_Memory_Vault"))
    vault.set_company_settings(client_id, override)
    return {"status": "success", "client_id": client_id, "prefix": override}

class PushPayload(BaseModel):
    module: str
    vouchers: List[Dict[str, Any]]
    format_override: Optional[str] = None
    target_bank_name: Optional[str] = None
    target_cash_code: Optional[str] = None
    year_folder: Optional[str] = None
    backup_path: Optional[str] = ""

@router.post("/api/push")
def push_vouchers_endpoint(payload: PushPayload):
    settings = load_settings()
    client_id = settings.get("active_client_id", "")
    with get_client_lock(client_id):
        client_path = os.path.join(settings["miracle_base_path"], client_id)
        
        if not os.path.exists(client_path):
            raise HTTPException(status_code=404, detail=f"Client folder not found at {client_path}")

        active_year = payload.year_folder.strip() if payload.year_folder else ""
        if not active_year:
            active_year = settings.get("active_year_folder", "")

        try:
            handler = MiracleDBFHandler(client_path)
            year_bounds = handler.get_all_year_folder_bounds()
            val_ledgers = handler.read_ledgers(year_folder=active_year)
            validation_errors = validate_vouchers_pre_push(
                module=payload.module,
                vouchers=payload.vouchers,
                client_path=client_path,
                year_folder=active_year,
                ledgers=val_ledgers,
                pre_computed_bounds=year_bounds
            )
            if validation_errors:
                err_msg = "Pre-push Validation Failures:\n" + "\n".join(validation_errors)
                print(f"❌ {err_msg}")
                raise HTTPException(status_code=400, detail=err_msg)
        except HTTPException:
            raise
        except Exception as val_err:
            print(f"⚠️ Validation error (skipped): {val_err}")
            
        configured_backup_path = (payload.backup_path or "").strip()
        if not configured_backup_path or configured_backup_path.upper() == "SKIP":
            print("[backup] Skip backup requested or backup path is empty — skipping database backup.")
        else:
            active_year = payload.year_folder.strip() if payload.year_folder else ""
            if not active_year:
                active_year = settings.get("active_year_folder", "")
                
            try:
                backup_full_client_folder(client_id, settings["miracle_base_path"], configured_backup_path, active_year_folder=active_year)
            except Exception as backup_err:
                print(f"❌ Backup failed, push aborted: {backup_err}")
                raise HTTPException(status_code=500, detail=f"Failed to create database backup: {backup_err}. Push aborted for safety.")

        try:
            vault = AIMemoryVault(vault_path=settings.get("memory_path", "../AI_Memory_Vault"))
            comp_settings = vault.get_company_settings(client_id)
            
            if "sales_prefix" not in comp_settings or "purchase_prefix" not in comp_settings:
                discovered = handler.auto_discover_prefixes(force_separate=True)
                vault.set_company_settings(client_id, discovered)
                comp_settings.update(discovered)
                
            if "sales_bill_format" not in comp_settings or "purchase_bill_format" not in comp_settings:
                bill_formats = handler.detect_bill_formats()
                vault.set_company_settings(client_id, bill_formats)
                comp_settings.update(bill_formats)
                
            sales_pref = comp_settings.get("sales_prefix", "SS,SS")
            purch_pref = comp_settings.get("purchase_prefix", "PP,PP")
            
            sales_setup_id = comp_settings.get(
                "sales_setup_id",
                settings.get("sales_setup_id", 5)
            )
            purchase_setup_id = comp_settings.get(
                "purchase_setup_id",
                settings.get("purchase_setup_id", 6)
            )
            try:
                sales_setup_id = int(sales_setup_id)
            except:
                sales_setup_id = 5
            try:
                purchase_setup_id = int(purchase_setup_id)
            except:
                purchase_setup_id = 6

            def _looks_like_purchase_prefix(pref: str) -> bool:
                parts = [p.strip().upper() for p in pref.split(',')]
                return any(p[:2] in ['PP', 'PB', 'PU', 'PI', 'PO', 'PA'] for p in parts if len(p) >= 2)

            def _looks_like_sales_prefix(pref: str) -> bool:
                parts = [p.strip().upper() for p in pref.split(',')]
                return any(p[:2] in ['SS', 'SL', 'SR', 'SA', 'SB', 'SC', 'SD'] for p in parts if len(p) >= 2)

            if payload.module == 'Sales':
                if _looks_like_purchase_prefix(sales_pref) and not _looks_like_sales_prefix(sales_pref):
                    discovered = handler.auto_discover_prefixes(force_separate=True)
                    corrected_sales = discovered.get("sales_prefix", "SS,SS")
                    if _looks_like_purchase_prefix(corrected_sales) and not _looks_like_sales_prefix(corrected_sales):
                        corrected_sales = "SS,SS"
                    sales_pref = corrected_sales
                    vault.set_company_settings(client_id, {"sales_prefix": sales_pref})
            elif payload.module == 'Purchases':
                if _looks_like_sales_prefix(purch_pref) and not _looks_like_purchase_prefix(purch_pref):
                    discovered = handler.auto_discover_prefixes(force_separate=True)
                    corrected_purch = discovered.get("purchase_prefix", "PP,PP")
                    if _looks_like_sales_prefix(corrected_purch) and not _looks_like_purchase_prefix(corrected_purch):
                        corrected_purch = "PP,PP"
                    purch_pref = corrected_purch
                    vault.set_company_settings(client_id, {"purchase_prefix": purch_pref})

            bill_fmt = comp_settings.get("sales_bill_format", "") if payload.module == 'Sales' else comp_settings.get("purchase_bill_format", "")
            raw_last_no = comp_settings.get("sales_last_bill_number", 0) if payload.module == 'Sales' else comp_settings.get("purchase_last_bill_number", 0)
            try:
                last_bill_num = int(raw_last_no)
            except (ValueError, TypeError):
                last_bill_num = 0

            # Always sort vouchers in forward chronological order (oldest first) before inserting into Miracle DBF files
            from datetime import datetime as _p_dt
            def parse_v_date(v):
                d_str = str(v.get("date", "")).strip()
                for _f in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y"):
                    try:
                        return _p_dt.strptime(d_str[:10], _f)
                    except ValueError:
                        pass
                return _p_dt.min

            # Multi-Year Voucher Partitioning
            vouchers_by_year = {}
            for v in payload.vouchers:
                v_date = v.get("date") or v.get("Date") or ""
                res = resolve_year_folder_for_date_fast(year_bounds, str(v_date), client_path)
                target_yr = res.get("resolved_folder") or active_year
                if target_yr not in vouchers_by_year:
                    vouchers_by_year[target_yr] = []
                vouchers_by_year[target_yr].append(v)

            total_count = 0
            combined_audit = {"injected": 0, "duplicates": 0, "missing_parties": 0, "anomalies": 0, "duplicate_details": []}
            year_counts = {}

            for yr_folder, yr_vouchers in vouchers_by_year.items():
                yr_vouchers.sort(key=parse_v_date)
                print(f"📦 [Multi-Year Push] Injecting {len(yr_vouchers)} voucher(s) into Financial Year folder '{yr_folder}'...")

                count = handler.inject_vouchers(
                    module=payload.module, 
                    vouchers=yr_vouchers,
                    year_folder=yr_folder,
                    sales_prefix=sales_pref,
                    purchase_prefix=purch_pref,
                    sales_setup_id=sales_setup_id,
                    purchase_setup_id=purchase_setup_id,
                    sales_series=comp_settings.get("sales_series", settings.get("sales_series", "")),
                    bill_format_pattern=bill_fmt,
                    last_bill_number=last_bill_num,
                    format_override=payload.format_override,
                    bank_name=payload.target_bank_name,
                    target_cash_code=payload.target_cash_code
                )
                
                total_count += count
                year_counts[yr_folder] = count
                
                # Aggregate audit report
                if hasattr(handler, 'audit_report') and isinstance(handler.audit_report, dict):
                    ar = handler.audit_report
                    combined_audit["injected"] += ar.get("injected", 0)
                    combined_audit["duplicates"] += ar.get("duplicates", 0)
                    combined_audit["missing_parties"] += ar.get("missing_parties", 0)
                    combined_audit["anomalies"] += ar.get("anomalies", 0)
                    if "duplicate_details" in ar and isinstance(ar["duplicate_details"], list):
                        combined_audit["duplicate_details"].extend(ar["duplicate_details"])
                        
                try:
                    handler.heal_blank_hsn_records(yr_folder)
                except Exception as heal_err:
                    print(f"⚠️ Warning: Post-push self-healing failed for {yr_folder}: {heal_err}")
                
                try:
                    handler.ensure_cdx_flags_active(yr_folder)
                except Exception as cdx_err:
                    print(f"⚠️ Warning: Post-push CDX flag auto-heal failed for {yr_folder}: {cdx_err}")

            if hasattr(handler, 'latest_injected_bill_number'):
                if payload.module == 'Sales':
                    vault.set_company_settings(client_id, {"sales_last_bill_number": handler.latest_injected_bill_number})
                elif payload.module == 'Purchases':
                    vault.set_company_settings(client_id, {"purchase_last_bill_number": handler.latest_injected_bill_number})
                    
            if payload.module == 'Bank Statements':
                _batch_mappings = {}
                for v in payload.vouchers:
                    nar = (v.get('narration') or '').strip().upper()
                    ldgr = (v.get('party_name') or '').strip()
                    if nar and ldgr and ldgr.upper() not in ('SUSPENSE ACCOUNT', 'SUSPENSE A/C', 'UPI DEBTORS', 'UPI CREDITORS'):
                        _batch_mappings[nar] = ldgr
                if _batch_mappings:
                    vault.batch_add_expense_mappings(client_id, _batch_mappings)

            # Auto-learn product catalog from Sales/Purchases push
            if payload.module in ('Sales', 'Purchases'):
                try:
                    vault.learn_from_pushed_vouchers(client_id, payload.vouchers, payload.module)
                except Exception as learn_err:
                    print(f"⚠️ [Auto-Learn] Non-critical: {learn_err}")
                    
            primary_year = max(year_counts, key=year_counts.get) if year_counts else active_year
            
            # Save updated active_year_folder if changed
            if primary_year and primary_year != settings.get("active_year_folder"):
                settings["active_year_folder"] = primary_year
                save_settings_to_file(settings)

            year_breakdown_str = ", ".join([f"{c} in {y}" for y, c in year_counts.items()])
            return {
                "status": "success", 
                "count": total_count,
                "primary_year": primary_year,
                "year_counts": year_counts,
                "audit_report": combined_audit, 
                "message": f"Successfully injected {total_count} vouchers into Miracle ({year_breakdown_str})."
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/opening-balances/extract")
async def extract_opening_balances_endpoint(file: UploadFile = File(...)):
    try:
        temp_dir = "temp_uploads"
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.join(temp_dir, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        settings = load_settings()
        gemini = GeminiService(
            api_key=settings.get("gemini_api_key", ""),
            is_paid_api_key=settings.get("is_paid_api_key", False)
        )
        
        client_id = settings.get("active_client_id", "")
        base_path = settings.get("miracle_base_path", "")
        client_path = os.path.join(base_path, client_id)
        handler = MiracleDBFHandler(client_path)
        year_folder = handler.get_latest_year_folder()
        ledgers = handler.read_ledgers(year_folder) if year_folder else []
        ledger_names = [led['name'] for led in ledgers]
        
        result = gemini.extract_opening_balances(file_path, ledger_names)
        
        if "extracted_data" in result:
            for item in result["extracted_data"]:
                item["matched_code"] = ""
                name_upper = item.get("ledger_name", "").strip().upper()
                for led in ledgers:
                    if led['name'].strip().upper() == name_upper or led['print_name'].strip().upper() == name_upper:
                        item["matched_code"] = led['code']
                        item["ledger_name"] = led['name']
                        break
        
        try:
            os.remove(file_path)
        except:
            pass

        return result
    except Exception as e:
        print(f"Error in extract_opening_balances: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class OpeningBalancePushPayload(BaseModel):
    entries: List[dict]
    backup_path: Optional[str] = ""

@router.post("/api/opening-balances/push")
def push_opening_balances_endpoint(payload: OpeningBalancePushPayload):
    settings = load_settings()
    client_id = settings.get("active_client_id", "")
    with get_client_lock(client_id):
        try:
            base_path = settings.get("miracle_base_path", "")
            active_year = settings.get("active_year_folder", "")
            
            configured_backup_path = (payload.backup_path or "").strip()
            if not configured_backup_path or configured_backup_path.upper() == "SKIP":
                print("[backup] Skip backup requested or backup path is empty — skipping database backup.")
            else:
                try:
                    backup_full_client_folder(client_id, base_path, configured_backup_path, active_year_folder=active_year)
                except Exception as backup_err:
                    print(f"❌ Backup failed, opening balance push aborted: {backup_err}")
                    raise HTTPException(status_code=500, detail=f"Failed to create database backup: {backup_err}. Push aborted for safety.")

            client_path = os.path.join(base_path, client_id)
            handler = MiracleDBFHandler(client_path)
            
            final_entries = []
            for row in payload.entries:
                name = row.get("ledger_name", "").strip()
                l_code = row.get("matched_code", "").strip()
                if not l_code:
                    hint = row.get("group_hint", "Suspense")
                    print(f"Auto-creating ledger '{name}' for opening balance based on hint '{hint}'")
                    mod_hint = 'Sales' if 'debtor' in hint.lower() or 'asset' in hint.lower() or 'cash' in hint.lower() or 'bank' in hint.lower() else 'Purchases'
                    l_code = handler.create_party_ledger(
                        name=name,
                        module=mod_hint
                    )
                    
                if l_code:
                    final_entries.append({
                        'ledger_code': l_code,
                        'balance': row.get('balance', 0.0),
                        'dr_cr': row.get('dr_cr', 'D')
                    })
            
            result = handler.inject_opening_balances(final_entries)
            return result
            
        except Exception as e:
            print(f"Error in push_opening_balances: {e}")
            raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/repair-bank-flags")
@router.post("/api/repair-bank-flags")
def repair_bank_flags_endpoint(year: Optional[str] = None, handler: MiracleDBFHandler = Depends(get_handler)):
    try:
        result = handler.repair_bank_entry_flags(year_folder=year or None)
        total_repaired = result.get("repaired_headers", 0) + result.get("repaired_lines", 0)
        return {
            "status": "success",
            "message": f"Repaired {total_repaired} entries (Headers: {result.get('repaired_headers', 0)}, Lines: {result.get('repaired_lines', 0)}) across {len(result['folders'])} year folder(s).",
            "repaired": total_repaired,
            "repaired_headers": result.get("repaired_headers", 0),
            "repaired_lines": result.get("repaired_lines", 0),
            "skipped": result.get("skipped", 0),
            "folders": result.get("folders", []),
            "errors": result.get("errors", [])
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in repair_bank_flags: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/repair-purchase-flags")
@router.post("/api/repair-purchase-flags")
def repair_purchase_flags_endpoint(year: Optional[str] = None, handler: MiracleDBFHandler = Depends(get_handler)):
    try:
        result = handler.repair_purchase_voucher_flags(year_folder=year or None)
        total_repaired = result.get("repaired_headers", 0)
        return {
            "status": "success",
            "message": f"Repaired {total_repaired} Purchase voucher headers across {len(result['folders'])} year folder(s).",
            "repaired": total_repaired,
            "repaired_headers": total_repaired,
            "folders": result.get("folders", []),
            "errors": result.get("errors", [])
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in repair_purchase_flags: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/repair-cdx-flags")
@router.post("/api/repair-cdx-flags")
def repair_cdx_flags_endpoint(year: Optional[str] = None):
    settings = load_settings()
    client_id = settings.get("active_client_id", "")
    with get_client_lock(client_id):
        client_path = os.path.join(settings["miracle_base_path"], client_id)
        if not os.path.exists(client_path):
            raise HTTPException(status_code=404, detail=f"Client folder not found at {client_path}")

        try:
            handler = MiracleDBFHandler(client_path)
            target_yr = year.strip() if year else settings.get("active_year_folder", "")
            healed = handler.ensure_cdx_flags_active(target_yr)
            return {
                "status": "success",
                "message": f"Successfully activated CDX index flags on {healed} DBF table header(s).",
                "repaired_count": healed
            }
        except HTTPException:
            raise
        except Exception as e:
            print(f"Error in repair_cdx_flags: {e}")
            raise HTTPException(status_code=500, detail=str(e))

class ResolveSuspensePayload(BaseModel):
    vouchers: list
    year_folder: Optional[str] = ""

@router.post("/api/resolve-suspense")
def resolve_suspense_endpoint(payload: ResolveSuspensePayload):
    try:
        settings = load_settings()
        client_id = settings.get("active_client_id", "")
        base_path = settings.get("miracle_base_path", "")
        client_dir = os.path.join(base_path, client_id) if (base_path and client_id) else ""
        
        service = GeminiService()
        
        vault_path = settings.get("memory_path", "../AI_Memory_Vault")
        vault = AIMemoryVault(vault_path=vault_path)
        client_memory = vault.load_memory(client_id) if client_id else {}
        
        # Load active DBF ledgers if available
        if client_dir and os.path.exists(client_dir):
            try:
                from dbf_handler import MiracleDBFHandler
                handler = MiracleDBFHandler(client_dir)
                client_memory["existing_ledgers"] = handler.read_ledgers_all_years()
            except Exception as le:
                print(f"⚠️ Could not load DBF ledgers for suspense resolution: {le}")

        result_json = {"status": "success", "extracted_data": payload.vouchers}
        
        # Step 1: Rule-based & Narration Party Extraction pass
        step1_json = service.map_ledgers_for_statement(result_json, client_memory, module="Bank Statements")
        
        # Step 2: AI Intelligence Resolution pass for any remaining unmapped / generic rows
        updated_json = service.ai_assist_suspense_mappings(step1_json, client_memory, module="Bank Statements")
        
        return {
            "status": "success",
            "vouchers": updated_json.get("extracted_data", [])
        }
    except Exception as e:
        print(f"❌ Error resolving suspense entries: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/repair-narrations")
@router.post("/api/repair-narrations")
def repair_narrations(year_folder: str | None = None, handler: MiracleDBFHandler = Depends(get_handler)):
    try:
        settings = load_settings()
        target_yr = year_folder or settings.get("active_year_folder") or handler.get_latest_year_folder()
        res = handler.repair_all_voucher_narrations(target_yr)
        return res
    except Exception as e:
        print(f"❌ Error repairing voucher narrations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/train-memory")
def train_memory_from_history():
    """Scans all historical DBF folders for the active client and trains clean expense mappings into AI Memory Vault."""
    try:
        settings = load_settings()
        base_path = settings.get("miracle_base_path", "")
        active_client = settings.get("active_client_id", "CMP0021")
        client_dir = os.path.join(base_path, active_client)
        
        from ai_memory import AIMemoryVault
        vault = AIMemoryVault()
        trained_count = vault.train_from_history(active_client, client_dir)
        return {
            "status": "success",
            "message": f"Successfully trained AI Memory! Learned {trained_count} clean expense mappings across past database years.",
            "trained_count": trained_count
        }
    except Exception as e:
        print(f"❌ Error training memory from history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/memory-vault")
def get_memory_vault():
    """Returns the complete AI Memory Vault data (expense mappings, product catalog, supplier catalog) for active client."""
    try:
        settings = load_settings()
        active_client = settings.get("active_client_id", "CMP0021")
        from ai_memory import AIMemoryVault
        vault = AIMemoryVault()
        mem_data = vault.load_memory(active_client)
        return {
            "status": "success",
            "client_id": active_client,
            "memory": mem_data
        }
    except Exception as e:
        print(f"❌ Error fetching memory vault: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/memory-vault")
def save_memory_vault_entry(payload: dict):
    """Saves or updates a specific expense mapping or catalog entry in AI Memory Vault."""
    try:
        settings = load_settings()
        active_client = settings.get("active_client_id", "CMP0021")
        from ai_memory import AIMemoryVault
        vault = AIMemoryVault()
        
        category = payload.get("category", "expense_mapping")
        key = payload.get("key", "").strip()
        value = payload.get("value", "")
        
        if not key:
            raise HTTPException(status_code=400, detail="Key cannot be empty.")
            
        mem_data = vault.load_memory(active_client)
        
        if category == "expense_mapping":
            clean_k = vault.clean_mapping_key(key)
            clean_val = vault.clean_mapping_value(str(value))
            if not clean_k:
                clean_k = key.upper()
            if "expense_mappings" not in mem_data:
                mem_data["expense_mappings"] = {}
            mem_data["expense_mappings"][clean_k] = str(clean_val or value).strip()
            
        elif category == "product_catalog":
            if "product_catalog" not in mem_data:
                mem_data["product_catalog"] = {}
            k_low = key.lower()
            entry = mem_data["product_catalog"].get(k_low, {})
            entry["display_name"] = key
            if isinstance(value, dict):
                entry.update(value)
            mem_data["product_catalog"][k_low] = entry
            
        elif category == "supplier_catalog":
            if "supplier_catalog" not in mem_data:
                mem_data["supplier_catalog"] = {}
            k_low = key.lower()
            entry = mem_data["supplier_catalog"].get(k_low, {})
            entry["display_name"] = key
            if isinstance(value, dict):
                entry.update(value)
            mem_data["supplier_catalog"][k_low] = entry
            
        vault.save_memory(active_client, mem_data)
        return {"status": "success", "message": f"Saved '{key}' in AI Memory Vault."}
    except Exception as e:
        print(f"❌ Error saving memory vault entry: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/memory-vault/item")
def delete_memory_vault_entry(category: str, key: str):
    """Deletes a specific entry from AI Memory Vault."""
    try:
        settings = load_settings()
        active_client = settings.get("active_client_id", "CMP0021")
        from ai_memory import AIMemoryVault
        vault = AIMemoryVault()
        
        mem_data = vault.load_memory(active_client)
        deleted = False
        
        if category in ("expense_mapping", "expense_mappings"):
            deleted = vault.delete_expense_mapping(active_client, key)
        elif category == "product_catalog":
            cat = mem_data.get("product_catalog", {})
            target_k = next((k for k in cat if k == key or k.lower() == key.lower() or k.upper() == key.upper()), None)
            if target_k:
                del cat[target_k]
                mem_data["product_catalog"] = cat
                vault.save_memory(active_client, mem_data)
                deleted = True
        elif category == "supplier_catalog":
            cat = mem_data.get("supplier_catalog", {})
            target_k = next((k for k in cat if k == key or k.lower() == key.lower() or k.upper() == key.upper()), None)
            if target_k:
                del cat[target_k]
                mem_data["supplier_catalog"] = cat
                vault.save_memory(active_client, mem_data)
                deleted = True
                
        return {"status": "success", "deleted": deleted, "key": key}
    except Exception as e:
        print(f"❌ Error deleting memory vault item: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/generate-memory-rule")
def generate_memory_rule_from_prompt(payload: dict):
    """
    Takes natural language prompt, calls Gemini API to understand customer intent,
    generates structured rules with explanations & concrete examples, and saves to AI Memory Vault.
    """
    try:
        user_prompt = payload.get("prompt", "").strip()
        auto_save = payload.get("auto_save", True)
        if not user_prompt:
            raise HTTPException(status_code=400, detail="Prompt text cannot be empty.")
            
        settings = load_settings()
        active_client = payload.get("client_id") or settings.get("active_client_id", "CMP0021")
        base_path = settings.get("miracle_base_path", "")
        client_dir = os.path.join(base_path, active_client)
        
        # Load DBF ledgers if available for context
        handler = MiracleDBFHandler(client_dir)
        year_folder = settings.get("active_year_folder") or handler.get_latest_year_folder()
        ledgers = []
        if year_folder:
            try:
                ledgers = handler.read_ledgers(year_folder)
            except Exception:
                pass

        from ai_memory import AIMemoryVault
        vault = AIMemoryVault()
        client_memory = vault.load_memory(active_client)
        
        service = GeminiService()
        result = service.generate_memory_rules_from_prompt(user_prompt, client_memory=client_memory, existing_ledgers=ledgers)
        
        rules = result.get("rules", [])
        saved_count = 0
        
        if auto_save and rules:
            # Collect all expense_mapping rules first to batch into a single write
            expense_batch = {}
            for rule in rules:
                cat = rule.get("category", "expense_mapping")
                k = rule.get("key", "").strip()
                v = rule.get("value", "")
                if not k or not v:
                    continue
                    
                if cat == "expense_mapping":
                    expense_batch[k] = str(v)
                    saved_count += 1
                elif cat == "product_catalog":
                    vault.add_product_keyword_rule(active_client, k, str(v))
                    saved_count += 1
                elif cat == "supplier_catalog":
                    k_low = k.lower()
                    if "supplier_catalog" not in client_memory:
                        client_memory["supplier_catalog"] = {}
                    entry = client_memory["supplier_catalog"].get(k_low, {})
                    entry["display_name"] = k
                    if isinstance(v, str) and len(v) >= 10:
                        entry["gstin"] = v
                    client_memory["supplier_catalog"][k_low] = entry
                    vault.save_memory(active_client, client_memory)
                    saved_count += 1

            # Write all expense_mapping rules in a single disk operation
            if expense_batch:
                vault.batch_add_expense_mappings(active_client, expense_batch)
                    
        return {
            "status": "success",
            "summary": result.get("summary", f"Generated {len(rules)} rule(s)."),
            "rules": rules,
            "saved_count": saved_count,
            "message": f"Successfully generated {len(rules)} rule(s) and saved {saved_count} to AI Memory Vault!"
        }
    except Exception as e:
        print(f"❌ Error generating memory rule from prompt: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/simulate-memory-rule")
def simulate_memory_rule(payload: dict):
    """
    Tests a text string (narration or item name) against client AI Memory Vault rules
    and returns matching rule details, confidence, and target value.
    """
    try:
        test_text = payload.get("test_text", "").strip()
        if not test_text:
            return {"status": "error", "matched": False, "message": "Test text is empty."}
            
        settings = load_settings()
        active_client = payload.get("client_id") or settings.get("active_client_id", "CMP0021")
        
        from ai_memory import AIMemoryVault
        vault = AIMemoryVault()
        
        # Test Expense Mappings
        mapped_ledger, matched_key = vault.find_fuzzy_expense_mapping(active_client, test_text)
        if mapped_ledger:
            return {
                "status": "success",
                "matched": True,
                "category": "expense_mapping",
                "matched_key": matched_key,
                "matched_value": mapped_ledger,
                "confidence": 98 if matched_key.upper() in test_text.upper() else 88,
                "explanation": f"Matched expense mapping key '{matched_key}' -> maps to '{mapped_ledger}'"
            }
            
        # Test Product Catalog
        prod_cat = vault.get_product_catalog(active_client)
        test_low = test_text.lower()
        for pk, pentry in prod_cat.items():
            if pk in test_low or test_low in pk or pentry.get("display_name", "").lower() in test_low:
                return {
                    "status": "success",
                    "matched": True,
                    "category": "product_catalog",
                    "matched_key": pentry.get("display_name", pk),
                    "matched_value": f"HSN: {pentry.get('hsn', '-')} | GST: {pentry.get('gst_pct', '-')}%",
                    "confidence": 95,
                    "explanation": f"Matched product catalog entry '{pentry.get('display_name', pk)}'"
                }
                
        # Test Supplier Catalog
        sup_cat = vault.get_supplier_catalog(active_client)
        for sk, sentry in sup_cat.items():
            if sk in test_low or test_low in sk or sentry.get("display_name", "").lower() in test_low:
                return {
                    "status": "success",
                    "matched": True,
                    "category": "supplier_catalog",
                    "matched_key": sentry.get("display_name", sk),
                    "matched_value": f"GSTIN: {sentry.get('gstin', '-')}",
                    "confidence": 95,
                    "explanation": f"Matched supplier catalog entry '{sentry.get('display_name', sk)}'"
                }
                
        return {
            "status": "success",
            "matched": False,
            "message": "No matching Memory Vault rule found for this input text."
        }
    except Exception as e:
        print(f"❌ Error simulating memory rule: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/memory-vault/bulk-delete")
def bulk_delete_memory_vault_entries(payload: dict):
    """Deletes multiple items from AI Memory Vault in one call."""
    try:
        items = payload.get("items", [])
        if not items or not isinstance(items, list):
            raise HTTPException(status_code=400, detail="Items array is empty.")
            
        settings = load_settings()
        active_client = payload.get("client_id") or settings.get("active_client_id", "CMP0021")
        from ai_memory import AIMemoryVault
        vault = AIMemoryVault()
        
        mem_data = vault.load_memory(active_client)
        expense_mappings = mem_data.get("expense_mappings", {})
        product_catalog = mem_data.get("product_catalog", {})
        supplier_catalog = mem_data.get("supplier_catalog", {})
        deleted_count = 0
        
        for item in items:
            cat = item.get("category", "")
            key = item.get("key", "")
            if not cat or not key:
                continue
            if cat in ["expense_mapping", "expense_mappings"]:
                clean_k = vault.clean_mapping_key(key)
                if key in expense_mappings:
                    del expense_mappings[key]
                    deleted_count += 1
                elif clean_k in expense_mappings:
                    del expense_mappings[clean_k]
                    deleted_count += 1
                elif key.upper() in expense_mappings:
                    del expense_mappings[key.upper()]
                    deleted_count += 1
            elif cat == "product_catalog":
                target_k = next((k for k in product_catalog if k == key or k.lower() == key.lower() or k.upper() == key.upper()), None)
                if target_k:
                    del product_catalog[target_k]
                    deleted_count += 1
            elif cat == "supplier_catalog":
                target_k = next((k for k in supplier_catalog if k == key or k.lower() == key.lower() or k.upper() == key.upper()), None)
                if target_k:
                    del supplier_catalog[target_k]
                    deleted_count += 1
                    
        mem_data["expense_mappings"] = expense_mappings
        mem_data["product_catalog"] = product_catalog
        mem_data["supplier_catalog"] = supplier_catalog
        
        vault.save_memory(active_client, mem_data)
        return {"status": "success", "deleted_count": deleted_count, "message": f"Successfully deleted {deleted_count} memory rules."}
    except Exception as e:
        print(f"❌ Error bulk deleting memory vault entries: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/memory-vault/export")
def export_memory_vault():
    """Exports the client's AI Memory Vault JSON as a downloadable attachment."""
    try:
        settings = load_settings()
        active_client = settings.get("active_client_id", "CMP0021")
        from ai_memory import AIMemoryVault
        vault = AIMemoryVault()
        mem_data = vault.load_memory(active_client)
        
        from fastapi.responses import JSONResponse
        content = json.dumps(mem_data, indent=4, ensure_ascii=False)
        headers = {
            "Content-Disposition": f"attachment; filename=AI_Memory_Vault_{active_client}.json"
        }
        return JSONResponse(content=mem_data, headers=headers)
    except Exception as e:
        print(f"❌ Error exporting memory vault: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/memory-vault/import")
def import_memory_vault(payload: dict):
    """Imports and merges JSON rules into client AI Memory Vault."""
    try:
        rules = payload.get("memory")
        if not rules or not isinstance(rules, dict):
            rules = payload
            
        if isinstance(rules, dict) and not any(k in rules for k in ["expense_mappings", "product_catalog", "supplier_catalog", "specifications"]):
            rules = {"expense_mappings": rules}
            
        if not isinstance(rules, dict):
            raise HTTPException(status_code=400, detail="Invalid memory payload.")
            
        settings = load_settings()
        active_client = payload.get("client_id") or settings.get("active_client_id", "CMP0021")
        from ai_memory import AIMemoryVault
        vault = AIMemoryVault()
        
        existing = vault.load_memory(active_client)
        
        # Merge expense_mappings
        if "expense_mappings" in rules and isinstance(rules["expense_mappings"], dict):
            if "expense_mappings" not in existing: existing["expense_mappings"] = {}
            existing["expense_mappings"].update(rules["expense_mappings"])
            
        # Merge product_catalog
        if "product_catalog" in rules and isinstance(rules["product_catalog"], dict):
            if "product_catalog" not in existing: existing["product_catalog"] = {}
            existing["product_catalog"].update(rules["product_catalog"])
            
        # Merge supplier_catalog
        if "supplier_catalog" in rules and isinstance(rules["supplier_catalog"], dict):
            if "supplier_catalog" not in existing: existing["supplier_catalog"] = {}
            existing["supplier_catalog"].update(rules["supplier_catalog"])
            
        vault.save_memory(active_client, existing)
        return {"status": "success", "message": f"Successfully imported memory vault rules for client {active_client}."}
    except Exception as e:
        print(f"❌ Error importing memory vault: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/clean-memory-vault")
def clean_memory_vault():
    """Retroactively purges numeric/fragmented noise keys and synthesizes clean rules via Gemini AI for active client."""
    try:
        settings = load_settings()
        active_client = settings.get("active_client_id", "CMP0021")
        from ai_memory import AIMemoryVault
        vault = AIMemoryVault()
        
        # Step 1: Local deterministic clean & rebuild
        changed_count = vault.rebuild_memory_keys(active_client)
        
        # Step 2: Gemini AI synthesis & optimization
        mem_data = vault.load_memory(active_client)
        raw_expense_rules = mem_data.get("expense_mappings", {})
        
        if raw_expense_rules:
            from gemini_service import GeminiService
            gemini = GeminiService()
            if gemini.api_key:
                optimized_rules = gemini.optimize_and_synthesize_memory_rules(raw_expense_rules)
                if optimized_rules and isinstance(optimized_rules, dict):
                    mem_data["expense_mappings"] = optimized_rules
                    vault.save_memory(active_client, mem_data)
                    changed_count += max(0, len(raw_expense_rules) - len(optimized_rules))
                    
        return {
            "status": "success",
            "message": f"Successfully AI-optimized Memory Vault! Consolidated rules into {len(mem_data.get('expense_mappings', {}))} clean mappings.",
            "changed_count": changed_count
        }
    except Exception as e:
        print(f"❌ Error cleaning memory vault: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/memory-vault/import-excel")
async def import_excel_memory_rules(file: UploadFile = File(...)):
    """
    Accepts an uploaded Excel (.xlsx, .xls) or CSV file, passes its content to Gemini AI,
    understands all columns (narrations, ledgers, items, HSN, suppliers), and auto-maps rules into AI Memory Vault.
    """
    try:
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"memory_import_{file.filename}")
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        settings = load_settings()
        active_client = settings.get("active_client_id", "CMP0021")
        
        # Read existing Miracle ledgers for smart matching
        base_path = settings.get("miracle_base_path", "")
        client_dir = os.path.join(base_path, active_client)
        existing_ledgers = []
        try:
            from dbf_handler import MiracleDBFHandler
            handler = MiracleDBFHandler(client_dir)
            existing_ledgers = handler.get_ledgers()
        except Exception:
            pass

        from gemini_service import GeminiService
        gemini = GeminiService()
        extracted_rules = gemini.parse_excel_and_map_rules(temp_path, existing_ledgers)

        if os.path.exists(temp_path):
            os.remove(temp_path)

        from ai_memory import AIMemoryVault
        vault = AIMemoryVault()
        existing = vault.load_memory(active_client)

        exp_count = 0
        prod_count = 0
        supp_count = 0

        # Merge expense_mappings
        if "expense_mappings" in extracted_rules and isinstance(extracted_rules["expense_mappings"], dict):
            if "expense_mappings" not in existing: existing["expense_mappings"] = {}
            existing["expense_mappings"].update(extracted_rules["expense_mappings"])
            exp_count = len(extracted_rules["expense_mappings"])

        # Merge product_catalog
        if "product_catalog" in extracted_rules and isinstance(extracted_rules["product_catalog"], dict):
            if "product_catalog" not in existing: existing["product_catalog"] = {}
            existing["product_catalog"].update(extracted_rules["product_catalog"])
            prod_count = len(extracted_rules["product_catalog"])

        # Merge supplier_catalog
        if "supplier_catalog" in extracted_rules and isinstance(extracted_rules["supplier_catalog"], dict):
            if "supplier_catalog" not in existing: existing["supplier_catalog"] = {}
            existing["supplier_catalog"].update(extracted_rules["supplier_catalog"])
            supp_count = len(extracted_rules["supplier_catalog"])

        vault.save_memory(active_client, existing)
        total = exp_count + prod_count + supp_count

        return {
            "status": "success",
            "message": f"✨ Gemini AI auto-mapped {total} rules ({exp_count} expense mappings, {prod_count} products, {supp_count} suppliers) from Excel file!",
            "extracted": {
                "expense_count": exp_count,
                "product_count": prod_count,
                "supplier_count": supp_count
            }
        }
    except Exception as e:
        print(f"❌ Error importing Excel memory rules: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/memory-vault/export-excel")
def export_excel_memory_vault():
    """Exports client AI Memory Vault rules as a clean CSV/Excel file download."""
    try:
        settings = load_settings()
        active_client = settings.get("active_client_id", "CMP0021")
        from ai_memory import AIMemoryVault
        vault = AIMemoryVault()
        mem_data = vault.load_memory(active_client)

        csv_lines = ["--- EXPENSE MAPPINGS ---", "Memory Key / Search Pattern,Mapped Miracle Ledger,Source"]
        expense_mappings = mem_data.get("expense_mappings", {})
        for k, v in sorted(expense_mappings.items()):
            src = "AI Rule" if " " in k else "DBF Learned"
            csv_lines.append(f'"{k}","{v}","{src}"')

        csv_lines.append("")
        csv_lines.append("--- PRODUCT CATALOG ---")
        csv_lines.append("Item Name / Search Key,Display Name,HSN Code,GST %,UOM,Last Rate")
        prod_cat = mem_data.get("product_catalog", {})
        for k, v in sorted(prod_cat.items()):
            d_name = v.get("display_name", k)
            hsn = v.get("hsn", "")
            gst = v.get("gst_pct", "")
            uom = v.get("uom", "")
            rate = v.get("last_rate", "")
            csv_lines.append(f'"{k}","{d_name}","{hsn}","{gst}","{uom}","{rate}"')

        csv_lines.append("")
        csv_lines.append("--- SUPPLIER CATALOG ---")
        csv_lines.append("Supplier Name,GSTIN,City,Typical Items")
        supp_cat = mem_data.get("supplier_catalog", {})
        for k, v in sorted(supp_cat.items()):
            d_name = v.get("display_name", k)
            gstin = v.get("gstin", "")
            city = v.get("city", "")
            items = "; ".join(v.get("typical_items", []))
            csv_lines.append(f'"{d_name}","{gstin}","{city}","{items}"')

        content = "\n".join(csv_lines)
        from fastapi.responses import Response
        return Response(
            content=content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=AI_Memory_Vault_{active_client}.csv"}
        )
    except Exception as e:
        print(f"❌ Error exporting Excel memory vault: {e}")
        raise HTTPException(status_code=500, detail=str(e))



