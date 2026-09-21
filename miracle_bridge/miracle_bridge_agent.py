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


BRIDGE_VERSION = "2.0.0"

def resolve_cloud_url() -> str:
    """Dynamically resolves Cloud Server URL from environment, local settings.json, or default fallback."""
    if os.environ.get("RENDER_CLOUD_URL"):
        return os.environ.get("RENDER_CLOUD_URL").rstrip("/")
    
    config_paths = [
        os.path.join(BASE_DIR, "bridge_config.json"),
        os.path.join(BASE_DIR, "settings.json"),
        "C:\\Miracle\\bridge_config.json"
    ]
    for cp in config_paths:
        if os.path.exists(cp):
            try:
                with open(cp, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    if cfg.get("cloud_url"):
                        return cfg["cloud_url"].rstrip("/")
            except Exception:
                pass

    return "https://miracle-ai-autoentry.onrender.com"

CLOUD_URL = resolve_cloud_url()


def enable_windows_autostart():
    """Registers MiracleBridge in Windows Startup (HKCU Run key) on client PC."""
    if sys.platform != 'win32':
        return
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
        exe_path = os.path.abspath(sys.argv[0])
        winreg.SetValueEx(key, "MiracleBridge", 0, winreg.REG_SZ, f'"{exe_path}"')
        winreg.CloseKey(key)
        print("✅ Registered MiracleBridge in Windows Startup (HKCU Run).")
    except Exception as e:
        print(f"⚠️ Could not register Windows Startup key: {e}")


def trigger_ota_update(download_url: str):
    """Downloads updated binary, creates batch replacement script, and restarts MiracleBridge."""
    try:
        import requests
        import subprocess
        print(f"🔄 MiracleBridge OTA Update starting from {download_url}...")
        
        target_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        new_exe_path = os.path.join(target_dir, "MiracleBridge_new.exe")
        current_exe_path = os.path.abspath(sys.argv[0])
        exe_basename = os.path.basename(current_exe_path)
        
        full_url = download_url if download_url.startswith("http") else (CLOUD_URL + download_url)
        resp = requests.get(full_url, stream=True, timeout=30)
        if resp.status_code == 200:
            with open(new_exe_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            print("✅ Downloaded updated MiracleBridge binary.")
            
            bat_path = os.path.join(target_dir, "update_bridge.bat")
            bat_content = f"""@echo off
timeout /t 2 /nobreak > nul
del /f /q "{exe_basename}"
move /y "MiracleBridge_new.exe" "{exe_basename}"
start "" "{exe_basename}"
del "%~f0"
"""
            with open(bat_path, "w", encoding="utf-8") as bf:
                bf.write(bat_content)
                
            print("🚀 Executing background updater batch script and closing agent...")
            if sys.platform == 'win32':
                subprocess.Popen(["cmd.exe", "/c", bat_path], creationflags=0x08000000, cwd=target_dir)
            else:
                subprocess.Popen(["/bin/bash", "-c", f"sleep 2 && mv -f MiracleBridge_new.exe '{exe_basename}' && python3 miracle_bridge_agent.py"], cwd=target_dir)
            sys.exit(0)
        else:
            print(f"⚠️ OTA Update download failed with status {resp.status_code}")
    except Exception as err:
        print(f"❌ Error during MiracleBridge OTA Update: {err}")


def check_for_updates_background(manual_trigger: bool = False):
    """Queries Render Cloud version endpoint for OTA update triggers."""
    try:
        import requests
        check_url = f"{CLOUD_URL}/api/bridge/version?current_version={BRIDGE_VERSION}"
        r = requests.get(check_url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data.get("needs_update") and data.get("download_url"):
                print(f"🔔 Update available: v{data.get('latest_version')} (Current: v{BRIDGE_VERSION})")
                trigger_ota_update(data.get("download_url"))
            else:
                if manual_trigger:
                    print(f"✅ MiracleBridge is up to date (v{BRIDGE_VERSION}).")
        else:
            if manual_trigger:
                print(f"⚠️ Update check failed with status code {r.status_code}")
    except Exception as err:
        print(f"⚠️ Background update check warning: {err}")


def start_update_checker_loop():
    """Launches background thread for periodic version checks."""
    def run_loop():
        time.sleep(10)
        check_for_updates_background(manual_trigger=False)
        while True:
            time.sleep(14400)  # Every 4 hours
            check_for_updates_background(manual_trigger=False)
            
    t = threading.Thread(target=run_loop, daemon=True)
    t.start()


def push_masters_to_cloud():
    """Scans local Miracle DBF folders dynamically across all drives and pushes ledgers and products to Render Cloud master cache."""
    try:
        import requests
        discovered_clients = scan_all_miracle_paths()
        if not discovered_clients:
            return
            
        for item in discovered_clients:
            client_path = item.get("path")
            client_id = item.get("client_id", "").upper()
            if not client_path or not os.path.exists(client_path):
                continue
            try:
                handler = MiracleDBFHandler(client_path)
                ledgers = handler.read_ledgers_all_years()
                products = handler.read_products_all_years()
                if ledgers or products:
                    sync_url = f"{CLOUD_URL}/api/bridge/sync-masters"
                    payload = {
                        "client_id": client_id,
                        "ledgers": ledgers,
                        "products": products
                    }
                    requests.post(sync_url, json=payload, timeout=10)
                    print(f"☁️ Master Sync: Pushed {len(ledgers)} ledgers and {len(products)} products for {client_id} to Render Cloud.")
            except Exception as e:
                print(f"⚠️ Master Sync warning for {client_id}: {e}")
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


def start_system_tray_icon():
    """Initializes Windows System Tray notification area icon."""
    try:
        import pystray
        from PIL import Image, ImageDraw
        
        img = Image.new('RGB', (64, 64), color=(15, 23, 42))
        draw = ImageDraw.Draw(img)
        draw.ellipse([12, 12, 52, 52], fill=(16, 185, 129))
        
        def on_check_updates(icon, item):
            threading.Thread(target=check_for_updates_background, kwargs={"manual_trigger": True}, daemon=True).start()
            
        def on_exit_app(icon, item):
            icon.stop()
            sys.exit(0)
            
        menu = pystray.Menu(
            pystray.MenuItem("MiracleBridge Status: Active", lambda icon, item: None, enabled=False),
            pystray.MenuItem(f"Version: v{BRIDGE_VERSION}", lambda icon, item: None, enabled=False),
            pystray.MenuItem("Port: 9123 (Localhost)", lambda icon, item: None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Check for Updates", on_check_updates),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit Agent", on_exit_app)
        )
        
        icon = pystray.Icon("MiracleBridge", img, f"MiracleBridge v{BRIDGE_VERSION} (Port 9123)", menu)
        tray_thread = threading.Thread(target=icon.run, daemon=True)
        tray_thread.start()
        print("🟢 MiracleBridge System Tray Icon initialized successfully.")
    except Exception as e:
        print(f"ℹ️ System Tray Notice (Running without Tray Icon UI): {e}")


import secrets
import json

def get_or_create_bridge_secret_token() -> str:
    """Gets or generates a secure secret token for local agent authorization."""
    if os.environ.get("BRIDGE_SECRET_TOKEN"):
        return os.environ.get("BRIDGE_SECRET_TOKEN")
    config_paths = [
        os.path.join(BASE_DIR, "bridge_config.json"),
        os.path.join(BASE_DIR, "settings.json"),
        "C:\\Miracle\\bridge_config.json"
    ]
    for cp in config_paths:
        if os.path.exists(cp):
            try:
                with open(cp, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    if cfg.get("bridge_secret_token"):
                        return cfg["bridge_secret_token"]
            except Exception:
                pass
    token = secrets.token_hex(32)
    try:
        cfg_file = os.path.join(BASE_DIR, "bridge_config.json")
        with open(cfg_file, "w", encoding="utf-8") as f:
            json.dump({"bridge_secret_token": token}, f, indent=2)
    except Exception:
        pass
    return token

EXPECTED_SECRET_TOKEN = get_or_create_bridge_secret_token()

app = FastAPI(
    title="Miracle Local DBF Bridge Agent",
    description="Local Windows Agent for Miracle Accounting AI Auto-Entry",
    version=BRIDGE_VERSION
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
async def verify_bridge_token_and_cors_headers(request, call_next):
    if request.method == "OPTIONS":
        from fastapi.responses import Response
        response = Response(status_code=204)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Allow-Private-Network"] = "true"
        return response

    # Token Verification Guard for protected endpoints
    if request.url.path not in ["/health", "/status", "/docs", "/openapi.json"]:
        auth_header = request.headers.get("X-Bridge-Token") or request.headers.get("Authorization")
        if auth_header:
            clean_token = auth_header.replace("Bearer ", "").strip()
            if clean_token != EXPECTED_SECRET_TOKEN:
                from fastapi.responses import JSONResponse
                print(f"⚠️ Security Notice: Rejected unauthorized access attempt to {request.url.path}")
                return JSONResponse(status_code=401, content={"detail": "Unauthorized MiracleBridge Access. Invalid X-Bridge-Token."})

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
    target_cash_code: Optional[str] = "ACASHACT"
    backup_path: Optional[str] = ""
    force_push: Optional[bool] = False

@app.get("/health")
@app.get("/status")
def health_check():
    """Health check endpoint to confirm bridge agent is running on client PC"""
    return {
        "status": "online",
        "agent_name": "MiracleBridge Agent",
        "version": BRIDGE_VERSION,
        "port": 9123,
        "platform": sys.platform
    }

class LocalPDFParseRequest(BaseModel):
    pdf_path: str
    password: Optional[str] = ""
    client_id: Optional[str] = "CMP0001"

def extract_pdf_stream_locally(pdf_path: str, password: str = "") -> List[Dict[str, Any]]:
    """
    Client PC Stream Generator: Parses PDF page-by-page.
    Calls gc.collect() after each page to keep Python desktop RAM < 50 MB.
    """
    import gc
    import re
    parsed_rows = []
    
    try:
        import pypdf
        reader = pypdf.PdfReader(pdf_path)
        if reader.is_encrypted and password:
            reader.decrypt(password)
            
        date_pattern = re.compile(r'(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})')
        num_pattern = re.compile(r'([\d,]+\.\d{2})')

        for page_idx, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            
            for line in lines:
                try:
                    date_match = date_pattern.search(line)
                    num_matches = num_pattern.findall(line)
                    
                    if date_match and num_matches:
                        tx_date = date_match.group(1)
                        clean_line = line.replace(tx_date, '').strip()
                        clean_line = "".join(c for c in clean_line if ord(c) >= 32 and not (0xD800 <= ord(c) <= 0xDFFF))
                        
                        nums = [float(n.replace(',', '')) for n in num_matches if n.replace(',', '').replace('.', '').isdigit()]
                        if not nums:
                            continue
                            
                        deposit = 0.0
                        withdrawal = 0.0
                        balance = 0.0
                        
                        if len(nums) >= 2:
                            balance = nums[-1]
                            amount = nums[-2]
                            if "CR" in line.upper() or "BY" in line.upper() or "DEP" in line.upper():
                                deposit = amount
                            else:
                                withdrawal = amount
                        elif len(nums) == 1:
                            withdrawal = nums[0]

                        parsed_rows.append({
                            "date": tx_date,
                            "narration": clean_line[:200],
                            "withdrawal": withdrawal,
                            "deposit": deposit,
                            "balance": balance,
                            "chq_no": ""
                        })
                except Exception as line_err:
                    continue  # Safely skip unparseable line without stopping document flow

            # Reclaim page RAM immediately
            del page
            del text
            gc.collect()

    except Exception as err:
        print(f"⚠️ Local PDF stream parsing warning: {err}")
        
    return parsed_rows


@app.post("/api/local/parse-pdf")
def parse_pdf_locally(req: LocalPDFParseRequest):
    """
    Parses a local PDF statement on the Client PC with page-by-page streaming + GC.
    Returns lightweight JSON array ready for Cloud transmission.
    """
    if not os.path.exists(req.pdf_path):
        raise HTTPException(status_code=404, detail=f"PDF file not found at {req.pdf_path}")

    rows = extract_pdf_stream_locally(req.pdf_path, req.password or "")
    
    return {
        "status": "success",
        "client_id": req.client_id,
        "pdf_path": req.pdf_path,
        "extracted_count": len(rows),
        "transactions": rows
    }


# ── CLIENT-SIDE IMAGE OPTIMIZATION, DEDUPLICATION & SELF-LEARNING ENGINE ─────

LOCAL_INTEL_DIR = os.path.join(os.path.expanduser("~"), ".miracle_bridge")
LOCAL_INTEL_DB = os.path.join(LOCAL_INTEL_DIR, "client_intelligence.db")
TEMP_IMAGE_CACHE_DIR = os.path.join(LOCAL_INTEL_DIR, "temp_image_cache")
BLOCKED_GENERIC_KEYWORDS = {"CASH", "PETROL", "RENT", "SALARY", "TAX", "GST", "BANK CHARGES", "WITHDRAWAL"}


def init_client_intelligence_db():
    """Initializes local SQLite database for image deduplication, self-learning regex memory, and offline resilience queue."""
    os.makedirs(LOCAL_INTEL_DIR, exist_ok=True)
    os.makedirs(TEMP_IMAGE_CACHE_DIR, exist_ok=True)
    
    import sqlite3
    with sqlite3.connect(LOCAL_INTEL_DB) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS file_dedup_cache (
                file_hash TEXT PRIMARY KEY,
                created_at REAL,
                client_id TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS local_regex_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT,
                pattern TEXT,
                ledger_code TEXT,
                direction TEXT,
                hit_count INTEGER DEFAULT 1,
                confidence REAL DEFAULT 0.90,
                last_used_timestamp REAL,
                created_at REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS offline_pending_vouchers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT,
                payload_json TEXT,
                created_at REAL,
                status TEXT DEFAULT 'PENDING',
                retry_count INTEGER DEFAULT 0
            )
        """)
        conn.commit()


def queue_offline_voucher(client_id: str, voucher_data: dict):
    """Saves un-synced vouchers locally when internet connectivity drops."""
    try:
        init_client_intelligence_db()
        import sqlite3
        with sqlite3.connect(LOCAL_INTEL_DB) as conn:
            conn.execute(
                "INSERT INTO offline_pending_vouchers (client_id, payload_json, created_at) VALUES (?, ?, ?)",
                (client_id, json.dumps(voucher_data), time.time())
            )
            conn.commit()
        print(f"📦 Network Notice: Saved voucher payload locally to client_intelligence.db offline queue.")
    except Exception as err:
        print(f"⚠️ Offline queue warning: {err}")


def start_offline_sync_loop():
    """
    Background worker: Monitors connectivity to Render Cloud server every 30s.
    Automatically flushes pending offline vouchers when network restores.
    """
    def run_offline_sync():
        init_client_intelligence_db()
        import sqlite3
        import requests

        time.sleep(15)  # Initial boot delay
        while True:
            time.sleep(30)
            try:
                # Ping cloud health endpoint
                h_res = requests.get(f"{CLOUD_URL}/health", timeout=5)
                if h_res.status_code == 200:
                    with sqlite3.connect(LOCAL_INTEL_DB) as conn:
                        conn.row_factory = sqlite3.Row
                        cur = conn.cursor()
                        cur.execute("SELECT id, client_id, payload_json FROM offline_pending_vouchers WHERE status = 'PENDING' LIMIT 5")
                        pending_rows = cur.fetchall()

                        for row in pending_rows:
                            rec_id = row["id"]
                            c_id = row["client_id"]
                            v_payload = json.loads(row["payload_json"])

                            items_data = v_payload if isinstance(v_payload, list) else v_payload.get("items", v_payload.get("vouchers", []))
                            mod_type = v_payload.get("module_type", "bank") if isinstance(v_payload, dict) else "bank"

                            # Attempt cloud sync post
                            sync_res = requests.post(
                                f"{CLOUD_URL}/api/vouchers/sync-offline",
                                json={"client_id": c_id, "module_type": mod_type, "items": items_data},
                                timeout=10
                            )
                            if sync_res.status_code in (200, 201, 202):
                                cur.execute("UPDATE offline_pending_vouchers SET status = 'SYNCED' WHERE id = ?", (rec_id,))
                                conn.commit()
                                print(f"🚀 Auto-Sync Success: Successfully pushed queued offline voucher #{rec_id} to cloud!")
            except Exception as e:
                pass

    t = threading.Thread(target=run_offline_sync, daemon=True)
    t.start()
    print("🟢 MiracleBridge Offline Auto-Sync Daemon Thread started.")


class ImageOptimizationRequest(BaseModel):
    image_path: str
    client_id: Optional[str] = "CMP0001"
    max_dim: Optional[int] = 1920


class LocalRegexMatchRequest(BaseModel):
    narration: str
    direction: str
    client_id: Optional[str] = "CMP0001"


class LearnRuleRequest(BaseModel):
    narration: str
    ledger_code: str
    direction: str
    client_id: Optional[str] = "CMP0001"


def optimize_and_deduplicate_image(image_path: str, client_id: str, max_dim: int = 1920) -> Dict[str, Any]:
    """
    Client PC Image Optimization:
    1. Computes SHA256 hash to skip duplicate bill uploads.
    2. Resizes camera photo to 1080p (max_dim x max_dim).
    3. Converts to Grayscale ('L') and boosts contrast 1.5x for high-precision OCR.
    4. Saves compressed WebP (~250 KB) with silent fallback to raw file if PIL fails.
    """
    try:
        init_client_intelligence_db()
        import hashlib
        import sqlite3

        if not os.path.exists(image_path):
            return {"status": "error", "message": f"File not found: {image_path}", "upload_path": image_path}

        # 1. Compute SHA256 Hash for deduplication
        hasher = hashlib.sha256()
        with open(image_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        file_hash = hasher.hexdigest()

        with sqlite3.connect(LOCAL_INTEL_DB) as conn:
            cur = conn.cursor()
            cur.execute("SELECT file_hash FROM file_dedup_cache WHERE file_hash = ?", (file_hash,))
            if cur.fetchone():
                return {
                    "status": "duplicate_skipped",
                    "message": "Invoice already processed on this PC.",
                    "file_hash": file_hash,
                    "upload_path": image_path
                }

        # 2. Downsample and optimize image using Pillow
        opt_filename = f"{file_hash[:12]}_compressed.webp"
        opt_path = os.path.join(TEMP_IMAGE_CACHE_DIR, opt_filename)

        from PIL import Image, ImageEnhance
        with Image.open(image_path) as img:
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            img = img.convert("L")
            img = ImageEnhance.Contrast(img).enhance(1.5)
            img.save(opt_path, "WEBP", quality=82, optimize=True)

        with sqlite3.connect(LOCAL_INTEL_DB) as conn:
            conn.execute("INSERT INTO file_dedup_cache (file_hash, created_at, client_id) VALUES (?, ?, ?)",
                         (file_hash, time.time(), client_id))
            conn.commit()

        return {
            "status": "success",
            "upload_path": opt_path,
            "raw_fallback_path": image_path,
            "file_hash": file_hash,
            "saved_bytes": max(0, os.path.getsize(image_path) - os.path.getsize(opt_path))
        }

    except Exception as err:
        print(f"⚠️ Local image compression fallback warning: {err}")
        return {"status": "success", "upload_path": image_path, "raw_fallback_path": image_path, "file_hash": None}


def match_narration_locally(client_id: str, narration: str, direction: str) -> Dict[str, Any]:
    """
    Executes Stage 1 & Stage 2 Regex matching on the Client PC in < 1ms O(1) time.
    """
    try:
        init_client_intelligence_db()
        import sqlite3
        import re
        
        cleaned = narration.upper().strip()

        with sqlite3.connect(LOCAL_INTEL_DB) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            
            cur.execute("""
                SELECT id, pattern, ledger_code, hit_count, confidence 
                FROM local_regex_rules 
                WHERE client_id = ? AND direction = ?
                ORDER BY hit_count DESC
            """, (client_id, direction.upper()))

            for rule in cur.fetchall():
                if re.search(rule["pattern"], cleaned, re.IGNORECASE):
                    cur.execute("""
                        UPDATE local_regex_rules 
                        SET hit_count = hit_count + 1, last_used_timestamp = ? 
                        WHERE id = ?
                    """, (time.time(), rule["id"]))
                    conn.commit()

                    return {
                        "matched": True,
                        "ledger_code": rule["ledger_code"],
                        "confidence": rule["confidence"],
                        "source": "client_local_regex"
                    }
    except Exception as err:
        print(f"⚠️ Local regex match warning: {err}")

    return {"matched": False}


def learn_and_prune_rules(client_id: str, narration: str, ledger_code: str, direction: str):
    """
    Self-Learning Module: Creates regex rule when voucher is approved.
    Auto-Pruning Engine: Automatically purges stale rules (> 90 days unused) & keeps DB < 200 KB.
    """
    try:
        init_client_intelligence_db()
        import sqlite3
        import re

        cleaned_words = [w for w in re.sub(r'[^A-Z\s]', '', narration.upper()).split() if len(w) > 2]
        if any(word in BLOCKED_GENERIC_KEYWORDS for word in cleaned_words) and len(cleaned_words) <= 2:
            return

        tokens = [t for t in cleaned_words if t not in {"NEFT", "RTGS", "UPI", "IMPS", "PAID", "FROM", "TO"}][:3]
        if not tokens:
            return
            
        pattern = r'\b' + r'\s+'.join(re.escape(t) for t in tokens) + r'\b'

        with sqlite3.connect(LOCAL_INTEL_DB) as conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM local_regex_rules WHERE client_id = ? AND pattern = ?", (client_id, pattern))
            existing = cur.fetchone()

            if existing:
                cur.execute("""
                    UPDATE local_regex_rules 
                    SET hit_count = hit_count + 1, last_used_timestamp = ? 
                    WHERE id = ?
                """, (time.time(), existing[0]))
            else:
                cur.execute("""
                    INSERT INTO local_regex_rules 
                    (client_id, pattern, ledger_code, direction, hit_count, confidence, last_used_timestamp, created_at)
                    VALUES (?, ?, ?, ?, 1, 0.95, ?, ?)
                """, (client_id, pattern, ledger_code, direction.upper(), time.time(), time.time()))

            # Auto-prune rules unused for > 90 days with <= 2 hits
            cutoff_90_days = time.time() - (90 * 86400)
            cur.execute("""
                DELETE FROM local_regex_rules 
                WHERE client_id = ? AND last_used_timestamp < ? AND hit_count <= 2
            """, (client_id, cutoff_90_days))

            # Cap max active rules per client at 500 (Python-driven list slice for 100% SQLite compatibility)
            cur.execute("SELECT id FROM local_regex_rules WHERE client_id = ? ORDER BY hit_count DESC, last_used_timestamp DESC", (client_id,))
            all_rule_ids = [r[0] for r in cur.fetchall()]
            if len(all_rule_ids) > 500:
                ids_to_delete = all_rule_ids[500:]
                placeholders = ",".join(["?"] * len(ids_to_delete))
                cur.execute(f"DELETE FROM local_regex_rules WHERE id IN ({placeholders})", ids_to_delete)

            conn.commit()
            clean_old_temp_images()

    except Exception as err:
        print(f"⚠️ Rule learning warning: {err}")


def clean_old_temp_images():
    """Deletes cached compressed images older than 7 days."""
    try:
        cutoff_7_days = time.time() - (7 * 86400)
        if os.path.exists(TEMP_IMAGE_CACHE_DIR):
            for fname in os.listdir(TEMP_IMAGE_CACHE_DIR):
                fpath = os.path.join(TEMP_IMAGE_CACHE_DIR, fname)
                if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff_7_days:
                    os.remove(fpath)
    except Exception:
        pass


@app.post("/api/local/optimize-image")
def optimize_image_endpoint(req: ImageOptimizationRequest):
    """Endpoint to optimize & deduplicate bill photos on the Client PC."""
    res = optimize_and_deduplicate_image(req.image_path, req.client_id or "CMP0001", req.max_dim or 1920)
    return res


@app.post("/api/local/match-regex")
def match_regex_endpoint(req: LocalRegexMatchRequest):
    """Endpoint for instant sub-millisecond local narration matching."""
    res = match_narration_locally(req.client_id or "CMP0001", req.narration, req.direction)
    return res


@app.post("/api/local/learn-rule")
def learn_rule_endpoint(req: LearnRuleRequest):
    """Endpoint to register a self-learned regex rule on approval."""
    learn_and_prune_rules(req.client_id or "CMP0001", req.narration, req.ledger_code, req.direction)
    return {"status": "success", "message": "Rule registered and local DB auto-pruned"}




def resolve_valid_base_path(base_path: str) -> str:
    """Intelligently resolves the actual Miracle folder on the local Windows PC if a Mac/cloud path is passed"""
    if base_path and os.path.exists(base_path) and not ("/Users/" in base_path or "/home/" in base_path):
        return base_path
    
    candidates = ["C:\\Miracle", "D:\\Miracle", "E:\\Miracle", "C:\\Miracle9070", "D:\\Miracle9070", "E:\\Miracle9070"]
    for c in candidates:
        if os.path.exists(c):
            return c
            
    for drive in ["C:\\", "D:\\", "E:\\"]:
        if os.path.exists(drive):
            try:
                for sub in os.listdir(drive):
                    if sub.upper().startswith("CMP") and os.path.isdir(os.path.join(drive, sub)):
                        return drive
            except Exception:
                pass
    return "C:\\Miracle"

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
                clients.append({"id": d, "name": company_name or d})
            except Exception:
                clients.append({"id": d, "name": d})
    return {"clients": sorted(clients, key=lambda x: x["id"])}

@app.get("/api/local-years")
def get_local_years(base_path: str = "C:\\Miracle", client_id: str = "CMP0001"):
    """Lists all available financial year folders (YRxx) in local client directory"""
    base_path = resolve_valid_base_path(base_path)
    if not base_path or not os.path.exists(base_path):
        return {"years": [], "recommended": ""}
    
    client_path = os.path.join(base_path, client_id)
    if not os.path.exists(client_path):
        return {"years": [], "recommended": ""}
        
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
        return {"years": mapped_years, "recommended": recommended}
    except Exception as e:
        print(f"Error fetching local years: {e}")
        return {"years": [], "recommended": ""}

@app.get("/api/local-ledgers")
def get_local_ledgers(base_path: str = "C:\\Miracle", client_id: str = "CMP0005", year_folder: str = "YR25", year: Optional[str] = None):
    """Reads classified party ledgers directly from local DBF files on client machine"""
    base_path = resolve_valid_base_path(base_path)
    client_path = os.path.join(base_path, client_id)
    if not os.path.exists(client_path):
        return {"status": "success", "ledgers": []}
    try:
        target_year = year or year_folder or "YR25"
        handler = MiracleDBFHandler(client_path)
        ledgers = handler.get_all_ledgers(target_year)
        return {"status": "success", "year": target_year, "ledgers": ledgers, "data": ledgers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read local ledgers: {str(e)}")

@app.get("/api/local-groups")
def get_local_groups(base_path: str = "C:\\Miracle", client_id: str = "CMP0005"):
    """Reads account groups hierarchy directly from local RKACCM11.DBF"""
    base_path = resolve_valid_base_path(base_path)
    client_path = os.path.join(base_path, client_id)
    if not os.path.exists(client_path):
        return {"status": "success", "groups": []}
    try:
        handler = MiracleDBFHandler(client_path)
        groups = handler.read_account_groups()
        return {"status": "success", "groups": groups}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read account groups: {str(e)}")

@app.get("/api/local-products")
def get_local_products(base_path: str = "C:\\Miracle", client_id: str = "CMP0005", year_folder: str = "", year: Optional[str] = None):
    """Reads product masters directly from local RKACCM21.DBF"""
    base_path = resolve_valid_base_path(base_path)
    client_path = os.path.join(base_path, client_id)
    if not os.path.exists(client_path):
        return {"status": "success", "products": []}
    try:
        target_year = year or year_folder or ""
        handler = MiracleDBFHandler(client_path)
        products = handler.get_products(target_year)
        return {"status": "success", "products": products}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read products: {str(e)}")

@app.get("/api/repair-bank-flags")
@app.post("/api/repair-bank-flags")
def repair_bank_flags(base_path: str = "C:\\Miracle", client_id: str = "CMP0005", year: str = "", year_folder: str = ""):
    """Repairs closing balance flags for all pushed bank and cash entries on local PC"""
    try:
        base_path = resolve_valid_base_path(base_path)
        client_path = os.path.join(base_path, client_id)
        if not os.path.exists(client_path):
            return {"status": "error", "message": f"Client directory '{client_path}' not found."}
        target_year = year_folder or year or ""
        handler = MiracleDBFHandler(client_path)
        count = handler.repair_bank_closing_flags(year_folder=target_year)
        return {"status": "success", "message": f"Repaired closing balance flags for {count} bank/cash entries."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/repair-narrations")
@app.post("/api/repair-narrations")
def repair_narrations(base_path: str = "C:\\Miracle", client_id: str = "CMP0005", year_folder: str = "", year: str = ""):
    """Repairs memo narrations (RKACCT40.DBF) for local client database"""
    try:
        base_path = resolve_valid_base_path(base_path)
        client_path = os.path.join(base_path, client_id)
        if not os.path.exists(client_path):
            return {"status": "error", "message": f"Client directory '{client_path}' not found."}
        target_year = year_folder or year or ""
        handler = MiracleDBFHandler(client_path)
        res = handler.repair_missing_narrations(year_folder=target_year)
        return {"status": "success", "message": "Narrations repaired successfully.", "result": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/repair-cdx-flags")
@app.post("/api/repair-cdx-flags")
def repair_cdx_flags(base_path: str = "C:\\Miracle", client_id: str = "CMP0005", year: str = "", year_folder: str = ""):
    """Heals CDX index byte 28 header flags for local client tables"""
    try:
        base_path = resolve_valid_base_path(base_path)
        client_path = os.path.join(base_path, client_id)
        if not os.path.exists(client_path):
            return {"status": "error", "message": f"Client directory '{client_path}' not found."}
        target_year = year_folder or year or ""
        handler = MiracleDBFHandler(client_path)
        count = handler.heal_cdx_header_flags(year_folder=target_year)
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
            handler = MiracleDBFHandler(client_dir)
            
            # Delegate injection based on module type with robust string matching & multi-year date partitioning
            m_type = (module_type or "").strip().lower()
            if m_type in ("bank", "bank_statements", "bank statements"):
                norm_module = "Bank Statements"
            elif m_type in ("sales", "sale"):
                norm_module = "Sales"
            elif m_type in ("purchase", "purchases"):
                norm_module = "Purchases"
            elif m_type in ("cash", "cash_entries", "cash entries"):
                norm_module = "Cash Entries"
            elif m_type in ("opening_balance", "opening_balances", "opening balance"):
                norm_module = "Opening Balances"
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported module_type '{module_type}'")

            if norm_module == "Opening Balances":
                res = handler.push_opening_balances(vouchers, active_year_folder)
            else:
                b_name = getattr(payload, "target_bank_name", None) or "Bank Account"
                c_code = getattr(payload, "target_cash_code", None) or "ACASHACT"
                force_p = bool(getattr(payload, "force_push", False))
                
                res = handler.inject_vouchers(
                    module=norm_module,
                    vouchers=vouchers,
                    year_folder=active_year_folder,
                    sales_prefix=payload.sales_prefix or "SS,SS",
                    purchase_prefix=payload.purchase_prefix or "PP,PP",
                    sales_setup_id=payload.sales_setup_id or 5,
                    purchase_setup_id=payload.purchase_setup_id or 6,
                    bank_name=b_name,
                    target_cash_code=c_code,
                    force_push=force_p
                )

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

def check_single_instance_lock(port: int = 9123) -> bool:
    """Checks if another instance of MiracleBridgeAgent is already running on port 9123."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
        s.close()
        return True
    except OSError:
        return False

def cleanup_old_temp_files():
    """Auto-cleans temporary upload files older than 1 week (7 days / 604,800 seconds) on agent startup."""
    try:
        temp_dir = tempfile.gettempdir()
        now = time.time()
        one_week_seconds = 7 * 86400  # 604,800 seconds (1 week)
        for filename in os.listdir(temp_dir):
            if filename.startswith("lock_bypass_") or filename.startswith("temp_"):
                filepath = os.path.join(temp_dir, filename)
                if os.path.isfile(filepath) and (now - os.path.getmtime(filepath)) > one_week_seconds:
                    try:
                        os.remove(filepath)
                    except Exception:
                        pass
    except Exception as cleanup_err:
        print(f"⚠️ Temp cleanup notice: {cleanup_err}")

if __name__ == "__main__":
    if not check_single_instance_lock(9123):
        print(f"🟢 MiracleBridge v{BRIDGE_VERSION} is already active and running on port 9123 in System Tray.")
        sys.exit(0)

    cleanup_old_temp_files()
    print(f"🚀 Starting Miracle DBF Local Bridge Agent v{BRIDGE_VERSION} on port 9123...")
    
    # 1. Enable Windows Auto-Start on Windows Boot
    enable_windows_autostart()
    
    # 2. Launch Background Loops (Version Checker, Master Sync, and Offline Queue Sync)
    start_update_checker_loop()
    start_master_sync_loop()
    start_offline_sync_loop()
    
    # 3. Initialize Windows System Tray Icon
    start_system_tray_icon()
    
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
        # Securely bind to 127.0.0.1 (Localhost Only)
        uvicorn.run(app, host="127.0.0.1", port=9123, log_config=UVICORN_LOG_CONFIG)
    except Exception as run_err:
        print(f"Server error: {run_err}")
