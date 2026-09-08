import os
import json
import re
import threading
import time
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

client_locks = {}
client_locks_lock = threading.Lock()

# ── Settings In-Process Cache ─────────────────────────────────────────────────
_settings_cache: dict = {}
_settings_cache_time: float = 0.0
_settings_cache_ttl: float = 30.0          # seconds — enough for any request burst
_settings_cache_lock = threading.Lock()

def get_client_lock(client_id: str) -> threading.Lock:
    with client_locks_lock:
        if client_id not in client_locks:
            client_locks[client_id] = threading.Lock()
        return client_locks[client_id]

SETTINGS_FILE = Path(__file__).resolve().parents[1] / "settings.json"

class SystemSettings(BaseModel):
    gemini_api_key: str
    miracle_base_path: str
    active_client_id: str
    memory_path: str
    gemini_model: str = "gemini-3.1-flash-lite"
    sales_prefix: str = "SS,SS"
    purchase_prefix: str = "PP,PP"
    sales_setup_id: int = 5
    purchase_setup_id: int = 6
    sales_series: str = ""
    auto_create_b2b: bool = True
    auto_create_b2c: bool = True
    is_paid_api_key: bool = False
    active_year_folder: str = ""
    backup_path: str = ""
def clean_api_key(key: str) -> str:
    if not key:
        return ""
    key = key.strip()
    match = re.search(r'(AIzaSy[A-Za-z0-9_-]+|AQ\.[A-Za-z0-9_-]+)', key)
    if match:
        return match.group(1)
    
    tokens = key.split()
    for token in reversed(tokens):
        token_clean = token.strip("[],:\"'")
        if token_clean.startswith("AIzaSy") or token_clean.startswith("AQ."):
            return token_clean
    return key

import logging

def _load_local_env_files():
    """Reads PROJECT.env or .env from project root or backend dir if present."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(os.path.dirname(base_dir))
    backend_dir = os.path.dirname(base_dir)
    env_paths = [
        os.path.join(root_dir, "PROJECT.env"),
        os.path.join(backend_dir, "PROJECT.env"),
        os.path.join(root_dir, ".env"),
        os.path.join(backend_dir, ".env"),
    ]
    for ep in env_paths:
        if os.path.exists(ep):
            try:
                with open(ep, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("'\"")
                            if k and v and (k not in os.environ or not os.environ[k] or "AIzaSy..." in os.environ[k]):
                                os.environ[k] = v
            except Exception as e:
                logging.debug(f"Could not parse env file {ep}: {e}")

def get_gemini_api_key_pool(settings: dict | None = None) -> list:
    """
    Gathers and sanitizes all available Gemini API keys from environment variables
    (GEMINI_API_KEY, GEMINI_API_KEY_2 .. GEMINI_API_KEY_10), PROJECT.env/.env files, and settings.json.
    Returns a deduplicated list of clean API keys.
    """
    _load_local_env_files()
    keys = []
    
    # 1. Environment Variables (Render / Local PROJECT.env / System)
    env_vars = ["GEMINI_API_KEY", "GEMINI_API_KEY_1"] + [f"GEMINI_API_KEY_{i}" for i in range(2, 11)]
    for var in env_vars:
        val = os.getenv(var, "").strip()
        if val:
            for raw_k in re.split(r'[,;\s]+', val):
                c_key = clean_api_key(raw_k)
                if c_key and c_key not in keys:
                    keys.append(c_key)
                    
    # 2. Configured settings keys
    if settings and isinstance(settings, dict):
        raw_setting = settings.get("gemini_api_key", "")
        if raw_setting:
            for raw_k in re.split(r'[,;\s]+', raw_setting):
                c_key = clean_api_key(raw_k)
                if c_key and c_key not in keys:
                    keys.append(c_key)
                    
    return keys

def load_settings() -> dict:
    global _settings_cache, _settings_cache_time

    # ── Fast Path: Return cached settings if still fresh ──────────────────────
    with _settings_cache_lock:
        if _settings_cache and (time.monotonic() - _settings_cache_time) < _settings_cache_ttl:
            return _settings_cache.copy()

    default_settings = {
        "gemini_api_key": "",
        "miracle_base_path": "C:\\Miracle",
        "active_client_id": "CMP0001",
        "memory_path": "C:\\Miracle\\AI_Memory_Vault",
        "gemini_model": "gemini-3.1-flash-lite",
        "sales_prefix": "SS,SS",
        "purchase_prefix": "PP,PP",
        "sales_setup_id": 5,
        "purchase_setup_id": 6,
        "sales_series": "",
        "auto_create_b2b": True,
        "auto_create_b2c": True,
        "is_paid_api_key": False,
        "active_year_folder": "",
        "backup_path": ""
    }
    backend_dir = Path(__file__).resolve().parent.parent
    parent_dir = backend_dir.parent
    modified = False

    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                if "gemini_api_key" in saved:
                    original_key = saved["gemini_api_key"]
                    cleaned_key = clean_api_key(original_key)
                    if cleaned_key != original_key:
                        saved["gemini_api_key"] = cleaned_key
                        modified = True
                default_settings.update(saved)
        except Exception as e:
            print(f"Error reading settings: {e}")

    base_path_str = default_settings.get("miracle_base_path", "")
    if sys.platform == "win32" and (not base_path_str or "/Users/" in base_path_str or "/home/" in base_path_str):
        default_settings["miracle_base_path"] = "C:\\Miracle"
        modified = True
            
    mem_path_str = default_settings.get("memory_path", "")
    if sys.platform == "win32" and (not mem_path_str or "/Users/" in mem_path_str or "/home/" in mem_path_str):
        default_settings["memory_path"] = "C:\\Miracle\\AI_Memory_Vault"
        modified = True

    curr_base_path_str = default_settings.get("miracle_base_path", "")
    curr_base_path = Path(curr_base_path_str) if curr_base_path_str else None
    if curr_base_path and curr_base_path.exists():
        active_client = default_settings.get("active_client_id", "")
        active_client_path = curr_base_path / active_client if active_client else None
        if not active_client_path or not active_client_path.exists():
            valid_clients = []
            try:
                for item in curr_base_path.iterdir():
                    if item.name.upper().startswith("CMP") and item.is_dir():
                        valid_clients.append(item.name)
            except Exception:
                pass
            if valid_clients:
                default_settings["active_client_id"] = sorted(valid_clients)[0]
                modified = True

    if modified:
        save_settings_to_file(default_settings)

    with _settings_cache_lock:
        _settings_cache = default_settings
        _settings_cache_time = time.monotonic()

    return default_settings

def save_settings_to_file(settings: dict):
    global _settings_cache, _settings_cache_time
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
        with _settings_cache_lock:
            _settings_cache = settings.copy()
            _settings_cache_time = time.monotonic()
        invalidate_client_discovery_cache()
    except Exception as e:
        print(f"Error saving settings: {e}")

def get_company_name(client_path: str) -> str:
    from dbfread import DBF
    c_path = Path(client_path)
    mei_path = c_path / "rkcmpmei.dbf"
    if not g_exists_resilient(mei_path):
        mei_path = c_path / "RKCMPMEI.DBF"
    
    name = ""
    if g_exists_resilient(mei_path):
        try:
            db = DBF(str(mei_path))
            for r in db:
                name = str(r.get('MEIF03', '')).strip()
                break
        except Exception:
            pass
            
    if not name:
        mm_path = c_path / "rkcmpmm.dbf"
        if not g_exists_resilient(mm_path):
            mm_path = c_path / "RKCMPMM.DBF"
        if g_exists_resilient(mm_path):
            try:
                db = DBF(str(mm_path))
                for r in db:
                    if r.get('FIELD01') == 'CMP_LINFO':
                        name = str(r.get('FIELD02', '')).split('~')[0].strip()
                        break
            except Exception:
                pass
    return name or ""

def g_exists_resilient(path: Path) -> bool:
    try:
        return path.exists()
    except Exception:
        return False

# ── Discovery Cache ────────────────────────────────────────────────────────────
_DISCOVER_CLIENTS_CACHE: Dict[str, Any] = {}
_DISCOVER_CLIENTS_LOCK = threading.Lock()
_DISCOVER_CLIENTS_TTL = 60.0

def discover_clients(base_path: str) -> List[Dict[str, str]]:
    now = time.monotonic()
    b_path_str = str(base_path or "").strip()
    
    with _DISCOVER_CLIENTS_LOCK:
        cached = _DISCOVER_CLIENTS_CACHE.get(b_path_str)
        if cached and (now - cached[0]) < _DISCOVER_CLIENTS_TTL:
            return [c.copy() for c in cached[1]]
            
    clients = []
    b_path = Path(b_path_str)
    if b_path.exists():
        try:
            for item in b_path.iterdir():
                if item.is_dir() and item.name.upper().startswith("CMP"):
                    name = get_company_name(str(item))
                    clients.append({"id": item.name, "name": name or "Unknown Company"})
        except Exception as e:
            print(f"Error discovering clients: {e}")
    if not clients:
        clients = [
            {"id": "CMP0001", "name": "Miracle Client CMP0001"},
            {"id": "CMP0002", "name": "Miracle Client CMP0002"}
        ]
    result = sorted(clients, key=lambda x: x["id"])
    
    with _DISCOVER_CLIENTS_LOCK:
        _DISCOVER_CLIENTS_CACHE[b_path_str] = (now, result)
        
    return [c.copy() for c in result]

def invalidate_client_discovery_cache():
    with _DISCOVER_CLIENTS_LOCK:
        _DISCOVER_CLIENTS_CACHE.clear()


def resolve_year_folder_for_date(client_path: str, date_str: str) -> dict:
    """
    Resolves the physical Miracle year folder (e.g. 'YR25', 'YR26', 'YR27') for a given ISO date string.
    Uses empirical bounds discovered from DBFs in client_path.
    
    Returns dict:
      {
         "resolved_folder": "YR26",
         "folder_exists": True,
         "fy_start": "2026-04-01",
         "fy_end": "2027-03-31",
         "reason": "empirical_match"
      }
    """
    clean_date = str(date_str).strip()[:10]
    
    # 1. Ask handler for empirical bounds across all year folders in client_path
    if client_path and os.path.exists(client_path):
        try:
            from dbf_handler import MiracleDBFHandler
            handler = MiracleDBFHandler(client_path)
            all_bounds = handler.get_all_year_folder_bounds()
            
            # Check if clean_date falls into any existing folder's bounds
            for yr_folder, b_info in all_bounds.items():
                f_start = b_info.get("fy_start")
                f_end = b_info.get("fy_end")
                if f_start and f_end and (f_start <= clean_date <= f_end):
                    yr_dir = os.path.join(client_path, yr_folder)
                    exists = os.path.exists(yr_dir)
                    return {
                        "resolved_folder": yr_folder,
                        "folder_exists": exists,
                        "fy_start": f_start,
                        "fy_end": f_end,
                        "reason": "empirical_match"
                    }
        except Exception as e:
            print(f"⚠️ Error resolving empirical year folder for date '{date_str}': {e}")
            
    # 2. Fallback calculation if folder bounds match wasn't found
    try:
        from datetime import datetime as _dt
        dt_obj = _dt.strptime(clean_date, "%Y-%m-%d").date()
        if dt_obj.month >= 4:
            fy_start_yr = dt_obj.year
            fy_end_yr = dt_obj.year + 1
        else:
            fy_start_yr = dt_obj.year - 1
            fy_end_yr = dt_obj.year
            
        calculated_yr = f"YR{str(fy_start_yr)[-2:]}"
        yr_dir = os.path.join(client_path, calculated_yr) if client_path else ""
        exists = bool(yr_dir and os.path.exists(yr_dir))
        
        # If calculated year folder doesn't exist, check for closest existing folder
        if not exists and client_path and os.path.exists(client_path):
            try:
                for d in os.listdir(client_path):
                    if d.upper().startswith("YR") and os.path.isdir(os.path.join(client_path, d)):
                        calculated_yr = d.upper()
                        exists = True
                        break
            except Exception:
                pass
        
        return {
            "resolved_folder": calculated_yr,
            "folder_exists": exists,
            "fy_start": f"{fy_start_yr}-04-01",
            "fy_end": f"{fy_end_yr}-03-31",
            "reason": "fallback_calculation"
        }
    except Exception:
        return {
            "resolved_folder": "YR26",
            "folder_exists": False,
            "fy_start": "2025-04-01",
            "fy_end": "2026-03-31",
            "reason": "default_error_fallback"
        }


def resolve_year_folder_for_date_fast(bounds_map: dict, date_str: str, client_path: str = "") -> dict:
    """
    Fast O(1) version of resolve_year_folder_for_date().
    Accepts pre-computed bounds_map (from handler.get_all_year_folder_bounds())
    instead of spawning a MiracleDBFHandler internally.
    """
    clean_date = str(date_str).strip()[:10]
    
    # 1. Check against pre-computed bounds (zero disk I/O)
    if bounds_map:
        for yr_folder, b_info in bounds_map.items():
            f_start = b_info.get("fy_start")
            f_end = b_info.get("fy_end")
            if f_start and f_end and (f_start <= clean_date <= f_end):
                yr_dir = os.path.join(client_path, yr_folder) if client_path else ""
                exists = bool(yr_dir and os.path.exists(yr_dir))
                return {
                    "resolved_folder": yr_folder,
                    "folder_exists": exists,
                    "fy_start": f_start,
                    "fy_end": f_end,
                    "reason": "empirical_match"
                }

    # 2. Fallback calculation if folder bounds match wasn't found
    try:
        from datetime import datetime as _dt
        dt_obj = _dt.strptime(clean_date, "%Y-%m-%d").date()
        if dt_obj.month >= 4:
            fy_start_yr = dt_obj.year
            fy_end_yr = dt_obj.year + 1
        else:
            fy_start_yr = dt_obj.year - 1
            fy_end_yr = dt_obj.year
            
        calculated_yr = f"YR{str(fy_start_yr)[-2:]}"
        yr_dir = os.path.join(client_path, calculated_yr) if client_path else ""
        exists = bool(yr_dir and os.path.exists(yr_dir))
        
        # If calculated year folder doesn't exist, check for closest existing folder
        if not exists and bounds_map:
            closest = max(bounds_map.keys())
            yr_dir = os.path.join(client_path, closest) if client_path else ""
            exists = bool(yr_dir and os.path.exists(yr_dir))
            if exists:
                calculated_yr = closest
        elif not exists and client_path and os.path.exists(client_path):
            try:
                for d in os.listdir(client_path):
                    if d.upper().startswith("YR") and os.path.isdir(os.path.join(client_path, d)):
                        calculated_yr = d.upper()
                        exists = True
                        break
            except Exception:
                pass
        
        return {
            "resolved_folder": calculated_yr,
            "folder_exists": exists,
            "fy_start": f"{fy_start_yr}-04-01",
            "fy_end": f"{fy_end_yr}-03-31",
            "reason": "fallback_calculation"
        }
    except Exception:
        return {
            "resolved_folder": "YR26",
            "folder_exists": False,
            "fy_start": "2025-04-01",
            "fy_end": "2026-03-31",
            "reason": "default_error_fallback"
        }


from core.voucher_validator import validate_vouchers_pre_push
