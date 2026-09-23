import os
import json
import re
import threading
import time
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
    gemini_api_key: str = ""
    miracle_base_path: str = "C:\\Miracle"
    active_client_id: str = "CMP0001"
    memory_path: str = "C:\\Miracle\\AI_Memory_Vault"
    gemini_model: str = "gemini-3.1-flash-lite"
    sales_prefix: str = "SS,SS"
    purchase_prefix: str = "PP,PP"
    sales_setup_id: int = 5
    purchase_setup_id: int = 6
    sales_series: str = ""
    auto_create_b2b: bool = True
    auto_create_b2c: bool = True
    is_paid_api_key: bool = False
    active_year_folder: Optional[str] = ""
    backup_path: Optional[str] = ""

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

def get_company_name(client_path: str) -> str:
    from dbfread import DBF
    c_path = Path(client_path)
    mei_path = c_path / "rkcmpmei.dbf"
    if not mei_path.exists():
        mei_path = c_path / "RKCMPMEI.DBF"
    
    name = ""
    if mei_path.exists():
        try:
            db = DBF(str(mei_path))
            for r in db:
                name = str(r.get('MEIF03', '')).strip()
                break
        except Exception:
            pass
            
    if not name:
        mm_path = c_path / "rkcmpmm.dbf"
        if not mm_path.exists():
            mm_path = c_path / "RKCMPMM.DBF"
        if mm_path.exists():
            try:
                db = DBF(str(mm_path))
                for r in db:
                    if r.get('FIELD01') == 'CMP_LINFO':
                        name = str(r.get('FIELD02', '')).split('~')[0].strip()
                        break
            except Exception:
                pass
    return name or ""
