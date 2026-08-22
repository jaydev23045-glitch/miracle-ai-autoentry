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

def load_settings() -> dict:
    global _settings_cache, _settings_cache_time

    # ── Fast Path: Return cached settings if still fresh ──────────────────────
    with _settings_cache_lock:
        if _settings_cache and (time.monotonic() - _settings_cache_time) < _settings_cache_ttl:
            return _settings_cache.copy()

    default_settings = {
        "gemini_api_key": "",
        "miracle_base_path": "/Users/jaydevnakum/Work Place/WORK/APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank",
        "active_client_id": "CMP0003",
        "memory_path": "/Users/jaydevnakum/Work Place/WORK/APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/AI_Memory_Vault",
        "gemini_model": "gemini-1.5-flash",
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
    base_path = Path(base_path_str) if base_path_str else None
    if not base_path or not base_path.exists():
        has_cmp = False
        try:
            if parent_dir.exists():
                for item in parent_dir.iterdir():
                    if item.name.upper().startswith("CMP") and item.is_dir():
                        has_cmp = True
                        break
        except Exception:
            pass
        if has_cmp:
            default_settings["miracle_base_path"] = str(parent_dir)
            modified = True
            
    mem_path_str = default_settings.get("memory_path", "")
    mem_path = Path(mem_path_str) if mem_path_str else None
    if not mem_path or not mem_path.exists():
        fallback_mem = parent_dir / "AI_Memory_Vault"
        if fallback_mem.exists():
            default_settings["memory_path"] = str(fallback_mem)
            modified = True
        elif parent_dir.exists():
            try:
                fallback_mem.mkdir(parents=True, exist_ok=True)
                default_settings["memory_path"] = str(fallback_mem)
                modified = True
            except Exception:
                pass

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
    temp_file = Path(str(SETTINGS_FILE) + ".tmp")
    try:
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
        temp_file.replace(SETTINGS_FILE)
        with _settings_cache_lock:
            _settings_cache = settings.copy()
            _settings_cache_time = time.monotonic()
    except Exception as e:
        if temp_file.exists():
            temp_file.unlink()
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
            {"id": "CMP0003", "name": "Demo Client CMP0003"},
            {"id": "CMP0002", "name": "Nakum Digvijay Jayeshbhai"}
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


def validate_vouchers_pre_push(module: str, vouchers: List[Dict[str, Any]], client_path: str, year_folder: str, ledgers: List[Dict[str, Any]], pre_computed_bounds: dict = None) -> List[str]:
    """
    Validates vouchers before pushing to DBF using empirical Financial Year bounds.
    Returns a list of error message strings. If empty, validation passed.
    """
    errors = []
    
    # Build ledger lookups (pre-computed ONCE for entire batch - BN-8)
    ledger_names = {l['name'].strip().upper() for l in ledgers if isinstance(l, dict) and l.get('name')}
    ledger_codes = {l['code'].strip().upper() for l in ledgers if isinstance(l, dict) and l.get('code')}
    real_ledger_names_list = [l['name'].strip() for l in ledgers if isinstance(l, dict) and l.get('name')]
    
    for idx, v in enumerate(vouchers):
        row_label = f"Row #{idx + 1}"
        
        # 1. Date & Empirical FY Bounds Check
        v_date = v.get('date') or v.get('Date')
        if not v_date:
            errors.append(f"{row_label}: Missing date.")
        else:
            v_date_str = str(v_date).strip()
            if len(v_date_str) != 10 or v_date_str.count("-") != 2:
                errors.append(f"{row_label}: Invalid date format '{v_date_str}' (expected YYYY-MM-DD).")
            else:
                if pre_computed_bounds is not None:
                    res = resolve_year_folder_for_date_fast(pre_computed_bounds, v_date_str, client_path)
                else:
                    res = resolve_year_folder_for_date(client_path, v_date_str)
                resolved_folder = res["resolved_folder"]
                folder_exists = res["folder_exists"]
                fy_start = res["fy_start"]
                fy_end = res["fy_end"]
                
                if not folder_exists:
                    errors.append(
                        f"{row_label}: Date '{v_date_str}' belongs to Financial Year folder '{resolved_folder}' "
                        f"({fy_start} to {fy_end}), but directory '{resolved_folder}' does not exist in client folder "
                        f"'{os.path.basename(client_path)}'. Please open Miracle Accounting Software and create year {resolved_folder} first."
                    )
                elif not (fy_start <= v_date_str <= fy_end):
                    errors.append(
                        f"{row_label}: Date '{v_date_str}' is outside Financial Year bounds ({fy_start} to {fy_end} for {resolved_folder})."
                    )
                    
        # 2. Amount & Math check
        if module in ["Sales", "Purchases"]:
            bill_no = v.get('billNo') or v.get('bill_no')
            if not bill_no or str(bill_no).strip().upper() in ["NONE", "NAN", ""]:
                errors.append(f"{row_label}: Missing invoice number.")
                
            party_name = (v.get('party') or v.get('party_name') or "").strip()
            if not party_name or party_name.upper().startswith("UNKNOWN_PARTY:"):
                errors.append(f"{row_label}: Unmapped/Unknown party name '{party_name}'.")
            elif party_name.upper() not in ledger_names and party_name.upper() not in ledger_codes:
                is_auto_b2c = v.get('isB2C')
                is_auto_b2b = v.get('autoCreateB2B')
                if not (is_auto_b2c or is_auto_b2b):
                    # Auto-heal missing ledgers
                    gstin = v.get('gstin', '')
                    if gstin and len(str(gstin)) >= 10:
                        v['autoCreateB2B'] = True
                    else:
                        v['isB2C'] = True

            # Math check
            def to_float(val):
                if val is None:
                    return 0.0
                try:
                    s = str(val).replace("₹", "").replace(",", "").strip()
                    return float(s) if s else 0.0
                except:
                    return 0.0
            
            taxable = to_float(v.get('taxable'))
            cgst = to_float(v.get('cgst'))
            sgst = to_float(v.get('sgst'))
            igst = to_float(v.get('igst'))
            gst = to_float(v.get('gst'))
            discount = to_float(v.get('discount'))
            freight = to_float(v.get('freight'))
            tcs = to_float(v.get('tcs'))
            tds = to_float(v.get('tds'))
            total = to_float(v.get('total'))
            
            expected_gst = cgst + sgst + igst
            if expected_gst > 0 and gst > 0 and abs(expected_gst - gst) > 1.0:
                # Auto-heal: trust the sum of components
                v['gst'] = expected_gst
                gst = expected_gst
                
            actual_gst_for_math = max(expected_gst, gst)
            expected_total = round(taxable + actual_gst_for_math + freight + tcs - discount - tds, 2)
            
            if abs(expected_total - total) > 5.0:
                diff = round(total - expected_total, 2)
                # Auto-heal logic
                if actual_gst_for_math == 0.0 and diff > 0 and abs((taxable + diff) - total) <= 2.0:
                    # Missing GST case
                    v['gst'] = diff
                    # Also try to split it into CGST/SGST if intra-state? Just put in GST.
                elif diff < 0 and discount == 0.0:
                    # Overcharged expected, maybe there's a discount
                    v['discount'] = abs(diff)
                elif diff > 0 and freight == 0.0:
                    # Guard: only assign as freight if diff is NOT suspiciously close to the discount.
                    # If diff ≈ discount, it means the discount was already baked into taxable,
                    # and we would be creating a phantom "freight" that cancels the discount.
                    discount_proximity = abs(diff - discount)
                    if discount > 0 and discount_proximity < (discount * 0.05 + 1.0):
                        # Diff matches discount value — discount was double-counted, NOT freight. Ignore diff.
                        print(f"  ⚠️ [Ghost Freight Guard] Diff {diff:.2f} matches discount {discount:.2f}. Discount likely already in taxable. Skipping auto-freight.")
                    elif diff > 5.0:
                        # A real unexplained charge — assign to freight
                        v['freight'] = diff
                    else:
                        # Small rounding noise — ignore
                        pass
                else:
                    # If we can't cleanly auto-heal, throw error
                    errors.append(f"{row_label} (Bill {bill_no}): Mathematically unbalanced invoice. Expected Total: {expected_total:.2f}, Provided Total: {total:.2f} (diff: {abs(expected_total - total):.2f}).")

        elif module in ["Bank Statements", "Cash Entries"]:
            party_name = (v.get('party_name') or v.get('mapped_ledger') or v.get('party') or "").strip()
            
            # Hard fail: completely empty or unknown string
            if not party_name or party_name.upper().startswith("UNKNOWN_PARTY:"):
                errors.append(f"{row_label}: Transaction has an empty party or ledger name.")
            
            elif party_name.upper() not in ledger_names and party_name.upper() not in ledger_codes:
                import difflib
                
                # If explicit Suspense Account, auto-map to Suspense ledger in Miracle
                if party_name.upper() in ("SUSPENSE ACCOUNT", "SUSPENSE A/C"):
                    suspense_match = next((l['name'] for l in ledgers if 'SUSPENSE' in l['name'].upper()), 'Suspense Account')
                    v['mapped_ledger'] = suspense_match
                    v['party_name']    = suspense_match
                    v['party']         = suspense_match
                    v['group_hint']    = 'Suspense Account'
                    print(f"  ⚖️ [Accounting Foundation Rule] Suspense entry retained as '{suspense_match}'")
                else:
                    # Strategy 1: Fuzzy match against existing Miracle ledgers
                    close = difflib.get_close_matches(party_name, real_ledger_names_list, n=1, cutoff=0.70)
                    if close:
                        healed = close[0]
                        print(f"  🔗 [Accounting Heal] '{party_name}' → '{healed}' (fuzzy ledger match)")
                        v['mapped_ledger'] = healed
                        v['party_name']    = healed
                        v['party']         = healed
                    else:
                        # Strategy 2: Determine appropriate accounting group hint
                        tx_type = str(v.get('transaction_type', 'Payment')).strip().capitalize()
                        is_receipt = (tx_type == 'Receipt')
                        
                        GENERIC_EXPENSES = {
                            'TELEPHONE EXP', 'TELEPHONE EXPENSE', 'MOBILE EXP', 'ELECTRICITY EXP', 'ELECTRICITY EXPENSE',
                            'WATER EXPENSE', 'WATER EXP', 'GAS EXP', 'GAS EXPENSE', 'CUTTING EQUIPMENTS', 'CUTTING TOOLS EXP',
                            'REPAIR & MAINTENANCE', 'REPAIRS EXP', 'PRINTING & STATIONERY', 'STATIONERY EXP',
                            'ADVERTISEMENT EXP', 'ADVERTISING EXP', 'STAFF WELFARE', 'FOOD EXP', 'ENTERTAINMENT EXP',
                            'GST PAYABLE', 'TDS PAYABLE', 'INSURANCE EXP', 'INSURANCE EXPENSE', 'FUEL EXPENSE', 'PETROL-DIESEL EXPENSE',
                            'BANK CHARGES', 'BANK CHARGE', 'BANK FEE', 'BANK FEES', 'BANK COMM', 'BANK COMMISSION',
                            'BANK INTEREST', 'SMS CHARGES', 'SMS CHGS', 'SERVICE CHARGES', 'PROCESSING FEE',
                            'PROCESSING FEES', 'MDR CHARGES', 'MDR RECOVERY', 'RUPAY MDR', 'CARD CHARGES',
                            'POS CHARGES', 'MIN BAL', 'MINIMUM BALANCE', 'CHQ RET', 'CHEQUE RETURN', 'CHQ DEP RET',
                            'DEBIT CARD FEE', 'ANNUAL FEE', 'FOREX CHARGES', 'GST ON BANK', 'PENALTY', 'INTEREST PAID'
                        }
                        
                        is_expense_keyword = party_name.upper() in GENERIC_EXPENSES or any(kw in party_name.upper() for kw in ['BANK CHARGE', 'BANK FEE', 'BANK COMM', 'SMS CHARGE', 'MDR RCVRY', 'MDR CHARGE', 'PROCESSING FEE', 'SERVICE CHARGE'])
                        
                        if is_expense_keyword:
                            v['group_hint'] = 'Indirect Expenses'
                            v['mapped_ledger'] = party_name if party_name else 'Bank Charges'
                            v['party_name']    = party_name if party_name else 'Bank Charges'
                            v['party']         = party_name if party_name else 'Bank Charges'
                            print(f"  ⚖️ [Accounting Foundation Rule] Expense '{party_name}' classified under Indirect Expenses")
                        else:
                            # Genuine party name (vendor/customer/person) -> Sundry Debtors (Receipt) or Sundry Creditors (Payment)
                            group = 'Sundry Debtors' if is_receipt else 'Sundry Creditors'
                            v['group_hint'] = group
                            v['mapped_ledger'] = party_name
                            v['party_name']    = party_name
                            v['party']         = party_name
                            print(f"  ⚖️ [Accounting Foundation Rule] Party '{party_name}' classified under {group}")

                
            # ── CRITICAL DOUBLE-ENTRY ACCOUNTING NATURE GUARD ────────────────────────
            tx_type = str(v.get('transaction_type', 'Payment')).strip().capitalize()
            gh = str(v.get('group_hint') or '').upper()
            if tx_type == 'Payment' and any(bad in gh for bad in ['SALES ACCOUNTS', 'DIRECT INCOME', 'INDIRECT INCOME', 'TRADING ACCOUNT']):
                healed_group = 'Indirect Expenses' if 'INDIRECT' in gh else 'Direct Expenses'
                print(f"  ⚖️ [Auto-Heal Accounting Nature] {row_label}: Converted Payment from '{v.get('group_hint')}' to '{healed_group}'")
                v['group_hint'] = healed_group
            elif tx_type == 'Receipt' and any(bad in gh for bad in ['PURCHASE ACCOUNTS', 'DIRECT EXPENSES', 'INDIRECT EXPENSES', 'SUNDRY CREDITORS']):
                healed_group = 'Indirect Income' if 'INDIRECT' in gh else 'Direct Income'
                print(f"  ⚖️ [Auto-Heal Accounting Nature] {row_label}: Converted Receipt from '{v.get('group_hint')}' to '{healed_group}'")
                v['group_hint'] = healed_group

            amount = v.get('amount')
            try:
                s = str(amount).replace("₹", "").replace(",", "").strip()
                amt_val = float(s) if s else 0.0
                if amt_val <= 0:
                    errors.append(f"{row_label}: Transaction amount must be positive (got {amount}).")
            except:
                errors.append(f"{row_label}: Invalid amount value '{amount}'.")

    return errors
