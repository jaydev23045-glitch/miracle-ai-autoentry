"""
Miracle AI Auto-Entry — Local DBF Bridge Agent (MiracleBridge)
---------------------------------------------------------------
This lightweight agent runs silently on the client's local Windows PC (port 9123).
It connects local Visual FoxPro DBF tables (C:\\Miracle\\CMPxxxx\\YRxx) to the Render Cloud Web App.

Web App Cloud URL: https://miracle-ai-app.onrender.com
Local Agent URL: http://localhost:9123
"""

import sys
import os
import stat
import time
import datetime
import zipfile
import tempfile
import uvicorn
import threading
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

# ── 1. PYINSTALLER WINDOWED MODE STDOUT/STDERR NULL WRITER ─────────────────────
# In PyInstaller --windowed mode, sys.stdout/sys.stderr are None.
# Dummy stream writer prevents AttributeError: 'NoneType' object has no attribute 'isatty'
class NullWriter:
    def write(self, text):
        pass
    def flush(self):
        pass
    def isatty(self):
        return False

if sys.stdout is None:
    sys.stdout = NullWriter()
if sys.stderr is None:
    sys.stderr = NullWriter()
if sys.stdin is None:
    sys.stdin = NullWriter()

# Ensure PyInstaller bundle directory or script directory is on sys.path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
if getattr(sys, 'frozen', False):
    bundle_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    sys.path.insert(0, bundle_dir)

sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.abspath(os.path.join(BASE_DIR, "..", "backend")))

CLOUD_URL = os.environ.get("RENDER_CLOUD_URL", "https://miracle-ai-autoentry.onrender.com").rstrip("/")

def sanitize_surrogates(val: Any) -> Any:
    """Universally removes lone UTF-16/UTF-32 surrogate code points (U+D800 to U+DFFF)."""
    if isinstance(val, str):
        return "".join(c for c in val if not (0xD800 <= ord(c) <= 0xDFFF))
    elif isinstance(val, dict):
        return {sanitize_surrogates(k): sanitize_surrogates(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [sanitize_surrogates(item) for item in val]
    return val

# Imports from local self-contained modules
try:
    from core.config import get_client_lock
except Exception:
    try:
        from backend.core.config import get_client_lock
    except Exception:
        _locks = {}
        _locks_guard = threading.Lock()
        def get_client_lock(client_id: str):
            with _locks_guard:
                if client_id not in _locks:
                    _locks[client_id] = threading.Lock()
                return _locks[client_id]

try:
    from dbf_handler import MiracleDBFHandler
except Exception:
    try:
        from backend.dbf_handler import MiracleDBFHandler
    except Exception as err:
        print(f"⚠️ Warning: Failed to import MiracleDBFHandler: {err}")

# Standalone Resilient ZIP Backup Helper
def copy_file_lock_resilient(src_path: str, dst_path: str) -> bool:
    try:
        import shutil
        shutil.copy2(src_path, dst_path)
        return True
    except Exception:
        return False

def zip_dir_resilient(src_dir: str, zip_path: str, base_dir_name: str, active_year_folder: str = ""):
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
                    except (IOError, OSError):
                        time.sleep(0.2)
                        
                if not success:
                    temp_copy = os.path.join(tempfile.gettempdir(), f"lock_bypass_{time.time_ns()}")
                    if copy_file_lock_resilient(abs_path, temp_copy):
                        try:
                            with open(temp_copy, 'rb') as f:
                                data = f.read()
                            zf.writestr(arcname, data)
                            success = True
                        except Exception:
                            pass
                        finally:
                            if os.path.exists(temp_copy):
                                try: os.remove(temp_copy)
                                except: pass

def ensure_writable_recursive(target_path: str) -> None:
    """
    Recursively ensures that target_path and all nested files/directories have write permissions.
    Self-heals read-only folder attributes (common in Windows copies, NAS mounts, or zip extracts).
    """
    if not target_path or not isinstance(target_path, str):
        return

    curr = target_path
    parents_to_heal = []
    while curr and curr != os.path.dirname(curr):
        if os.path.exists(curr):
            parents_to_heal.append(curr)
        curr = os.path.dirname(curr)

    for p in reversed(parents_to_heal):
        try:
            st = os.stat(p)
            if os.path.isdir(p):
                os.chmod(p, st.st_mode | stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
            else:
                os.chmod(p, st.st_mode | stat.S_IRUSR | stat.S_IWUSR)
        except Exception:
            pass

    if not os.path.exists(target_path):
        return

    if os.path.isdir(target_path):
        for root, dirs, files in os.walk(target_path):
            for d in dirs:
                dp = os.path.join(root, d)
                try:
                    st = os.stat(dp)
                    os.chmod(dp, st.st_mode | stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
                except Exception:
                    pass
            for f in files:
                fp = os.path.join(root, f)
                try:
                    st = os.stat(fp)
                    os.chmod(fp, st.st_mode | stat.S_IRUSR | stat.S_IWUSR)
                except Exception:
                    pass

def backup_full_client_folder(client_id: str, base_path: str, custom_backup_path: str = "", active_year_folder: str = "") -> str:
    if not client_id or not base_path:
        raise Exception("Client ID or base path is missing.")

    client_path = os.path.join(base_path, client_id)
    if not os.path.exists(client_path):
        raise Exception(f"Client folder not found at {client_path}")

    # Self-heal permissions on client folder
    ensure_writable_recursive(client_path)

    if custom_backup_path and custom_backup_path.strip():
        backups_dir = custom_backup_path.strip()
    else:
        backups_dir = os.path.join(base_path, client_id, "BACKUPS")
        
    ensure_writable_recursive(backups_dir)
    try:
        os.makedirs(backups_dir, exist_ok=True)
    except PermissionError as pe:
        print(f"⚠️ Permission error creating backup directory {backups_dir}: {pe}. Self-healing permissions and retrying...")
        ensure_writable_recursive(client_path)
        ensure_writable_recursive(backups_dir)
        os.makedirs(backups_dir, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"BACKUP_{client_id}_{timestamp}"
    backup_zip_path = os.path.join(backups_dir, backup_filename)
    archive_path = backup_zip_path + ".zip"

    print(f"[backup] Creating full client backup for {client_id} from {client_path} to {backups_dir}...")
    zip_dir_resilient(client_path, archive_path, client_id, active_year_folder)
    
    if not os.path.exists(archive_path) or os.path.getsize(archive_path) == 0:
        raise Exception(f"Backup failed: Output ZIP file is missing or empty at {archive_path}")
        
    print(f"✅ [backup] Full client backup verified & created successfully at: {archive_path}")
    return archive_path


app = FastAPI(
    title="Miracle Local DBF Bridge Agent",
    description="Local Windows Agent for Miracle Accounting AI Auto-Entry",
    version="1.0.0"
)

# CORS & Private Network Access (PNA): Allow communication from Render Cloud Web URL & Localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows requests from Render Cloud URL & Localhost
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_pna_and_cors_headers(request, call_next):
    if request.method == "OPTIONS":
        from fastapi.responses import Response
        response = Response(status_code=204)
    else:
        response = await call_next(request)
    
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Private-Network"] = "true"
    return response

@app.options("/{full_path:path}")
async def options_preflight_handler(full_path: str):
    from fastapi.responses import Response
    res = Response(status_code=204)
    res.headers["Access-Control-Allow-Origin"] = "*"
    res.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
    res.headers["Access-Control-Allow-Headers"] = "*"
    res.headers["Access-Control-Allow-Private-Network"] = "true"
    return res

class InjectRequestPayload(BaseModel):
    miracle_base_path: str
    active_client_id: str
    active_year_folder: str
    module_type: str  # "bank", "sales", "purchase", "cash", "opening_balance"
    vouchers: List[Dict[str, Any]]
    sales_setup_id: Optional[int] = 5
    purchase_setup_id: Optional[int] = 6
    sales_prefix: Optional[str] = "SS,SS"
    purchase_prefix: Optional[str] = "PP,PP"
    target_bank_name: Optional[str] = "Bank Account"
    target_bank_code: Optional[str] = None
    target_cash_code: Optional[str] = "ACASHACT"
    backup_path: Optional[str] = ""

@app.get("/health")
@app.get("/status")
def health_check():
    """Health check endpoint to confirm bridge agent is running on client PC"""
    return {
        "status": "online",
        "agent_name": "MiracleBridge Agent",
        "version": "1.0.0",
        "port": 9123,
        "platform": sys.platform
    }

def scan_all_miracle_paths() -> List[Dict[str, Any]]:
    """Scans all local drives (C:, D:, E:, F:, G:) and candidate locations to discover valid Miracle directories."""
    discovered = []
    seen = set()

    # 1. Standard candidate folders
    standard_candidates = [
        "C:\\Miracle", "D:\\Miracle", "E:\\Miracle", "F:\\Miracle",
        "C:\\Miracle9070", "D:\\Miracle9070", "E:\\Miracle9070",
        "C:\\Miracle_Data", "D:\\Miracle_Data", "E:\\Miracle_Data"
    ]

    # Add project local fallback paths if present
    for p in [BASE_DIR, os.path.abspath(os.path.join(BASE_DIR, ".."))]:
        for sub in ["MIRRACLE FILE", "Miracle9070", "mnt_mirracle"]:
            fp = os.path.join(p, sub)
            if os.path.exists(fp):
                standard_candidates.append(fp)

    for cand in standard_candidates:
        norm = os.path.normpath(cand).upper()
        if os.path.exists(cand) and os.path.isdir(cand) and norm not in seen:
            seen.add(norm)
            try:
                cmps = [d for d in os.listdir(cand) if os.path.isdir(os.path.join(cand, d)) and d.upper().startswith("CMP")]
                if cmps:
                    discovered.append({
                        "path": cand,
                        "client_count": len(cmps),
                        "clients": cmps
                    })
            except Exception:
                pass

    # 2. Drive root & 1-level subfolder scan across all drives
    drives = [f"{d}:\\" for d in "CDEFG" if os.path.exists(f"{d}:\\")]
    for drive in drives:
        norm_d = os.path.normpath(drive).upper()
        if norm_d not in seen:
            try:
                cmps = [d for d in os.listdir(drive) if os.path.isdir(os.path.join(drive, d)) and d.upper().startswith("CMP")]
                if cmps:
                    seen.add(norm_d)
                    discovered.append({
                        "path": drive,
                        "client_count": len(cmps),
                        "clients": cmps
                    })
            except Exception:
                pass

        # Scan 1-level subdirectories on drive
        try:
            for sub in os.listdir(drive):
                sub_path = os.path.join(drive, sub)
                norm_sub = os.path.normpath(sub_path).upper()
                if os.path.isdir(sub_path) and norm_sub not in seen and not sub.startswith("$") and sub.lower() not in ["windows", "program files", "program files (x86)", "system volume information", "users", "appdata"]:
                    try:
                        cmps = [d for d in os.listdir(sub_path) if os.path.isdir(os.path.join(sub_path, d)) and d.upper().startswith("CMP")]
                        if cmps:
                            seen.add(norm_sub)
                            discovered.append({
                                "path": sub_path,
                                "client_count": len(cmps),
                                "clients": cmps
                            })
                    except Exception:
                        pass
        except Exception:
            pass

    return sorted(discovered, key=lambda x: x["client_count"], reverse=True)

def resolve_valid_base_path(base_path: str = "") -> str:
    """Intelligently resolves the actual Miracle folder on the local Windows PC"""
    if base_path and os.path.exists(base_path) and not ("/Users/" in base_path or "/home/" in base_path):
        # Check if base_path itself contains CMP folders
        try:
            if any(d.upper().startswith("CMP") for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))):
                return base_path
        except Exception:
            pass

    discovered = scan_all_miracle_paths()
    if discovered:
        return discovered[0]["path"]

    return base_path or "C:\\Miracle"

def find_client_base_path(client_id: str, suggested_base_path: str = "") -> str:
    """Finds the specific Miracle base path containing target client_id across all PC drives"""
    if suggested_base_path and os.path.exists(os.path.join(suggested_base_path, client_id)):
        return suggested_base_path

    discovered = scan_all_miracle_paths()
    for item in discovered:
        if client_id.upper() in [c.upper() for c in item["clients"]]:
            return item["path"]

    return resolve_valid_base_path(suggested_base_path)

@app.get("/api/discover-miracle-paths")
def discover_miracle_paths():
    """Lists all detected Miracle installation directories across all drives on the local PC"""
    discovered = scan_all_miracle_paths()
    rec = discovered[0]["path"] if discovered else "C:\\Miracle"
    return {
        "status": "success",
        "discovered_paths": discovered,
        "recommended_path": rec
    }

@app.get("/api/local-clients")
def get_local_clients(base_path: str = "C:\\Miracle"):
    """Lists all available client folders starting with CMP in local Miracle directory"""
    base_path = resolve_valid_base_path(base_path)
    if not base_path or not os.path.exists(base_path):
        return {"clients": [], "error": f"Base path '{base_path}' not found."}
    
    clients = []
    for d in os.listdir(base_path):
        full_p = os.path.join(base_path, d)
        if os.path.isdir(full_p) and d.upper().startswith("CMP"):
            try:
                handler = MiracleDBFHandler(full_p)
                company_name = handler.get_company_name()
                clients.append({"id": d, "name": company_name or d, "base_path": base_path})
            except Exception:
                clients.append({"id": d, "name": d, "base_path": base_path})
    return {"clients": sorted(clients, key=lambda x: x["id"]), "base_path": base_path}

@app.get("/api/local-years")
def get_local_years(base_path: str = "C:\\Miracle", client_id: str = "CMP0001"):
    """Lists all available financial year folders (YRxx) in local client directory"""
    base_path = find_client_base_path(client_id, base_path)
    if not base_path or not os.path.exists(base_path):
        return {"years": [], "recommended": "", "base_path": base_path}
    
    client_path = os.path.join(base_path, client_id)
    if not os.path.exists(client_path):
        return {"years": [], "recommended": "", "base_path": base_path}
        
    try:
        handler = MiracleDBFHandler(client_path)
        available = handler.get_available_year_folders()
        recommended = handler.get_latest_year_folder()
        bounds_map = handler.get_all_year_folder_bounds()
        
        mapped_years = []
        for yinfo in available:
            y = yinfo['name']
            is_valid = yinfo['is_valid']
            has_transactions = yinfo['has_transactions']
            
            b_info = bounds_map.get(y, {})
            f_start = b_info.get("fy_start", "")
            f_end = b_info.get("fy_end", "")
            
            if f_start and f_end and len(f_start) >= 10 and len(f_end) >= 10:
                try:
                    dt_start = datetime.datetime.strptime(f_start, "%Y-%m-%d")
                    dt_end = datetime.datetime.strptime(f_end, "%Y-%m-%d")
                    label = f"{dt_start.strftime('%d-%b-%Y')} To {dt_end.strftime('%d-%b-%Y')}"
                except Exception:
                    fy_s_yr = f_start[:4]
                    fy_e_yr = f_end[:4]
                    label = f"{fy_s_yr}-{str(fy_e_yr)[-2:]}"
            else:
                label = y
            
            mapped_years.append({
                "folder": y,
                "label": label,
                "is_valid": is_valid,
                "has_transactions": has_transactions,
                "recommended": (y == recommended)
            })
        return {"years": mapped_years, "recommended": recommended, "base_path": base_path}
    except Exception as e:
        print(f"Error fetching local years: {e}")
        return {"years": [], "recommended": "", "base_path": base_path}

@app.get("/api/local-ledgers")
def get_local_ledgers(base_path: str = "C:\\Miracle", client_id: str = "CMP0005", year_folder: str = "YR25"):
    """Reads classified party ledgers directly from local DBF files on client machine"""
    base_path = find_client_base_path(client_id, base_path)
    client_path = os.path.join(base_path, client_id)
    if not os.path.exists(client_path):
        return {"status": "success", "ledgers": [], "base_path": base_path}
    try:
        handler = MiracleDBFHandler(client_path)
        ledgers = handler.get_all_ledgers(year_folder)
        return {"status": "success", "year": year_folder, "ledgers": ledgers, "base_path": base_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read local ledgers: {str(e)}")

@app.get("/api/local-groups")
def get_local_groups(base_path: str = "C:\\Miracle", client_id: str = "CMP0005"):
    """Reads account groups hierarchy directly from local RKACCM11.DBF"""
    base_path = find_client_base_path(client_id, base_path)
    client_path = os.path.join(base_path, client_id)
    if not os.path.exists(client_path):
        return {"status": "success", "groups": [], "base_path": base_path}
    try:
        handler = MiracleDBFHandler(client_path)
        groups = handler.read_account_groups()
        return {"status": "success", "groups": groups, "base_path": base_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read account groups: {str(e)}")

@app.get("/api/local-products")
def get_local_products(base_path: str = "C:\\Miracle", client_id: str = "CMP0005", year_folder: str = ""):
    """Reads product masters directly from local RKACCM21.DBF"""
    base_path = find_client_base_path(client_id, base_path)
    client_path = os.path.join(base_path, client_id)
    if not os.path.exists(client_path):
        return {"status": "success", "products": [], "base_path": base_path}
    try:
        handler = MiracleDBFHandler(client_path)
        products = handler.get_products(year_folder)
        return {"status": "success", "products": products, "base_path": base_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read products: {str(e)}")

@app.get("/api/repair-bank-flags")
@app.post("/api/repair-bank-flags")
def repair_bank_flags(base_path: str = "C:\\Miracle", client_id: str = "CMP0005", year: str = ""):
    """Repairs closing balance flags for all pushed bank and cash entries on local PC"""
    try:
        base_path = resolve_valid_base_path(base_path)
        client_path = os.path.join(base_path, client_id)
        if not os.path.exists(client_path):
            return {"status": "error", "message": f"Client directory '{client_path}' not found."}
        handler = MiracleDBFHandler(client_path)
        count = handler.repair_bank_closing_flags(year_folder=year)
        return {"status": "success", "message": f"Repaired closing balance flags for {count} bank/cash entries."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/repair-narrations")
@app.post("/api/repair-narrations")
def repair_narrations(base_path: str = "C:\\Miracle", client_id: str = "CMP0005", year_folder: str = ""):
    """Repairs memo narrations (RKACCT40.DBF) for local client database"""
    try:
        base_path = resolve_valid_base_path(base_path)
        client_path = os.path.join(base_path, client_id)
        if not os.path.exists(client_path):
            return {"status": "error", "message": f"Client directory '{client_path}' not found."}
        handler = MiracleDBFHandler(client_path)
        res = handler.repair_missing_narrations(year_folder=year_folder)
        return {"status": "success", "message": "Narrations repaired successfully.", "result": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/repair-cdx-flags")
@app.post("/api/repair-cdx-flags")
def repair_cdx_flags(base_path: str = "C:\\Miracle", client_id: str = "CMP0005", year: str = ""):
    """Heals CDX index byte 28 header flags for local client tables"""
    try:
        base_path = resolve_valid_base_path(base_path)
        client_path = os.path.join(base_path, client_id)
        if not os.path.exists(client_path):
            return {"status": "error", "message": f"Client directory '{client_path}' not found."}
        handler = MiracleDBFHandler(client_path)
        count = handler.heal_cdx_header_flags(year_folder=year)
        return {"status": "success", "message": f"Healed CDX flags for {count} DBF tables."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/create-ledger")
def api_create_ledger(payload: dict):
    """Creates a new Miracle ledger directly in local DBF files on client PC"""
    try:
        miracle_base_path = resolve_valid_base_path(payload.get("miracle_base_path", "C:\\Miracle"))
        active_client_id = payload.get("active_client_id", "CMP0005")
        client_dir = os.path.join(miracle_base_path, active_client_id)
        
        name = payload.get("name", "").strip()
        print_name = payload.get("print_name", "").strip() or name
        group_code = payload.get("group_code", "").strip()
        gstin = payload.get("gstin", "").strip()
        city = payload.get("city", "").strip()
        module_type = payload.get("module_type", "").strip() or "Bank Statements"
        year = payload.get("year", "")
        
        save_memory = payload.get("save_memory", True)
        
        if not name:
            raise HTTPException(status_code=400, detail="Ledger name is required.")
            
        handler = MiracleDBFHandler(client_dir)
        ledger_code = handler.create_party_ledger(
            name=name,
            module=module_type,
            gstin=gstin,
            city=city,
            year_folder=year,
            explicit_group_code=group_code
        )

        if save_memory:
            try:
                from ai_memory import AIMemoryVault
                vault = AIMemoryVault()
                narration_key = payload.get("narration_key", "").strip()
                key_to_clean = narration_key if narration_key else name
                clean_key = AIMemoryVault.clean_mapping_key(key_to_clean) or AIMemoryVault.clean_mapping_key(name)
                if clean_key:
                    mem_data = vault.load_memory(active_client_id)
                    if "expense_mappings" not in mem_data:
                        mem_data["expense_mappings"] = {}
                    mem_data["expense_mappings"][clean_key] = name
                    vault.save_memory(active_client_id, mem_data)
            except Exception as mem_err:
                print(f"Warning: Could not save memory during bridge create-ledger: {mem_err}")

        return {
            "status": "success",
            "message": f"Successfully created ledger '{name}' with code '{ledger_code}'.",
            "ledger_code": ledger_code,
            "ledger_name": name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/inject")
def inject_vouchers(payload: InjectRequestPayload):
    """
    Receives extracted vouchers from Render Cloud Web App and writes
    them directly into local Miracle DBF tables (RKACCT41.DBF, RKACCT01.DBF, etc.)
    Also creates an automatic timestamped ZIP backup in configured custom backup_path.
    """
    try:
        miracle_base_path = resolve_valid_base_path(payload.miracle_base_path)
        active_client_id = payload.active_client_id
        active_year_folder = payload.active_year_folder
        module_type = payload.module_type
        vouchers = sanitize_surrogates(payload.vouchers or [])
        configured_backup_path = (payload.backup_path or "").strip()

        # Verify client path exists locally
        client_dir = os.path.join(miracle_base_path, active_client_id)
        if not os.path.exists(client_dir):
            raise HTTPException(
                status_code=404, 
                detail=f"Miracle client directory '{client_dir}' not found on this computer."
            )

        year_dir = os.path.join(client_dir, active_year_folder)
        if not os.path.exists(year_dir):
            raise HTTPException(
                status_code=404,
                detail=f"Miracle fiscal year directory '{year_dir}' not found."
            )

        # 1. Automatic Timestamped ZIP Backup before write
        backup_zip = None
        if not configured_backup_path or configured_backup_path.upper() != "SKIP":
            try:
                backup_zip = backup_full_client_folder(
                    active_client_id, 
                    miracle_base_path, 
                    custom_backup_path=configured_backup_path, 
                    active_year_folder=active_year_folder
                )
                print(f"📦 Created automated timestamped backup: {backup_zip}")
            except Exception as backup_err:
                print(f"⚠️ Backup Warning: {backup_err}")

        # 2. Thread-safe client DB lock & DBF injection
        with get_client_lock(active_client_id):
            handler = MiracleDBFHandler(client_dir)
            
            # Delegate injection based on module type with robust string matching
            m_type = (module_type or "").strip().lower()
            if m_type in ("bank", "bank_statements", "bank statements"):
                b_name = getattr(payload, "target_bank_name", None) or "Bank Account"
                b_code = getattr(payload, "target_bank_code", None) or ""
                res = handler._inject_bank_statements(vouchers, b_name, active_year_folder, payload_bank_code=b_code)
            elif m_type in ("sales", "sale"):
                res = handler._inject_sales(
                    vouchers, 
                    active_year_folder, 
                    setup_id=payload.sales_setup_id, 
                    sales_prefix=payload.sales_prefix
                )
            elif m_type in ("purchase", "purchases"):
                res = handler._inject_purchases(
                    vouchers, 
                    active_year_folder, 
                    setup_id=payload.purchase_setup_id, 
                    purchase_prefix=payload.purchase_prefix
                )
            elif m_type in ("cash", "cash_entries", "cash entries"):
                c_code = getattr(payload, "target_cash_code", None) or "ACASHACT"
                res = handler._inject_cash_entries(vouchers, c_code, active_year_folder)
            elif m_type in ("opening_balance", "opening_balances", "opening balance"):
                res = handler.push_opening_balances(vouchers, active_year_folder)
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported module_type '{module_type}'")

            audit_rep = handler.audit_report if hasattr(handler, 'audit_report') else {}
            return {
                "status": "success",
                "message": f"Successfully injected {len(vouchers)} {module_type} vouchers into Miracle DBF!",
                "backup_zip": backup_zip,
                "primary_year": active_year_folder,
                "audit_report": audit_rep,
                "result": res
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def push_masters_to_cloud():
    """Scans local Miracle DBF folders and pushes ledgers and products to Render Cloud master cache."""
    try:
        import requests
        base_path = "C:\\Miracle"
        if not os.path.exists(base_path):
            return
        
        cmp_folders = [f for f in os.listdir(base_path) if f.upper().startswith("CMP") and os.path.isdir(os.path.join(base_path, f))]
        for cmp in cmp_folders:
            client_path = os.path.join(base_path, cmp)
            try:
                handler = MiracleDBFHandler(client_path)
                ledgers = handler.read_ledgers_all_years()
                products = handler.read_products_all_years()
                if ledgers or products:
                    sync_url = f"{CLOUD_URL}/api/bridge/sync-masters"
                    payload = {
                        "client_id": cmp.upper(),
                        "ledgers": ledgers,
                        "products": products
                    }
                    requests.post(sync_url, json=payload, timeout=10)
                    print(f"☁️ Master Sync: Pushed {len(ledgers)} ledgers and {len(products)} products for {cmp} to Render Cloud.")
            except Exception as e:
                print(f"⚠️ Master Sync warning for {cmp}: {e}")
    except Exception as err:
        print(f"⚠️ Master Sync error: {err}")


def start_master_sync_loop():
    """Launches background thread for periodic master catalog syncing to Render Cloud."""
    def run_sync():
        time.sleep(5)
        push_masters_to_cloud()
        while True:
            time.sleep(60)  # Push every 60 seconds
            push_masters_to_cloud()
            
    t = threading.Thread(target=run_sync, daemon=True)
    t.start()


if __name__ == "__main__":
    print("🚀 Starting Miracle DBF Local Bridge Agent on port 9123...")
    start_master_sync_loop()
    
    # Safe Uvicorn Log Configuration for PyInstaller --windowed / GUI mode
    UVICORN_LOG_CONFIG = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(levelname)s - %(message)s",
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.NullHandler",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": "INFO"},
            "uvicorn.error": {"level": "INFO"},
            "uvicorn.access": {"handlers": ["default"], "level": "INFO"},
        },
    }

    try:
        uvicorn.run(app, host="0.0.0.0", port=9123, log_config=UVICORN_LOG_CONFIG)
    except Exception as run_err:
        print(f"Server error: {run_err}")
