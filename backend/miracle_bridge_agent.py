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

def backup_full_client_folder(client_id: str, base_path: str, custom_backup_path: str = "", active_year_folder: str = "") -> str:
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
        
    print(f"✅ [backup] Full client backup verified & created successfully at: {archive_path}")
    return archive_path


app = FastAPI(
    title="Miracle Local DBF Bridge Agent",
    description="Local Windows Agent for Miracle Accounting AI Auto-Entry",
    version="1.0.0"
)

# CORS: Allow communication from Render Cloud Web URL & Localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows requests from Render Cloud URL & Localhost
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class InjectRequestPayload(BaseModel):
    miracle_base_path: str
    active_client_id: str
    active_year_folder: str
    module_type: str  # "bank", "sales", "purchase", "cash", "opening_balance"
    vouchers: List[Dict[str, Any]]
    sales_setup_id: Optional[int] = 3
    purchase_setup_id: Optional[int] = 6
    sales_prefix: Optional[str] = "SS,SS"
    purchase_prefix: Optional[str] = "PP,PP"
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

@app.get("/api/local-clients")
def get_local_clients(base_path: str = "C:\\Miracle"):
    """Lists all available client folders starting with CMP in local Miracle directory"""
    if not os.path.exists(base_path):
        return {"clients": [], "error": f"Base path '{base_path}' not found."}
    
    clients = [
        d for d in os.listdir(base_path)
        if os.path.isdir(os.path.join(base_path, d)) and d.upper().startswith("CMP")
    ]
    return {"clients": sorted(clients)}

@app.get("/api/local-ledgers")
def get_local_ledgers(base_path: str = "C:\\Miracle", client_id: str = "CMP0005", year_folder: str = "YR25"):
    """Reads classified party ledgers directly from local DBF files on client machine"""
    try:
        handler = MiracleDBFHandler(base_path, client_id)
        ledgers = handler.get_all_ledgers(year_folder)
        return {"status": "success", "ledgers": ledgers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read local ledgers: {str(e)}")

@app.get("/api/local-groups")
def get_local_groups(base_path: str = "C:\\Miracle", client_id: str = "CMP0005"):
    """Reads account groups hierarchy directly from local RKACCM11.DBF"""
    try:
        handler = MiracleDBFHandler(base_path, client_id)
        groups = handler.get_account_groups()
        return {"status": "success", "groups": groups}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read account groups: {str(e)}")

@app.post("/inject")
def inject_vouchers(payload: InjectRequestPayload):
    """
    Receives extracted vouchers from Render Cloud Web App and writes
    them directly into local Miracle DBF tables (RKACCT41.DBF, RKACCT01.DBF, etc.)
    Also creates an automatic timestamped ZIP backup in configured custom backup_path.
    """
    try:
        miracle_base_path = payload.miracle_base_path
        active_client_id = payload.active_client_id
        active_year_folder = payload.active_year_folder
        module_type = payload.module_type
        vouchers = payload.vouchers
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
            handler = MiracleDBFHandler(miracle_base_path, active_client_id)
            
            # Delegate injection based on module type
            if module_type == "bank":
                res = handler._inject_bank_statements(vouchers, year_dir)
            elif module_type == "sales":
                res = handler._inject_sales(
                    vouchers, 
                    year_dir, 
                    setup_id=payload.sales_setup_id, 
                    sales_prefix=payload.sales_prefix
                )
            elif module_type == "purchase":
                res = handler._inject_purchases(
                    vouchers, 
                    year_dir, 
                    setup_id=payload.purchase_setup_id, 
                    purchase_prefix=payload.purchase_prefix
                )
            elif module_type == "cash":
                res = handler._inject_cash_entries(vouchers, year_dir)
            elif module_type == "opening_balance":
                res = handler.push_opening_balances(vouchers, year_dir)
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported module_type '{module_type}'")

            return {
                "status": "success",
                "message": f"Successfully injected {len(vouchers)} {module_type} vouchers into Miracle DBF!",
                "backup_zip": backup_zip,
                "result": res
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    print("🚀 Starting Miracle DBF Local Bridge Agent on port 9123...")
    
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
        uvicorn.run(app, host="127.0.0.1", port=9123, log_config=UVICORN_LOG_CONFIG)
    except Exception as run_err:
        print(f"Server error: {run_err}")
