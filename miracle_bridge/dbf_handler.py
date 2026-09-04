import contextlib
import os
import threading
import time
from datetime import date
import re
from dbfread import DBF

class MiracleDBFHandler:
    _CROSS_YEAR_CACHE = {}  # {(client_path, active_year_folder): (timestamp, ledgers_list)}
    _CROSS_YEAR_CACHE_LOCK = threading.Lock()
    _CROSS_YEAR_CACHE_TTL = 60.0  # 60 seconds TTL

    @classmethod
    def clear_cross_year_cache(cls, client_path: str = None):
        with cls._CROSS_YEAR_CACHE_LOCK:
            if client_path:
                norm_target = os.path.normpath(client_path.replace("\\", "/")).rstrip("/").upper()
                keys_to_del = [k for k in cls._CROSS_YEAR_CACHE if os.path.normpath(str(k[0]).replace("\\", "/")).rstrip("/").upper() == norm_target]
                for k in keys_to_del:
                    cls._CROSS_YEAR_CACHE.pop(k, None)
            else:
                cls._CROSS_YEAR_CACHE.clear()

    def __init__(self, client_path: str, active_client_id: str = None):
        if active_client_id and isinstance(active_client_id, str):
            if not client_path.endswith(active_client_id):
                full_path = os.path.join(client_path, active_client_id)
                if os.path.exists(full_path):
                    client_path = full_path
        self.client_path = client_path
        self.audit_report = {
            "injected": 0,
            "duplicates": 0,
            "anomalies": 0,
            "missing_parties": 0,
            "messages": [],
            "duplicate_details": []  # Full details for each skipped duplicate
        }
        if not os.path.exists(client_path):
            raise FileNotFoundError(f"Client path {client_path} does not exist.")

    def _parse_float(self, val) -> float:
        """Safely parses float numbers, stripping commas, currency symbols, and spaces."""
        try:
            from core.utils import parse_currency
            return parse_currency(val)
        except Exception:
            try:
                from backend.core.utils import parse_currency
                return parse_currency(val)
            except Exception:
                if val is None:
                    return 0.0
                if isinstance(val, (int, float)):
                    return float(val)
                s = str(val).replace(',', '').replace('₹', '').replace('$', '').strip()
                try:
                    return float(s)
                except Exception:
                    return 0.0


    def _write_raw_char_field(self, record, field_name: str, value: str, encoding: str = 'cp1252'):
        """Writes a character field directly to the record byte buffer to preserve exact padding/alignment."""
        from array import array
        field_name_upper = field_name.upper()
        if field_name_upper in record._meta:
            fielddef = record._meta[field_name_upper]
            start = fielddef[1]
            length = fielddef[2]
            
            # Encode string and pad/truncate to exact length
            encoded_val = value.encode(encoding, errors='replace')
            if len(encoded_val) < length:
                encoded_val = encoded_val.ljust(length, b' ')
            else:
                encoded_val = encoded_val[:length]
                
            record._data[start:start+length] = array('B', encoded_val)
            record._dirty = True

    def _append_record(self, table, rec_dict: dict, raw_fields: dict | None = None):
        """Appends a record to a dbf table and optionally writes raw unstripped bytes to specific fields."""
        cleaned = self.clean_record_dict(rec_dict, table=table)
        table.append(cleaned)
        rec = table[-1]
        if raw_fields:
            for f_name, f_val in raw_fields.items():
                self._write_raw_char_field(rec, f_name, f_val)
            rec._write()
        return rec

    @staticmethod
    def fit_dbf_str(val: str, max_len: int) -> str:
        """Safely converts val to string and trims to max_len bytes to prevent DBF field overflow."""
        if not val:
            return ""
        s_val = str(val).strip()
        return s_val[:max_len]

    @staticmethod
    def clean_dbf_string(val: str, encoding: str = 'cp1252') -> str:
        if not isinstance(val, str):
            return val
        
        # Map common Cyrillic/Greek/unencodeable look-alikes to Latin letters
        lookalikes = {
            '\u0410': 'A', # Cyrillic Capital A
            '\u0430': 'a', # Cyrillic Small a
            '\u0412': 'B', # Cyrillic Capital Ve (B)
            '\u0421': 'C', # Cyrillic Capital Es (C)
            '\u0441': 'c', # Cyrillic Small Es (c)
            '\u0415': 'E', # Cyrillic Capital Ie (E)
            '\u0435': 'e', # Cyrillic Small Ie (e)
            '\u041d': 'H', # Cyrillic Capital En (H)
            '\u041a': 'K', # Cyrillic Capital Ka (K)
            '\u043a': 'k', # Cyrillic Small Ka (k)
            '\u041c': 'M', # Cyrillic Capital Em (M)
            '\u043c': 'm', # Cyrillic Small Em (m)
            '\u041e': 'O', # Cyrillic Capital O (O)
            '\u043e': 'o', # Cyrillic Small O (o)
            '\u0420': 'P', # Cyrillic Capital Er (P)
            '\u0440': 'p', # Cyrillic Small Er (p)
            '\u0422': 'T', # Cyrillic Capital Te (T)
            '\u0442': 't', # Cyrillic Small Te (t)
            '\u0425': 'X', # Cyrillic Capital Ha (X)
            '\u0445': 'x', # Cyrillic Small Ha (x)
            '\u0443': 'y', # Cyrillic Small U (y)
            '\u00a0': ' ', # Non-breaking space
        }
        
        # Replace characters
        chars = [lookalikes.get(c, c) for c in val]
        cleaned = "".join(chars)
        
        try:
            return cleaned.encode(encoding, errors='replace').decode(encoding)
        except Exception:
            try:
                return cleaned.encode('ascii', errors='ignore').decode('ascii')
            except Exception:
                return val

    @staticmethod
    def clean_record_dict(rec_dict: dict, encoding: str = 'cp1252', table=None) -> dict:
        cleaned = {}
        valid_keys = None
        field_lengths = {}
        if table is not None:
            valid_keys = {k.lower() for k in table.field_names}
            try:
                if hasattr(table, 'field_info'):
                    for fn in table.field_names:
                        info = table.field_info(fn)
                        # info tuple is (type_code, length, decimals, cls)
                        # Skip memo fields (type code 77 / 'M') from size limits
                        if info[0] not in (77, 'M', 'm'):
                            field_lengths[fn.lower()] = info[1]
            except Exception:
                pass
            
        for k, v in rec_dict.items():
            k_lower = k.lower()
            if valid_keys is not None and k_lower not in valid_keys:
                continue
            if isinstance(v, str):
                s_val = MiracleDBFHandler.clean_dbf_string(v, encoding)
                # Auto-truncate if string exceeds DBF character field length limit
                if k_lower in field_lengths:
                    f_len = field_lengths[k_lower]
                    if len(s_val) > f_len:
                        print(f"⚠️ Auto-truncating DBF field '{k}' from {len(s_val)} to max DBF width {f_len} (Value: '{s_val[:f_len]}')")
                        s_val = s_val[:f_len]
                cleaned[k] = s_val
            elif isinstance(v, dict):
                cleaned[k] = MiracleDBFHandler.clean_record_dict(v, encoding, table)
            else:
                cleaned[k] = v
        return cleaned

    def get_company_name(self) -> str:
        """Reads RKCMPMEI.DBF or RKCMPMM.DBF to retrieve official Miracle company name."""
        c_path = self.client_path
        if not c_path or not os.path.exists(c_path):
            return ""

        # Method 1: RKCMPMEI.DBF (MEIF03 field)
        mei_path = os.path.join(c_path, 'RKCMPMEI.DBF')
        if not os.path.exists(mei_path):
            mei_path = os.path.join(c_path, 'rkcmpmei.dbf')
        if os.path.exists(mei_path):
            try:
                from dbfread import DBF
                table = DBF(mei_path, encoding='latin1', ignore_missing_memofile=True)
                for r in table:
                    val = str(r.get('MEIF03', '') or r.get('meif03', '')).strip()
                    if val:
                        return val
            except Exception:
                pass

        # Method 2: RKCMPMM.DBF (FIELD01 == 'CMP_LINFO', FIELD02 first segment)
        mm_path = os.path.join(c_path, 'RKCMPMM.DBF')
        if not os.path.exists(mm_path):
            mm_path = os.path.join(c_path, 'rkcmpmm.dbf')
        if os.path.exists(mm_path):
            try:
                from dbfread import DBF
                table = DBF(mm_path, encoding='latin1', ignore_missing_memofile=True)
                for r in table:
                    f01 = str(r.get('FIELD01', '')).strip()
                    if f01 == 'CMP_LINFO':
                        val = str(r.get('FIELD02', '')).split('~')[0].strip()
                        if val:
                            return val
            except Exception:
                pass

        # Method 3: RKCMPM98.DBF (FIELD01 == '_COMPNAME')
        m98_path = os.path.join(c_path, 'RKCMPM98.DBF')
        if not os.path.exists(m98_path):
            m98_path = os.path.join(c_path, 'rkcmpm98.dbf')
        if os.path.exists(m98_path):
            try:
                import dbf
                with self.safe_cdx_context(m98_path):
                    table = dbf.Table(m98_path)
                    table.open(mode=dbf.READ_ONLY)
                    for r in table:
                        if not dbf.is_deleted(r):
                            f01 = str(r['FIELD01']).strip()
                            if f01 in ('_COMPNAME', '_COMPANY', '_NAME'):
                                val = str(r['FIELD02']).strip()
                                table.close()
                                if val:
                                    return val
                    table.close()
            except Exception:
                pass

        return ""

    def get_company_state_code(self) -> str:
        """Reads RKCMPM98.DBF to retrieve the company's own GST state code digits (e.g. '27')."""
        import dbf
        m98_path = os.path.join(self.client_path, 'RKCMPM98.DBF')
        if not os.path.exists(m98_path):
            m98_path = os.path.join(self.client_path, 'rkcmpm98.dbf')
        if not os.path.exists(m98_path):
            return '24'  # default fallback if table missing
            
        try:
            with self.safe_cdx_context(m98_path):
                table = dbf.Table(m98_path)
                table.open(mode=dbf.READ_ONLY)
                gstin = ""
                for r in table:
                    if not dbf.is_deleted(r):
                        f01 = str(r['FIELD01']).strip()
                        if f01 == '_GSTINNO':
                            gstin = str(r['FIELD02']).strip()
                            break
                table.close()
                if gstin and len(gstin) >= 2 and gstin[:2].isdigit():
                    return gstin[:2]
        except Exception as e:
            print(f"Error reading company state code from DBF: {e}")
            
        return '24'  # default fallback

    def get_available_year_folders(self) -> list:
        """
        Returns all valid YRxx year folders for this client with metadata.
        Each entry: { 'name': 'YR26', 'has_transactions': True/False, 'is_valid': True/False }
        A folder is 'valid' if it contains the critical rkacct41.dbf transaction table.
        """
        result = []
        if not os.path.exists(self.client_path):
            return result
        try:
            for item in sorted(os.listdir(self.client_path), reverse=True):
                full_path = os.path.join(self.client_path, item)
                if not os.path.isdir(full_path):
                    continue
                    
                is_yr_match = bool(re.match(r'^YR\d+$', item, re.IGNORECASE) or re.search(r'F\.Y\.\s*\d+', item, re.IGNORECASE))
                t41_lower = os.path.join(full_path, 'rkacct41.dbf')
                t41_upper = os.path.join(full_path, 'RKACCT41.DBF')
                t01_lower = os.path.join(full_path, 'rkacct01.dbf')
                t01_upper = os.path.join(full_path, 'RKACCT01.DBF')
                
                has_t41 = os.path.exists(t41_lower) or os.path.exists(t41_upper)
                has_t01 = os.path.exists(t01_lower) or os.path.exists(t01_upper)
                
                if is_yr_match or has_t41 or has_t01:
                    yr = item.upper()
                    is_valid = has_t41 and has_t01
                    t41_size = 0
                    for p in [t41_lower, t41_upper]:
                        if os.path.exists(p):
                            t41_size = os.path.getsize(p)
                            break
                    has_transactions = t41_size > 2048
                    
                    result.append({
                        'name': yr,
                        'has_transactions': has_transactions,
                        'is_valid': is_valid,
                        't41_size': t41_size
                    })
        except Exception as e:
            print(f"Error listing year folders in {self.client_path}: {e}")
        return result

    def get_latest_year_folder(self) -> str:
        """
        Finds the best financial year folder (e.g. YR26) in the client directory.
        
        SMART LOGIC (not just alphabetical):
        1. Try to find the latest year that has the critical rkacct41.dbf file present.
        2. If no folder has the file, fall back to the alphabetically latest folder.
        
        This prevents the issue where Miracle creates a new empty YR27 folder
        and our code blindly picks it, causing data to be written to the wrong year.
        """
        if not os.path.exists(self.client_path):
            return 'YR26'
        
        folders = self.get_available_year_folders()
        
        if not folders:
            return 'YR26'
        
        # Priority 1: latest folder that has BOTH critical files (rkacct41 + rkacct01)
        valid_folders = [f for f in folders if f['is_valid']]
        if valid_folders:
            # Return the latest valid one (list is already sorted alphabetically)
            return valid_folders[-1]['name']
        
        # Priority 2: latest folder with just rkacct41 (partial)
        t41_folders = [f for f in folders if f['t41_size'] > 0]
        if t41_folders:
            return t41_folders[-1]['name']
        
        # Fallback: just return the alphabetically latest folder
        return folders[-1]['name']

    def get_all_year_folder_bounds(self) -> dict:
        """Returns a dict mapping year folder names (e.g. 'YR26') to financial year start/end dates."""
        available = self.get_available_year_folders()
        bounds = {}
        for yinfo in available:
            y_name = yinfo['name']
            try:
                yr_num = int(re.sub(r'[^0-9]', '', y_name))
                full_yr = 2000 + yr_num if yr_num < 100 else yr_num
                bounds[y_name] = {
                    "fy_start": f"{full_yr}-04-01",
                    "fy_end": f"{full_yr + 1}-03-31"
                }
            except Exception:
                bounds[y_name] = {
                    "fy_start": "",
                    "fy_end": ""
                }
        return bounds

    def _extract_gst_from_name(self, name: str) -> float | None:
        """
        Regex helper to extract explicit GST rate from a product name.
        E.g., "footwear Gst 0" -> 0.0, "FOOTWEAR GST 5%" -> 5.0, "Footwear Gst 18%" -> 18.0.
        """
        if not name:
            return None
        match = re.search(r'GST\s*(\d{1,2})\s*%?', name.strip(), re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except:
                pass
        return None

    def _resolve_charge_slots(self, year_folder: str | None = None, module: str = "Sales") -> dict:
        """
        Dynamically resolves database fields for additional charges (discount, freight, TCS, TDS, round_off)
        by querying the RKYRM45.DBF setup table for the active year.
        
        Returns a dict mapping charge keys to their resolved DBF slot configurations.
        """
        if not year_folder:
            year_folder = self.get_latest_year_folder()
            
        mod_prefix = "SS" if module.lower() == "sales" else "PP"
        
        yrm45_path = self._get_table_path('RKYRM45.DBF', year_folder)
        if not os.path.exists(yrm45_path):
            yrm45_path = self._get_table_path('rkyrm45.dbf', year_folder)
            
        resolved = {
            "discount": None,
            "freight": None,
            "tcs": None,
            "tds": None,
            "round_off": None
        }
        
        # Default legacy hardcoded fallbacks
        fallbacks = {
            "discount": "VAS00095",
            "freight": "VAS00097",
            "tcs": "VAS00098",
            "tds": "VAS00100",
            "round_off": "VAS00099"
        }
        
        if os.path.exists(yrm45_path):
            try:
                from dbfread import DBF
                table = DBF(yrm45_path, load=True, encoding='cp1252')
                for r in table:
                    f21 = str(r.get('FIELD21', '')).strip().upper()
                    f22 = str(r.get('FIELD22', '')).strip().upper()
                    if mod_prefix not in (f21, f22):
                        continue
                        
                    name = str(r.get('FIELD02', '')).strip().lower()
                    slot_val = str(r.get('FIELD54', '')).strip().upper()
                    ledger_code = str(r.get('FIELD04', '')).strip()
                    
                    if not slot_val:
                        continue
                        
                    resolved_type = None
                    if "discount" in name:
                        resolved_type = "discount"
                    elif any(kw in name for kw in ["freight", "transport", "packing", "forwarding", "loading"]):
                        resolved_type = "freight"
                    elif "tcs" in name:
                        resolved_type = "tcs"
                    elif "tds" in name:
                        resolved_type = "tds"
                    elif "round" in name or "kasar" in name:
                        resolved_type = "round_off"
                        
                    if resolved_type and not resolved[resolved_type]:
                        resolved[resolved_type] = {
                            "key": slot_val,
                            "is_dynamic": bool(re.match(r'^\d+$', slot_val)), # e.g. "00000001"
                            "ledger_code": ledger_code,
                            "name": r.get('FIELD02', '')
                        }
            except Exception as e:
                print(f"⚠️ [Resolver] Error reading RKYRM45: {e}")
                
        # Fill in missing ones using fallbacks
        for k, v in fallbacks.items():
            if not resolved[k]:
                resolved[k] = {
                    "key": v,
                    "is_dynamic": False,
                    "ledger_code": "",
                    "name": k.upper()
                }
                
        return resolved

    def _get_table_path(self, table_name: str, year_folder: str | None = None) -> str:
        """Constructs the full path to a DBF file for a given client and year."""

        if not year_folder:
            year_folder = self.get_latest_year_folder()
        if os.path.isabs(year_folder) or (self.client_path and self.client_path in year_folder):
            return os.path.join(year_folder, table_name)
        return os.path.join(self.client_path, year_folder, table_name)

    def read_vouchers(self, year_folder: str | None = None, limit: int = 100):
        """Reads the voucher headers from rkacct41.dbf"""

        if not year_folder:
            year_folder = self.get_latest_year_folder()
            
        file_path = self._get_table_path('RKACCT41.DBF', year_folder)
        if not os.path.exists(file_path):
            file_path = self._get_table_path('rkacct41.dbf', year_folder)
            if not os.path.exists(file_path):
                 raise FileNotFoundError(f"Voucher table not found at {file_path}")

        records = []
        try:
            table = DBF(file_path, load=True, encoding='cp1252')
            for idx, record in enumerate(table):
                if idx >= limit:
                    break
                records.append(dict(record))
            return records
        except Exception as e:
            raise Exception(f"Failed to read {file_path}: {str(e)}")

    def get_all_ledgers(self, year_folder: str | None = None) -> list:
        """Helper alias for reading classified ledgers across all years."""
        return self.read_ledgers_all_years(active_year_folder=year_folder)

    def get_products(self, year_folder: str | None = None) -> list:
        """Helper alias for reading products."""
        if year_folder:
            return self.read_products(year_folder=year_folder)
        return self.read_products_all_years()

    def read_ledgers(self, year_folder: str | None = None):
        """Reads and classifies all account ledgers from Miracle DBFs."""

        if not year_folder:
            year_folder = self.get_latest_year_folder()
            
        m01_path = self._get_table_path('RKACCM01.DBF', year_folder)
        m02_path = self._get_table_path('RKACCM02.DBF', year_folder)
        m11_path = self._get_table_path('RKACCM11.DBF', year_folder)
        
        # Check case variation
        if not os.path.exists(m01_path): m01_path = self._get_table_path('rkaccm01.dbf', year_folder)
        if not os.path.exists(m02_path): m02_path = self._get_table_path('rkaccm02.dbf', year_folder)
        if not os.path.exists(m11_path): m11_path = self._get_table_path('rkaccm11.dbf', year_folder)
        
        if not os.path.exists(m01_path):
            raise FileNotFoundError(f"Accounting ledger master table not found at {m01_path}")
            
        try:
            # Load master tables
            m01_table = DBF(m01_path, load=True, encoding='cp1252')
            
            # Load Print Names (m02) if available
            print_names = {}
            if os.path.exists(m02_path):
                try:
                    m02_table = DBF(m02_path, load=True, encoding='cp1252')
                    for r in m02_table.records: # type: ignore
                        print_names[r.get('FIELD01')] = r['FIELD61']
                except Exception as ex:
                    print(f"Warning: Failed to load print names: {ex}")
            
            # Load Groups (m11) if available
            groups = {}
            if os.path.exists(m11_path):
                try:
                    m11_table = DBF(m11_path, load=True, encoding='cp1252')
                    for r in m11_table.records: # type: ignore
                        groups[r.get('FIELD01')] = {
                            'name': r['FIELD02'],
                            'parent': r['FIELD04']
                        }
                except Exception as ex:
                    print(f"Warning: Failed to load account groups: {ex}")
            
            # Classification helper walking up the group hierarchy
            def classify_group(group_code):
                curr = group_code
                visited = set()
                while curr and curr not in visited:
                    visited.add(curr)
                    if curr == 'G0000013':
                        return 'Creditor'
                    if curr == 'G0000009':
                        return 'Debtor'
                    if curr == 'G0000004':
                        return 'Bank'
                    if curr == 'G0000005':
                        return 'Cash'
                    if curr in ['G0000023', 'G0000024']:
                        return 'Expense'
                    if curr == 'G0000001':
                        return 'Capital'
                    if curr == 'G0000006':
                        return 'FixedAsset'
                    if curr == 'G0000007':
                        return 'Investment'
                    if curr == 'G0000014':
                        return 'DutiesTaxes'
                    if curr == 'G0000021':
                        return 'Sales'
                    if curr == 'G0000022':
                        return 'IndirectIncome'
                    if curr == 'G0000028':
                        return 'Suspense'
                    
                    group_info = groups.get(curr)
                    if not group_info:
                        break
                    
                    g_name = str(group_info.get('name') or '').upper()
                    if 'CASH' in g_name:
                        return 'Cash'
                    if 'BANK' in g_name:
                        return 'Bank'
                    if 'DEBTOR' in g_name or 'CUSTOMER' in g_name:
                        return 'Debtor'
                    if 'CREDITOR' in g_name or 'SUPPLIER' in g_name or 'VENDOR' in g_name:
                        return 'Creditor'
                    if 'EXPENSE' in g_name:
                        return 'Expense'
                        
                    curr = group_info.get('parent')
                return 'Other'
                
            # Classify all ledgers
            ledgers = []
            for r in m01_table.records: # type: ignore
                code = r.get('FIELD01')
                name = r.get('FIELD02')
                group_code = r.get('FIELD05')
                gstin = str(r.get('M01F05') or '').strip()
                
                print_name = print_names.get(code, '') or name
                classification = classify_group(group_code)
                
                # Dynamic fallbacks based on ledger name/code string matching
                name_up = str(name or '').strip().upper()
                code_up = str(code or '').strip().upper()
                if classification == 'Other':
                    if 'CASH' in name_up or code_up == 'ACASHACT':
                        classification = 'Cash'
                    elif any(brand in name_up for brand in ['BANK', 'HDFC', 'ICICI', 'SBI', 'AXIS', 'KOTAK', 'CANARA', 'UNION']):
                        classification = 'Bank'
                
                ledgers.append({
                    'code': code,
                    'name': name,
                    'print_name': print_name,
                    'group_code': group_code,
                    'group_name': groups.get(group_code, {}).get('name', 'Unknown'),
                    'classification': classification,
                    'gstin': gstin
                })
                
            return ledgers
            
        except Exception as e:
            raise Exception(f"Failed to read ledgers for {year_folder}: {str(e)}")

    def read_account_groups(self, year_folder: str | None = None) -> list:
        """Reads all account groups from RKACCM11.DBF and returns structured hierarchy."""
        if not year_folder:
            year_folder = self.get_latest_year_folder()
            
        m11_path = self._get_table_path('RKACCM11.DBF', year_folder)
        if not os.path.exists(m11_path): m11_path = self._get_table_path('rkaccm11.dbf', year_folder)
        
        if not os.path.exists(m11_path):
            return []
            
        try:
            m11_table = DBF(m11_path, load=True, encoding='cp1252')
            groups_dict = {}
            for r in m11_table.records:
                code = str(r.get('FIELD01', '')).strip()
                name = str(r.get('FIELD02', '')).strip()
                print_name = str(r.get('FIELD03', '')).strip() or name
                parent = str(r.get('FIELD04', '')).strip()
                groups_dict[code] = {
                    'code': code,
                    'name': name,
                    'print_name': print_name,
                    'parent_code': parent,
                    'parent_name': ''
                }
                
            # Fill parent names and resolve financial category
            for code, info in groups_dict.items():
                p_code = info['parent_code']
                if p_code in groups_dict:
                    info['parent_name'] = groups_dict[p_code]['name']
                
                # Nature classification by walking parent hierarchy
                curr = code
                visited = set()
                category = 'Other'
                while curr and curr not in visited:
                    visited.add(curr)
                    if curr == 'G0000013':
                        category = 'Creditor'
                        break
                    elif curr == 'G0000009':
                        category = 'Debtor'
                        break
                    elif curr == 'G0000004':
                        category = 'Bank'
                        break
                    elif curr == 'G0000005':
                        category = 'Cash'
                        break
                    elif curr in ['G0000023', 'G0000024']:
                        category = 'Expense'
                        break
                    elif curr == 'G0000001':
                        category = 'Capital'
                        break
                    elif curr == 'G0000006':
                        category = 'FixedAsset'
                        break
                    elif curr == 'G0000007':
                        category = 'Investment'
                        break
                    elif curr == 'G0000014':
                        category = 'DutiesTaxes'
                        break
                    elif curr == 'G0000021':
                        category = 'Sales'
                        break
                    elif curr == 'G0000022':
                        category = 'IndirectIncome'
                        break
                    elif curr == 'G0000028':
                        category = 'Suspense'
                        break
                    
                    p_info = groups_dict.get(curr)
                    if not p_info:
                        break
                    g_name_up = p_info['name'].upper()
                    if 'CASH' in g_name_up:
                        category = 'Cash'
                        break
                    elif 'BANK' in g_name_up:
                        category = 'Bank'
                        break
                    elif 'DEBTOR' in g_name_up or 'CUSTOMER' in g_name_up:
                        category = 'Debtor'
                        break
                    elif 'CREDITOR' in g_name_up or 'SUPPLIER' in g_name_up:
                        category = 'Creditor'
                        break
                    elif 'EXPENSE' in g_name_up:
                        category = 'Expense'
                        break
                    curr = p_info.get('parent_code')
                info['category'] = category

            return list(groups_dict.values())
        except Exception as e:
            print(f"Error reading account groups for {year_folder}: {e}")
            return []

    get_account_groups = read_account_groups

    def read_ledgers_all_years(self, active_year_folder: str | None = None) -> list:
        """
        Reads and MERGES ledgers from ALL available year folders.
        
        Why this matters:
          Miracle stores a copy of RKACCM01.DBF inside each year folder (YR25, YR26, YR27).
          When a new year is created, Miracle copies the ledger master at that point in time.
          Any new parties we create in YR25 via our tool are added to YR25/rkaccm01.dbf but
          NOT automatically reflected in YR26/rkaccm01.dbf — causing our push code to see
          the party as "new" and create a duplicate ledger.
          
          This method solves that by reading ALL year folders and merging into one unified list.
          The ACTIVE year folder (the one being pushed to) has the highest priority — if the
          same name exists in multiple years, the active-year entry's code is used.
          
        Returns:
          A merged list of ledger dicts. No duplicates by name. Active year wins on conflict.
        """
        if not active_year_folder:
            active_year_folder = self.get_latest_year_folder()
            
        cache_key = (self.client_path, active_year_folder)
        now = time.monotonic()
        
        with MiracleDBFHandler._CROSS_YEAR_CACHE_LOCK:
            if cache_key in MiracleDBFHandler._CROSS_YEAR_CACHE:
                cache_time, cached_ledgers = MiracleDBFHandler._CROSS_YEAR_CACHE[cache_key]
                if (now - cache_time) < MiracleDBFHandler._CROSS_YEAR_CACHE_TTL:
                    print(f"⚡ [Ledger Cache HIT] Serviced {len(cached_ledgers)} ledgers from RAM in 0.0001s.")
                    return [l.copy() for l in cached_ledgers]
        
        all_folders = self.get_available_year_folders()
        # Sort so active year is processed LAST (highest priority / wins on conflict)
        folder_names = [f['name'] for f in all_folders if f['name'] != active_year_folder]
        folder_names.append(active_year_folder)  # active year is last = highest priority
        
        merged: dict = {}  # key = ledger name (upper) → ledger dict
        
        for yr in folder_names:
            try:
                yr_ledgers = self.read_ledgers(yr)
                for led in yr_ledgers:
                    name_key = (led.get('name') or '').strip().upper()
                    if name_key:
                        led['year_folder'] = yr
                        merged[name_key] = led  # later year overwrites earlier (active year wins)
            except Exception as e:
                # If a year folder has no ledger file, skip it silently
                print(f"  [cross-year] Skipped {yr}: {e}")
        
        result = list(merged.values())
        print(f"[cross-year ledger merge] {len(result)} unique ledgers found across {len(folder_names)} year folders.")
        with MiracleDBFHandler._CROSS_YEAR_CACHE_LOCK:
            MiracleDBFHandler._CROSS_YEAR_CACHE[cache_key] = (now, result)
        return result


    def get_debtor_balances(self, year_folder: str | None = None) -> list:
        """Calculates closing balances for all Sundry Debtors."""
        if not year_folder:
            year_folder = self.get_latest_year_folder()
            
        ledgers = self.read_ledgers(year_folder)
        debtor_map = {l['code']: l['name'] for l in ledgers if l.get('classification') == 'Debtor'}
        
        m01_path = self._get_table_path('RKACCM01.DBF', year_folder)
        t01_path = self._get_table_path('RKACCT01.DBF', year_folder)
        
        balances = {code: 0.0 for code in debtor_map}
        last_dates = {code: None for code in debtor_map}
        import dbf
        import os
        from datetime import date
        
        if os.path.exists(m01_path):
            with self.safe_cdx_context(m01_path):
                m01 = dbf.Table(m01_path)
                m01.open(mode=dbf.READ_ONLY)
                for r in m01:
                    if dbf.is_deleted(r): continue
                    code = str(r['FIELD01']).strip()
                    if code in balances:
                        ob = float(r['FIELD09'] or 0.0) if 'FIELD09' in m01.field_names else 0.0 # type: ignore
                        dc = str(r['FIELD10']).strip().upper() if 'FIELD10' in m01.field_names else ''
                        if dc == 'D':
                            balances[code] += ob
                        elif dc == 'C':
                            balances[code] -= ob
                m01.close()
                
        if os.path.exists(t01_path):
            with self.safe_cdx_context(t01_path):
                t01 = dbf.Table(t01_path)
                t01.open(mode=dbf.READ_ONLY)
                for r in t01:
                    if dbf.is_deleted(r): continue
                    code = str(r['FIELD03']).strip()
                    if code in balances:
                        amt = float(r['FIELD05'] or 0.0) # type: ignore
                        dc = str(r['FIELD06'] or '').strip().upper()
                        if dc == 'D':
                            balances[code] += amt
                        elif dc == 'C':
                            balances[code] -= amt
                            
                        dt = r['FIELD02']
                        if isinstance(dt, date):
                            ld = last_dates[code]
                            if ld is None or dt > ld:
                                last_dates[code] = dt # type: ignore
                t01.close()
                
        result = []
        year_folder_name = year_folder if year_folder else "YR26"
        try:
            year_num = int(year_folder_name[-2:])
            fallback_date = f"20{year_num}-03-31"
        except:
            fallback_date = "2026-03-31"
            
        for code, bal in balances.items():
            if abs(bal) > 0.01:
                last_dt = last_dates.get(code)
                
                final_date = fallback_date
                if last_dt:
                    try:
                        fy_start = f"20{year_num - 1}-04-01" # type: ignore
                        last_dt_str = last_dt.strftime('%Y-%m-%d')
                        if last_dt_str >= fy_start:
                            final_date = last_dt_str
                    except: pass

                result.append({
                    'code': code,
                    'name': debtor_map[code],
                    'balance': round(bal, 2),
                    'last_transaction_date': final_date
                })
        return result

    def get_all_last_transaction_dates(self) -> dict:
        year_folder = self.get_latest_year_folder()
        if not year_folder:
            return {}
            
        t01_path = self._get_table_path('RKACCT01.DBF', year_folder)
        last_dates = {}
        
        import os
        import dbf
        from datetime import date
        
        if os.path.exists(t01_path):
            with self.safe_cdx_context(t01_path):
                try:
                    t01 = dbf.Table(t01_path)
                    t01.open(mode=dbf.READ_ONLY)
                    for r in t01:
                        if dbf.is_deleted(r): continue
                        code = str(r['FIELD03']).strip()
                        dt = r['FIELD02']
                        if isinstance(dt, date):
                            if code not in last_dates or dt > last_dates[code]:
                                last_dates[code] = dt
                    t01.close()
                except Exception as e:
                    print(f"Error reading T01 for dates: {e}")
                    
        # Convert to string formats
        return {code: dt.strftime('%Y-%m-%d') for code, dt in last_dates.items()}

    def find_ledger_by_keyword(self, keyword: str, year_folder: str | None = None) -> str:
        """Finds a ledger code by searching for a keyword in ledger name or print name."""
        try:
            ledgers = self.read_ledgers(year_folder)
            for led in ledgers:
                if keyword.upper() in led['name'].upper() or keyword.upper() in led['print_name'].upper():
                    return led['code']
        except Exception as e:
            print(f"Error finding ledger by keyword '{keyword}': {e}")
        return ""

    def get_or_create_dynamic_ledger(self, keyword: str, ledger_name: str, group_code: str, parent_group: str, year_folder: str | None = None) -> str:
        """Finds a ledger by keyword, or creates it if it doesn't exist."""
        ledger_name = ledger_name.strip()[:60]
        existing_code = self.find_ledger_by_keyword(keyword, year_folder)
        if existing_code:
            return existing_code
            
        print(f"Ledger for '{keyword}' not found. Creating new ledger: {ledger_name}")

        if not year_folder:
            year_folder = self.get_latest_year_folder()
            
        m01_path = self._get_table_path('RKACCM01.DBF', year_folder)
        m02_path = self._get_table_path('RKACCM02.DBF', year_folder)
        if not os.path.exists(m01_path): m01_path = self._get_table_path('rkaccm01.dbf', year_folder)
        if not os.path.exists(m02_path): m02_path = self._get_table_path('rkaccm02.dbf', year_folder)
        
        if not os.path.exists(m01_path) or not os.path.exists(m02_path):
            raise FileNotFoundError("Miracle master ledger tables not found.")
            
        import dbf
        import random
        import string
        
        with self.safe_cdx_context(m01_path):
            t01 = dbf.Table(m01_path)
            t01.open(mode=dbf.READ_WRITE)
            try:
                existing_codes = {str(r['FIELD01']).strip().upper() for r in t01}
                existing_links = {str(r['FIELD16']).strip().upper() for r in t01 if r['FIELD16']}
                
                def gen_code(prefix, length=8):
                    return f"{prefix}{''.join(random.choices(string.ascii_uppercase + string.digits, k=length - len(prefix)))}"

                led_code = gen_code('AY')
                while led_code in existing_codes: led_code = gen_code('AY')
                    
                link_code = gen_code('TY')
                while link_code in existing_links: link_code = gen_code('TY')
                
                m01_rec = {
                    'FIELD01': led_code,
                    'FIELD02': ledger_name,
                    'FIELD04': 'B',
                    'FIELD05': group_code,
                    'FIELD06': parent_group,
                    'FIELD07': 'PR',
                    'FIELD08': '1',
                    'M01F14': 'U',
                    'FIELD16': link_code,
                    'M01F17': 'O',
                    'FIELD22': 'G',
                    'FIELD23': 'N',
                    'FIELD24': 'N',
                    'FIELD55': 'N',
                    'M01F03': 'N',
                    'M01F19': 'N',
                    'M01F23': 'N'
                }
                t01.append(self.clean_record_dict(m01_rec, table=t01)) # type: ignore
            finally:
                t01.close()
                
        with self.safe_cdx_context(m02_path):
            t02 = dbf.Table(m02_path)
            t02.open(mode=dbf.READ_WRITE)
            try:
                m02_rec = {
                    'FIELD01': led_code,
                    'FIELD08': link_code,
                    'FIELD61': ledger_name,
                    'FIELD90': 'A'
                }
                t02.append(self.clean_record_dict(m02_rec, table=t02)) # type: ignore
            finally:
                t02.close()
                
        self._register_guid('YRM01', led_code, is_header=False)
        return led_code

    def read_products(self, year_folder: str | None = None) -> list:
        """Reads all products from RKACCM21.DBF in the active client folder."""

        if not year_folder:
            year_folder = self.get_latest_year_folder()
            
        m21_path = self._get_table_path('RKACCM21.DBF', year_folder)
        if not os.path.exists(m21_path):
            m21_path = self._get_table_path('rkaccm21.dbf', year_folder)
            
        if not os.path.exists(m21_path):
            return []
            
        try:
            from dbfread import DBF
            m21_table = DBF(m21_path, load=True, encoding='cp1252')
            products = []
            for r in m21_table.records: # type: ignore
                code = r['FIELD01']
                name = r['FIELD02']
                # Read HSN/SAC from M21F31 first, fallback to FIELD40 (Alias) safely using .get()
                hsn = r.get('M21F31') or r.get('FIELD40') or ''
                if isinstance(hsn, str) and hsn.strip() == 'XXXXXXXX':
                    hsn = ''
                uom = r.get('FIELD05') or ''
                uqc = r.get('M21F28') or ''
                commodity = r.get('M21F27') or ''
                comm_type = r.get('M21F26') or ''
                
                category = commodity.strip() if commodity else (comm_type.strip() if comm_type else "General Stock")
                products.append({
                    'code': code.strip() if code else '',
                    'name': name.strip() if name else '',
                    'hsn_code': hsn.strip() if hsn else '',
                    'uom': uom.strip() if uom else '',
                    'uqc': uqc.strip() if uqc else '',
                    'commodity': commodity.strip() if commodity else '',
                    'commodity_type': comm_type.strip() if comm_type else '',
                    'category': category
                })
            return products
        except Exception as e:
            print(f"Error reading products for {year_folder}: {e}")
            return []

    def read_products_all_years(self) -> list:
        """Reads and merges all products from RKACCM21.DBF across ALL financial year directories (YR27, YR26, YR25)."""
        year_folders = self.get_available_year_folders()
        merged_products = {}
        seen_names = set()

        for yr in year_folders:
            folder_name = yr.get("name")
            if not folder_name:
                continue
            prods = self.read_products(year_folder=folder_name)
            for p in prods:
                p_code = p.get("code", "").strip()
                p_name = p.get("name", "").strip()
                key = (p_name.upper(), p_code.upper())
                if key not in seen_names and p_name:
                    seen_names.add(key)
                    merged_products[key] = p

        return list(merged_products.values())

    def _sync_party_to_other_years(self, party_name: str, party_code: str, source_year_folder: str, target_year_folder: str | None = None):
        """
        Copy RKACCM01 + RKACCM02 records for party_code from source_year_folder into target_year_folder.
        
        Note: Ledgers are strictly created/updated in the active selected year. Cross-year sync only runs
        when an explicit target_year_folder is provided (e.g., copying an existing ledger from a prior year into the current year).
        """
        import dbf as dbf_lib
        
        if not target_year_folder or target_year_folder == source_year_folder:
            return
            
        other_folders = [target_year_folder]
        
        # Read the source record from the source year
        src_m01 = self._get_table_path('rkaccm01.dbf', source_year_folder)
        src_m02 = self._get_table_path('rkaccm02.dbf', source_year_folder)
        if not os.path.exists(src_m01): src_m01 = self._get_table_path('RKACCM01.DBF', source_year_folder)
        if not os.path.exists(src_m02): src_m02 = self._get_table_path('RKACCM02.DBF', source_year_folder)
        
        src_m01_record = None
        src_m02_record = None
        
        try:
            with self.safe_cdx_context(src_m01):
                t = dbf_lib.Table(src_m01)
                t.open(mode=dbf_lib.READ_ONLY)
                for r in t:
                    if dbf_lib.is_deleted(r):
                        continue
                    if str(r['FIELD01']).strip() == party_code:
                        src_m01_record = {f: r[f] for f in t.field_names}
                        break
                t.close()
        except Exception as e:
            print(f"[sync] Could not read source RKACCM01 record for {party_name}: {e}")
            return
            
        try:
            with self.safe_cdx_context(src_m02):
                t = dbf_lib.Table(src_m02)
                t.open(mode=dbf_lib.READ_ONLY)
                for r in t:
                    if dbf_lib.is_deleted(r):
                        continue
                    if str(r['FIELD01']).strip() == party_code:
                        src_m02_record = {f: r[f] for f in t.field_names}
                        break
                t.close()
        except Exception as e:
            print(f"[sync] Could not read source RKACCM02 record for {party_name}: {e}")
        
        if not src_m01_record:
            print(f"[sync] No M01 record found for party_code={party_code}, skipping sync.")
            return
        
        # Write to each other year folder
        for yr in other_folders:
            try:
                dst_m01 = self._get_table_path('rkaccm01.dbf', yr)
                dst_m02 = self._get_table_path('rkaccm02.dbf', yr)
                if not os.path.exists(dst_m01): dst_m01 = self._get_table_path('RKACCM01.DBF', yr)
                if not os.path.exists(dst_m02): dst_m02 = self._get_table_path('RKACCM02.DBF', yr)
                
                # Check if this party already exists in the destination year
                already_exists = False
                if os.path.exists(dst_m01):
                    with self.safe_cdx_context(dst_m01):
                        t = dbf_lib.Table(dst_m01)
                        t.open(mode=dbf_lib.READ_ONLY)
                        for r in t:
                            if dbf_lib.is_deleted(r): continue
                            r_name = str(r['FIELD02']).strip().upper()
                            r_code = str(r['FIELD01']).strip()
                            if r_code == party_code or r_name == party_name.strip().upper():
                                already_exists = True
                                break
                        t.close()
                
                if already_exists:
                    # 1. Update existing record in destination year RKACCM01.DBF
                    with self.safe_cdx_context(dst_m01):
                        t = dbf_lib.Table(dst_m01)
                        t.open(mode=dbf_lib.READ_WRITE)
                        try:
                            for r in t:
                                if not dbf_lib.is_deleted(r):
                                    r_name = str(r['FIELD02']).strip().upper()
                                    r_code = str(r['FIELD01']).strip()
                                    if r_code == party_code or r_name == party_name.strip().upper():
                                        kw1 = {'FIELD02': src_m01_record['FIELD02'], 'FIELD05': src_m01_record['FIELD05']}
                                        if 'M01F05' in src_m01_record and src_m01_record['M01F05']:
                                            kw1['M01F05'] = src_m01_record['M01F05']
                                        dbf_lib.write(r, **kw1)
                                        print(f"[sync] Updated {party_name} ({party_code}) in {yr} RKACCM01 (Name/Group/GSTIN).")
                                        break
                        finally:
                            t.close()

                    # 2. Update existing record in destination year RKACCM02.DBF
                    if src_m02_record and os.path.exists(dst_m02):
                        with self.safe_cdx_context(dst_m02):
                            t = dbf_lib.Table(dst_m02)
                            t.open(mode=dbf_lib.READ_WRITE)
                            try:
                                for r in t:
                                    if not dbf_lib.is_deleted(r) and str(r['FIELD01']).strip() == party_code:
                                        kw2 = {}
                                        for fld in ['FIELD02', 'FIELD03', 'FIELD04', 'FIELD05', 'FIELD07', 'FIELD43', 'FIELD61']:
                                            if fld in src_m02_record and src_m02_record[fld]:
                                                kw2[fld] = src_m02_record[fld]
                                        if kw2:
                                            dbf_lib.write(r, **kw2)
                                        break
                            finally:
                                t.close()
                    continue
                
                # Write M01 record
                if os.path.exists(dst_m01):
                    with self.safe_cdx_context(dst_m01):
                        t = dbf_lib.Table(dst_m01)
                        t.open(mode=dbf_lib.READ_WRITE)
                        try:
                            t.append(self.clean_record_dict(src_m01_record, table=t))
                            print(f"[sync] ✅ Synced {party_name} ({party_code}) M01 → {yr}")
                        finally:
                            t.close()
                
                # Write M02 record if available
                if src_m02_record and os.path.exists(dst_m02):
                    with self.safe_cdx_context(dst_m02):
                        t = dbf_lib.Table(dst_m02)
                        t.open(mode=dbf_lib.READ_WRITE)
                        try:
                            t.append(self.clean_record_dict(src_m02_record, table=t))
                        finally:
                            t.close()
            except Exception as e:
                # Non-fatal: if sync to one year fails, continue with others
                print(f"[sync] ⚠️ Failed to sync {party_name} to {yr}: {e}")

    def sync_closing_balances_to_next_year(self, source_year_folder: str, affected_ledger_codes: list | None = None):
        """
        After injecting vouchers into source_year_folder (e.g. YR25 / 2025-26), automatically
        calculate updated closing balances for affected ledgers and carry them forward into the
        Opening Balance of the NEXT financial year folder (e.g. YR26 / 2026-27).
        """
        if not source_year_folder:
            return
            
        import dbf as dbf_lib
        import re
        
        # Calculate next year folder name (e.g. YR25 -> YR26)
        match = re.search(r'(\d+)', source_year_folder)
        if not match:
            return
        curr_num = int(match.group(1))
        next_yr_name = f"YR{curr_num + 1}"
        
        all_folders = self.get_available_year_folders()
        next_folder = None
        for f in all_folders:
            f_name = f['name']
            if f_name.upper() == next_yr_name.upper():
                next_folder = f_name
                break
                
        if not next_folder:
            return
            
        src_m01 = self._get_table_path('rkaccm01.dbf', source_year_folder)
        if not os.path.exists(src_m01): src_m01 = self._get_table_path('RKACCM01.DBF', source_year_folder)
        
        dst_m01 = self._get_table_path('rkaccm01.dbf', next_folder)
        if not os.path.exists(dst_m01): dst_m01 = self._get_table_path('RKACCM01.DBF', next_folder)
        
        if not os.path.exists(src_m01) or not os.path.exists(dst_m01):
            return

        # Calculate closing balances in source year for affected ledgers
        src_vouchers = self.read_vouchers(source_year_folder, limit=50000)
        src_ledgers = {l['code']: l for l in self.read_ledgers(source_year_folder)}
        
        target_codes = set(affected_ledger_codes or src_ledgers.keys())
        
        ledger_debits = {}
        ledger_credits = {}
        for v in src_vouchers:
            dr_code = str(v.get('dr_ledger_code', '')).strip()
            cr_code = str(v.get('cr_ledger_code', '')).strip()
            amt = float(v.get('amount', 0.0) or 0.0)
            if dr_code in target_codes:
                ledger_debits[dr_code] = ledger_debits.get(dr_code, 0.0) + amt
            if cr_code in target_codes:
                ledger_credits[cr_code] = ledger_credits.get(cr_code, 0.0) + amt
                
        for code in target_codes:
            if code not in src_ledgers:
                continue
            m = src_ledgers[code]
            op_amt = float(m.get('opening_balance', 0.0) or 0.0)
            op_type = str(m.get('opening_type', 'D')).strip().upper()
            
            op_signed = op_amt if op_type in ('D', '1', 'DB') else -op_amt
            net_dr = ledger_debits.get(code, 0.0)
            net_cr = ledger_credits.get(code, 0.0)
            
            closing_signed = op_signed + net_dr - net_cr
            closing_amt = round(abs(closing_signed), 2)
            closing_type = '1' if closing_signed >= 0 else '2'
            
            try:
                with self.safe_cdx_context(dst_m01):
                    t = dbf_lib.Table(dst_m01)
                    t.open(mode=dbf_lib.READ_WRITE)
                    try:
                        for r in t:
                            if not dbf_lib.is_deleted(r):
                                if str(r['FIELD01']).strip() == code:
                                    dbf_lib.write(r, FIELD08=closing_amt, FIELD09=closing_type)
                                    print(f"[carry-forward] ✅ Updated Opening Balance for {m.get('name')} ({code}) in {next_folder} to {closing_amt} ({'DB' if closing_type=='1' else 'CR'})")
                                    break
                    finally:
                        t.close()
            except Exception as ex:
                print(f"[carry-forward] ⚠️ Could not update opening balance in {next_folder} for {code}: {ex}")

    def create_party_ledger(self, name: str, module: str, gstin: str = "", address: str = "", city: str = "", pincode: str = "", year_folder: str | None = None, transaction_type: str = "", group_hint: str = "", explicit_group_code: str = "") -> str:
        """Automatically creates a new party ledger in RKACCM01 and RKACCM02. Handles B2B and B2C based on gstin."""
        MiracleDBFHandler.clear_cross_year_cache(self.client_path)
        name = name.strip()[:60]
        gstin = gstin.strip().upper()[:15]

        if not name or name.upper().startswith("UNKNOWN_PARTY") or name.upper() == "NONE":
            if gstin and len(gstin) >= 15:
                name = f"Supplier {gstin}" if module == "Purchases" else f"Customer {gstin}"
            else:
                name = f"Unregistered {module} Party"

        if not year_folder:
            year_folder = self.get_latest_year_folder()
            
        m01_path = self._get_table_path('RKACCM01.DBF', year_folder)
        m02_path = self._get_table_path('RKACCM02.DBF', year_folder)
        
        # Check case variation
        if not os.path.exists(m01_path): m01_path = self._get_table_path('rkaccm01.dbf', year_folder)
        if not os.path.exists(m02_path): m02_path = self._get_table_path('rkaccm02.dbf', year_folder)
        
        if not os.path.exists(m01_path) or not os.path.exists(m02_path):
            raise FileNotFoundError("Miracle master ledger tables not found.")

        import dbf
        import random
        import string

        # Resolve groups from RKACCM11.DBF dynamically to avoid mismatch with client-specific custom chart of accounts
        resolved_groups = {}
        group_code_to_parent = {}
        m11_path = self._get_table_path('RKACCM11.DBF', year_folder)
        if not os.path.exists(m11_path): m11_path = self._get_table_path('rkaccm11.dbf', year_folder)
        if os.path.exists(m11_path):
            try:
                m11_table = DBF(m11_path, load=True, encoding='cp1252')
                for r in m11_table.records:
                    g_code = str(r['FIELD01']).strip()
                    g_name = str(r['FIELD02']).strip().upper()
                    g_parent = str(r['FIELD04']).strip() if r.get('FIELD04') else ""
                    resolved_groups[g_name] = {"code": g_code, "parent": g_parent}
                    group_code_to_parent[g_code] = g_parent
            except Exception as ex:
                print(f"Warning: Failed to load groups in create_party_ledger: {ex}")

        def find_group_by_name(pattern_list, fallback_code, fallback_parent):
            for pattern in pattern_list:
                for name, info in resolved_groups.items():
                    if pattern in name:
                        return info["code"], info["parent"]
            return fallback_code, fallback_parent

        # Determine group codes based on name-based overrides first (highly reliable & universal)
        name_up = name.strip().upper()
        group_hint_up = group_hint.strip().upper()
        
        if explicit_group_code:
            group_code = explicit_group_code.strip()
            parent_group = group_code_to_parent.get(group_code, "")
        # 1. Suspense overrides
        elif "SUSPENSE" in name_up:
            group_code, parent_group = find_group_by_name(["SUSPENSE ACCOUNT", "SUSPENSE"], 'G0000028', '')
        # 1b. Bank Charges & Service Fees overrides (MUST evaluate BEFORE Bank Accounts!)
        elif any(w in name_up for w in ["BANK CHARG", "BANK CHAG", "BANK CHARGES", "SMS CHARG", "INSTAALERT", "ALERTCHG", "SERVICE CHG", "SERVICE CHARGE", "SERVICE CHARGES", "CARD CHARG", "ATM CHG", "MDR RCVRY"]):
            group_code, parent_group = find_group_by_name(["EXPENSE ACCOUNT", "INDIRECT EXPENSE", "EXPENSES (INDIRECT)", "INDIRECT EXPENSES", "EXPENSE"], 'G0000017', 'G0000002')
        # 2. Bank overrides (Only actual Bank A/cs like HDFC Bank, ICICI Bank, Axis Bank A/c)
        elif (any(w in name_up for w in ["BANK A/C", "BANK ACCOUNT", "CURRENT A/C", "SAVINGS A/C"]) or 
              any(w in name_up for w in ["HDFC", "ICICI", "SBI", "AXIS", "KOTAK", "BOB", "PNB", "UNION BANK", "CANARA"])) and not any(chg in name_up for chg in ["CHARGE", "CHARGES", "CHG", "CHGS", "INTEREST", "COMMISSION", "FEE", "FEES"]):
            group_code, parent_group = find_group_by_name(["BANK ACCOUNTS (BANKS)", "BANK ACCOUNTS", "BANKS"], 'G0000004', 'G0000003')
        # 3. Cash overrides
        elif name_up in ("CASH", "CASH ACCOUNT", "CASH A/C"):
            group_code, parent_group = find_group_by_name(["CASH HAND", "CASH"], 'G0000005', 'G0000003')
        # 4. Capital / Drawings overrides
        elif any(w in name_up for w in ["DRAWING", "DRAWINGS", "PERSONAL EXPENSE", "PERSONAL EXPENSES", "PARTNER CAPITAL"]):
            group_code, parent_group = find_group_by_name(["CAPITAL ACCOUNT", "CAPITAL"], 'G0000001', 'G0000010')
        # 5. Fixed Assets overrides
        elif any(w in name_up for w in [
            "COMPUTER", "LAPTOP", "PRINTER", "MACHINERY", "FURNITURE", "FIXTURE", "FIXTURES",
            "OFFICE EQUIPMENT", "EQUIPMENTS", "VEHICLE", "MOTOR CAR", "BIKE", "LAND", "BUILDING", "AIR CONDITIONER"
        ]):
            group_code, parent_group = find_group_by_name(["FIXED ASSETS", "FIXED ASSET"], 'G0000006', 'G0000003')
        # 6. Investments overrides
        elif any(w in name_up for w in ["MUTUAL FUND", "SHARES", "STOCK", "INVESTMENT", "INVESTMENTS", "FIXED DEPOSIT", "FD A/C"]):
            group_code, parent_group = find_group_by_name(["INVESTMENTS", "INVESTMENT"], 'G0000007', 'G0000003')
        # 7. Secured / Unsecured Loans overrides
        elif "UNSECURED LOAN" in name_up or "UNSECURED LOANS" in name_up:
            group_code, parent_group = find_group_by_name(["UNSECURED LOANS", "UNSECURED"], 'G0000019', 'G0000010')
        elif "SECURED LOAN" in name_up or "SECURED LOANS" in name_up:
            group_code, parent_group = find_group_by_name(["SECURED LOANS", "SECURED"], 'G0000008', 'G0000010')
        # 8. Expense overrides (covers Rent, Salary, Fees, Charges, Welfare, Office, Printing, Repairs, etc.)
        elif any(w in name_up for w in [
            "EXPENSE", "EXPENSES", "CHARGE", "CHARGES", "RENT", "SALARY", "SALARIES", "INTEREST", "FEES", "FEE",
            "TELEPHONE", "ELECTRICITY", "POWER", "FUEL", "PETROL", "DIESEL", "CONVEYANCE", "TRAVEL", "TRAVELLING",
            "OFFICE", "PRINTING", "STATIONERY", "REPAIR", "REPAIRS", "MAINTENANCE", "COMMISSION", "BROKERAGE",
            "PROFESSIONAL", "AUDIT", "POSTAGE", "COURIER", "SUBSCRIPTION", "ADVERTISEMENT", "ADVERTISING",
            "WELFARE", "INSURANCE", "PROMOTION", "ENTERTAINMENT", "DONATION", "DONETION", "TEA", "COFFEE",
            "REFRESHMENT", "REFRESHMENTS", "MILK", "WATER", "CLEANING", "SWEET", "SWEETS", "FARSAN", "FOOD",
            "HOTEL", "RESTAURANT", "CATERING", "SOFTWARE", "INTERNET", "WIFI", "DOMAIN", "HOSTING", "CLOUD",
            "BROADBAND", "MOBILE", "RECHARGE", "PENALTY", "LATE FEE", "SERVICE CHG", "SERVICE CHARGE", "SERVICE CHARGES"
        ]):
            group_code, parent_group = find_group_by_name(["EXPENSE ACCOUNT", "INDIRECT EXPENSE", "EXPENSES (INDIRECT)", "INDIRECT EXPENSES", "EXPENSE"], 'G0000017', 'G0000002')
        # 9. Income overrides
        elif any(w in name_up for w in ["INCOME", "INTEREST RECEIVED", "COMMISSION RECEIVED", "RENT RECEIVED", "DIVIDEND"]):
            group_code, parent_group = find_group_by_name(["INCOME (OTHER THEN SALES)", "INDIRECT INCOME", "INCOME"], 'G0000016', 'G0000002')
        # 10. Duties & Taxes overrides
        elif any(w in name_up for w in ["TAX", "GST", "CGST", "SGST", "IGST", "CESS", "DUTY", "DUTIES", "TDS", "TCS", "VAT"]):
            group_code, parent_group = find_group_by_name(["DUTIES & TAXES", "DUTIES AND TAXES", "TAXES"], 'G0000003', 'G0000010')
            
        # If no name-based override matched, fall back to module and group_hint
        elif "INDIRECT EXPENSE" in group_hint_up or "EXPENSE" in group_hint_up:
            group_code, parent_group = find_group_by_name(["EXPENSE ACCOUNT", "INDIRECT EXPENSE", "EXPENSE"], 'G0000017', 'G0000002')
        elif "DIRECT EXPENSE" in group_hint_up:
            group_code, parent_group = find_group_by_name(["EXPENSES (DIRECT)", "DIRECT EXPENSE"], 'G0000014', 'G0000002')
        elif "INDIRECT INCOME" in group_hint_up or "INCOME" in group_hint_up:
            group_code, parent_group = find_group_by_name(["INCOME (OTHER THEN SALES)", "INDIRECT INCOME", "INCOME"], 'G0000016', 'G0000002')
        elif "DIRECT INCOME" in group_hint_up:
            group_code, parent_group = find_group_by_name(["INCOME (TRADING)", "DIRECT INCOME"], 'G0000015', 'G0000002')
        elif "FIXED ASSET" in group_hint_up:
            group_code, parent_group = find_group_by_name(["FIXED ASSETS", "FIXED ASSET"], 'G0000006', 'G0000003')
        elif "CAPITAL" in group_hint_up:
            group_code, parent_group = find_group_by_name(["CAPITAL ACCOUNT", "CAPITAL"], 'G0000001', 'G0000010')
        elif "INVESTMENT" in group_hint_up:
            group_code, parent_group = find_group_by_name(["INVESTMENTS", "INVESTMENT"], 'G0000007', 'G0000003')
        elif "LOANS & ADVANCES" in group_hint_up or "LOANS AND ADVANCES" in group_hint_up:
            group_code, parent_group = find_group_by_name(["LOANS & ADVANCES (ASSET)", "LOANS & ADVANCES", "LOANS AND ADVANCES"], 'G0000007', 'G0000003')
        elif "UNSECURED LOANS" in group_hint_up or "UNSECURED" in group_hint_up:
            group_code, parent_group = find_group_by_name(["UNSECURED LOANS", "UNSECURED"], 'G0000019', 'G0000010')
        elif "SUNDRY DEBTORS" in group_hint_up or "DEBTOR" in group_hint_up or "CUSTOMER" in group_hint_up:
            group_code, parent_group = find_group_by_name(["SUNDRY DEBTORS", "DEBTOR", "CUSTOMER"], 'G0000009', 'G0000003')
        elif "SUNDRY CREDITORS" in group_hint_up or "CREDITOR" in group_hint_up or "SUPPLIER" in group_hint_up:
            group_code, parent_group = find_group_by_name(["SUNDRY CREDITORS", "CREDITOR", "SUPPLIER"], 'G0000013', 'G0000010')
        elif "SALES" in group_hint_up:
            group_code, parent_group = find_group_by_name(["SALES ACCOUNTS", "SALES"], 'G0000011', 'G0000002')
        elif "PURCHASE" in group_hint_up:
            group_code, parent_group = find_group_by_name(["PURCHASE ACCOUNTS", "PURCHASE"], 'G0000012', 'G0000002')
        elif "BANK" in group_hint_up:
            group_code, parent_group = find_group_by_name(["BANK ACCOUNTS", "BANK"], 'G0000004', 'G0000003')
        elif "CASH" in group_hint_up:
            group_code, parent_group = find_group_by_name(["CASH HAND", "CASH"], 'G0000005', 'G0000003')
        elif module == 'Purchases':
            group_code, parent_group = find_group_by_name(["SUNDRY CREDITORS", "CREDITOR", "SUPPLIER"], 'G0000013', 'G0000010')
        elif module == 'Sales':
            group_code, parent_group = find_group_by_name(["SUNDRY DEBTORS", "DEBTOR", "CUSTOMER"], 'G0000009', 'G0000003')
        elif module in ('Bank Statements', 'Cash Entries'):
            # Check if this looks like a person's name (no common business keywords)
            business_keywords = ['ENTERPRISE', 'SERVICES', 'PRIVATE', 'LIMITED', 'LTD', 'PVT', 'BANK', 
                                  'COMPANY', 'CORP', 'INC', 'STORES', 'TRADERS', 'SOLUTIONS', 'TECHNOLOGIES',
                                  'TECH', 'INDUSTRIES', 'MOTORS', 'FILLING STATION', 'PETROLEUM', 'MEDICAL',
                                  'HOSPITAL', 'SCHOOL', 'COLLEGE', 'ACADEMY', 'INSTITUTE', 'RECHARGE',
                                  'DIGITAL', 'INSURANCE', 'FINANCE', 'AGENCY', 'ASSOCIATES', 'MART', 
                                  'FARSAN', 'SWEETS', 'BAKERY', 'FOODS', 'AGRO', 'DISTRIBUTORS', 
                                  'AGENCIES', 'CLOTHING', 'APPARALS', 'TEXTILES', 'JEWELLERS', 'JEWEL', 
                                  'GEMS', 'METALS', 'STEEL', 'PHARMA', 'CHEM', 'CHEMICALS', 'LAB', 
                                  'LABORATORY', 'DIAGNOSTICS', 'CLINIC', 'CARE', 'TRAVELS', 'CARGO', 
                                  'COURIER', 'LOGISTICS', 'TRANSPORT', 'INFRA', 'BUILDERS', 'CONSTRUCTIONS', 
                                  'DEVELOPERS']
            has_business_keyword = any(kw in name.strip().upper() for kw in business_keywords)
            
            if not has_business_keyword:
                # Looks like an individual person name — use loan accounts
                if transaction_type.capitalize() == 'Receipt':
                    group_code, parent_group = find_group_by_name(["UNSECURED LOANS", "UNSECURED"], 'G0000019', 'G0000010')
                else:
                    group_code, parent_group = find_group_by_name(["LOANS & ADVANCES (ASSET)", "LOANS & ADVANCES", "LOANS AND ADVANCES"], 'G0000007', 'G0000003')
            else:
                # Business name — use Debtors/Creditors
                if transaction_type.capitalize() == 'Receipt':
                    group_code, parent_group = find_group_by_name(["SUNDRY DEBTORS", "DEBTOR", "CUSTOMER"], 'G0000009', 'G0000003')
                else:
                    group_code, parent_group = find_group_by_name(["SUNDRY CREDITORS", "CREDITOR", "SUPPLIER"], 'G0000013', 'G0000010')
        else:
            group_code, parent_group = find_group_by_name(["SUNDRY CREDITORS", "CREDITOR", "SUPPLIER"], 'G0000013', 'G0000010')

        is_registered = bool(gstin and len(gstin) >= 15)
        tax_class = 'R' if is_registered else 'U'
        raw_state_code = gstin[:2] if is_registered else str(self.get_company_state_code() or '24')
        state_code_digits = raw_state_code.zfill(2)
        
        STATE_GST_MAPPING = {
            "02": {"id": "ST000014", "name": "Himachal Pradesh"},
            "03": {"id": "ST000028", "name": "Punjab"},
            "06": {"id": "ST000013", "name": "Haryana"},
            "07": {"id": "ST000010", "name": "Delhi"},
            "08": {"id": "ST000029", "name": "Rajasthan"},
            "09": {"id": "ST000033", "name": "Uttar Pradesh"},
            "18": {"id": "ST000004", "name": "Assam"},
            "19": {"id": "ST000035", "name": "West Bengal"},
            "20": {"id": "ST000016", "name": "Jharkhand"},
            "22": {"id": "ST000007", "name": "Chhattisgarh"},
            "23": {"id": "ST000020", "name": "Madhya Pradesh"},
            "24": {"id": "ST000012", "name": "Gujarat"},
            "27": {"id": "ST000021", "name": "Maharashtra"},
            "29": {"id": "ST000017", "name": "Karnataka"},
            "30": {"id": "ST000011", "name": "Goa"},
            "33": {"id": "ST000031", "name": "Tamil Nadu"},
            "38": {"id": "ST000039", "name": "Ladakh"},
            "96": {"id": "ST000041", "name": "Foreign Country"}
        }

        mapping = STATE_GST_MAPPING.get(state_code_digits, {"id": "", "name": ""})
        state_code = mapping["id"]
        state_name = mapping["name"]

        # Parse/split address cleanly to lines of max 40 chars
        lines = []
        if address.strip():
            words = address.strip().split()
            current_line = []
            current_len = 0
            for word in words:
                added_len = len(word) + (1 if current_line else 0)
                if current_len + added_len > 40:
                    if current_line:
                        lines.append(" ".join(current_line))
                        current_line = [word]
                        current_len = len(word)
                    else:
                        lines.append(word[:40])
                        current_line = [word[40:]]
                        current_len = len(word[40:])
                else:
                    current_line.append(word)
                    current_len += added_len
            if current_line:
                lines.append(" ".join(current_line))

        line1 = lines[0] if len(lines) > 0 else ""
        line2 = lines[1] if len(lines) > 1 else ""
        line3 = " ".join(lines[2:]) if len(lines) > 2 else ""
        line3 = line3[:40]

        pan_val = gstin[2:12] if is_registered and len(gstin) >= 12 else ""

        with self.safe_cdx_context(m01_path):
            t01 = dbf.Table(m01_path)
            t01.open(mode=dbf.READ_WRITE)
            try:
                # Existing Ledger Duplicate Check
                for record in t01:
                    if not dbf.is_deleted(record):
                        rec_name = str(record['FIELD02']).strip().upper()
                        if rec_name == name_up:
                            existing_code = str(record['FIELD01']).strip()
                            t01.close()
                            print(f"[create_party_ledger] Party '{name}' already exists in RKACCM01 with code {existing_code}. Returning existing code.")
                            return existing_code

                existing_codes = {str(r['FIELD01']).strip().upper() for r in t01}
                existing_links = {str(r['FIELD16']).strip().upper() for r in t01 if r['FIELD16']}
                
                def gen_code(prefix, length=8):
                    chars = string.ascii_uppercase + string.digits
                    return f"{prefix}{''.join(random.choices(chars, k=length - len(prefix)))}"

                led_code = gen_code('AY')
                while led_code in existing_codes:
                    led_code = gen_code('AY')
                    
                link_code = gen_code('TY')
                while link_code in existing_links:
                    link_code = gen_code('TY')

                # Write to RKACCM01.DBF
                m01_rec = {
                    'FIELD01': led_code,
                    'FIELD02': name,
                    'FIELD04': 'B',
                    'FIELD05': group_code,
                    'FIELD06': parent_group,
                    'FIELD07': 'PR',
                    'FIELD08': '1',
                    'M01F14': tax_class, # 'R' = Registered, 'U' = Unregistered
                    'FIELD16': link_code,
                    'M01F17': 'O',
                    'FIELD22': 'G',
                    'FIELD23': 'N',
                    'FIELD24': 'N',
                    'FIELD34': pan_val,
                    'FIELD51': state_code,
                    'FIELD55': 'N',
                    'M01F03': 'N',
                    'M01F05': gstin if is_registered else "",
                    'M01F07': '01',
                    'M01F08': '1',
                    'M01F19': 'N',
                    'M01F22': 'Y0000001',
                    'M01F23': 'N',
                    'M01F25': 'P'
                }
                t01.append(self.clean_record_dict(m01_rec, table=t01)) # type: ignore
            finally:
                t01.close()

        # Write to RKACCM02.DBF
        with self.safe_cdx_context(m02_path):
            t02 = dbf.Table(m02_path)
            t02.open(mode=dbf.READ_WRITE)
            try:
                m02_rec = {
                    'FIELD01': led_code,
                    'FIELD02': line1,
                    'FIELD03': line2,
                    'FIELD04': line3,
                    'FIELD05': city.strip()[:25],
                    'FIELD07': pincode.strip()[:8],
                    'FIELD08': link_code,
                    'FIELD43': gstin if is_registered else "", # GSTIN goes here typically or FIELD42
                    'FIELD52': state_code,
                    'FIELD53': state_name,
                    'FIELD61': name,
                    'M02F74': state_code_digits,
                    'FIELD90': 'A'
                }
                t02.append(self.clean_record_dict(m02_rec, table=t02)) # type: ignore
            finally:
                t02.close()

        # Register in RKACCGID.DBF
        self._register_guid('YRM01', led_code, is_header=False)

        # Ledger created strictly in target year_folder (selected/current year)

        print(f"Auto-created new {'B2B' if is_registered else 'B2C'} ledger: {name} ({led_code}) with GSTIN {gstin}")
        return led_code

    def resolve_group_code_from_hint(self, group_hint: str) -> str:
        """Resolves human-readable group hint to exact official Miracle Accounting master group code."""
        if not group_hint:
            return ""
        gh = group_hint.strip().upper()
        if "SUNDRY DEBTORS" in gh or "DEBTOR" in gh or "CUSTOMER" in gh:
            return "G0000009"
        if "SUNDRY CREDITORS" in gh or "CREDITOR" in gh or "SUPPLIER" in gh:
            return "G0000013"
        if "INDIRECT EXPENSE" in gh or "EXPENSE" in gh or "INDIRECT EXP" in gh:
            return "G0000017"
        if "DIRECT EXPENSE" in gh:
            return "G0000014"
        if "INDIRECT INCOME" in gh or "INCOME" in gh:
            return "G0000016"
        if "DIRECT INCOME" in gh:
            return "G0000015"
        if "BANK" in gh or "BANK ACCOUNTS" in gh:
            return "G0000004"
        if "CASH" in gh or "CASH-IN-HAND" in gh:
            return "G0000005"
        if "DUTIES & TAXES" in gh or "TAXES" in gh or "DUTIES" in gh:
            return "G0000003"
        if "SALES" in gh:
            return "G0000011"
        if "PURCHASE" in gh:
            return "G0000012"
        if "CAPITAL" in gh or "DRAWING" in gh:
            return "G0000001"
        if "FIXED ASSETS" in gh or "ASSET" in gh:
            return "G0000006"
        if "UNSECURED LOANS" in gh or "UNSECURED" in gh:
            return "G0000019"
        if "SECURED LOANS" in gh or "SECURED" in gh:
            return "G0000008"
        if "SUSPENSE" in gh:
            return "G0000028"
        return "G0000009"

    def update_party_ledger(self, old_name: str, new_name: str, print_name: str = "", group_code: str = "", gstin: str = "", city: str = "", year_folder: str | None = None) -> str:
        """Updates an existing master ledger record in RKACCM01.DBF with new name, print name, group code, and gstin."""
        MiracleDBFHandler.clear_cross_year_cache(self.client_path)
        old_name_up = old_name.strip().upper()
        new_name = new_name.strip()[:60]
        if not print_name:
            print_name = new_name
        print_name = print_name.strip()[:60]

        if not year_folder:
            year_folder = self.get_latest_year_folder()

        m01_path = self._get_table_path('RKACCM01.DBF', year_folder)
        if not os.path.exists(m01_path):
            m01_path = self._get_table_path('rkaccm01.dbf', year_folder)

        if not os.path.exists(m01_path):
            raise FileNotFoundError(f"RKACCM01.DBF table not found at {m01_path}")

        import dbf
        target_code = ""

        with self.safe_cdx_context(m01_path):
            t01 = dbf.Table(m01_path)
            t01.open(mode=dbf.READ_WRITE)
            try:
                for record in t01:
                    if not dbf.is_deleted(record):
                        rec_name = str(record['FIELD02']).strip().upper()
                        rec_code = str(record['FIELD01']).strip().upper()
                        if rec_name == old_name_up or rec_code == old_name_up:
                            dbf.write(record, FIELD02=new_name)
                            if group_code:
                                dbf.write(record, FIELD05=group_code)
                            if gstin:
                                dbf.write(record, M01F05=gstin)
                            target_code = str(record['FIELD01']).strip()
                            print(f"[update_party_ledger] Updated ledger '{old_name}' -> '{new_name}' ({target_code}) in RKACCM01.DBF")
                            break
            finally:
                t01.close()

        # Update RKACCM02.DBF if target_code was found
        m02_path = self._get_table_path('RKACCM02.DBF', year_folder)
        if not os.path.exists(m02_path): m02_path = self._get_table_path('rkaccm02.dbf', year_folder)
        if target_code and os.path.exists(m02_path):
            with self.safe_cdx_context(m02_path):
                t02 = dbf.Table(m02_path)
                t02.open(mode=dbf.READ_WRITE)
                try:
                    for record in t02:
                        if not dbf.is_deleted(record) and str(record['FIELD01']).strip().upper() == target_code.upper():
                            if print_name:
                                dbf.write(record, FIELD61=print_name)
                            if city:
                                dbf.write(record, FIELD05=city.strip()[:25])
                            if gstin:
                                dbf.write(record, FIELD43=gstin)
                            break
                finally:
                    t02.close()

        if not target_code:
            # If old_name was a raw narration or uncreated party, create it as a new master ledger
            print(f"[update_party_ledger] Ledger '{old_name}' not found in RKACCM01.DBF. Creating new ledger '{new_name}'...")
            target_code = self.create_party_ledger(
                name=new_name,
                module="Bank Statements",
                gstin=gstin,
                city=city,
                year_folder=year_folder,
                explicit_group_code=group_code
            )

        return target_code

    def update_party_ledger_details(self, party_code: str, gstin: str = "", address: str = "", city: str = "", pincode: str = "", year_folder: str | None = None):
        """Checks and updates the party ledger's address, city, pincode, and GSTIN/PAN in RKACCM01/02 if they are missing or differ."""
        gstin = gstin.strip().upper()[:15]

        if not year_folder:
            year_folder = self.get_latest_year_folder()
            
        m01_path = self._get_table_path('RKACCM01.DBF', year_folder)
        m02_path = self._get_table_path('RKACCM02.DBF', year_folder)
        
        # Check case variation
        if not os.path.exists(m01_path): m01_path = self._get_table_path('rkaccm01.dbf', year_folder)
        if not os.path.exists(m02_path): m02_path = self._get_table_path('rkaccm02.dbf', year_folder)
        
        if not os.path.exists(m01_path) or not os.path.exists(m02_path):
            return
            
        import dbf
        
        # 1. Update RKACCM02.DBF (Address details)
        updated_m02 = False
        with self.safe_cdx_context(m02_path):
            t02 = dbf.Table(m02_path)
            t02.open(mode=dbf.READ_WRITE)
            try:
                for row in t02:
                    if row['FIELD01'].strip().upper() == party_code.strip().upper(): # type: ignore
                        # Split address if provided
                        lines = []
                        if address.strip():
                            words = address.strip().split()
                            current_line = []
                            current_len = 0
                            for word in words:
                                added_len = len(word) + (1 if current_line else 0)
                                if current_len + added_len > 40:
                                    if current_line:
                                        lines.append(" ".join(current_line))
                                        current_line = [word]
                                        current_len = len(word)
                                    else:
                                        lines.append(word[:40])
                                        current_line = [word[40:]]
                                        current_len = len(word[40:])
                                else:
                                    current_line.append(word)
                                    current_len += added_len
                            if current_line:
                                lines.append(" ".join(current_line))
                        
                        line1 = lines[0] if len(lines) > 0 else ""
                        line2 = lines[1] if len(lines) > 1 else ""
                        line3 = " ".join(lines[2:]) if len(lines) > 2 else ""
                        line3 = line3[:40]
                        
                        updates = {}
                        
                        # Determine if we should update address lines
                        # If existing are empty or if we have new address, let's update them
                        if line1 and line1.strip() != str(row['FIELD02']).strip():
                            updates['FIELD02'] = line1
                        if line2 and line2.strip() != str(row['FIELD03']).strip():
                            updates['FIELD03'] = line2
                        if line3 and line3.strip() != str(row['FIELD04']).strip():
                            updates['FIELD04'] = line3
                            
                        # Update City if empty or differs
                        city_clean = city.strip()[:25]
                        if city_clean and city_clean != str(row['FIELD05']).strip():
                            updates['FIELD05'] = city_clean
                            
                        # Update Pincode if empty or differs
                        pincode_clean = pincode.strip()[:8]
                        if pincode_clean and pincode_clean != str(row['FIELD07']).strip():
                            updates['FIELD07'] = pincode_clean
                            
                        # Update GSTIN if empty or differs
                        if gstin.strip() and gstin.strip() != str(row['FIELD43']).strip():
                            updates['FIELD43'] = gstin.strip()
                            
                        if updates:
                            dbf.write(row, **self.clean_record_dict(updates))
                            updated_m02 = True
                        break
            finally:
                t02.close()
                
        # 2. Update RKACCM01.DBF (GSTIN/PAN/Tax Class details)
        if gstin.strip():
            is_registered = len(gstin.strip()) >= 15
            tax_class = 'R' if is_registered else 'U'
            pan_val = gstin.strip()[2:12] if is_registered else ""
            
            with self.safe_cdx_context(m01_path):
                t01 = dbf.Table(m01_path)
                t01.open(mode=dbf.READ_WRITE)
                try:
                    for row in t01:
                        if row['FIELD01'].strip().upper() == party_code.strip().upper(): # type: ignore
                            updates_m01 = {}
                            if tax_class != str(row['M01F14']).strip():
                                updates_m01['M01F14'] = tax_class
                            if gstin.strip() != str(row['M01F05']).strip():
                                updates_m01['M01F05'] = gstin.strip()
                            if pan_val and pan_val != str(row['FIELD34']).strip():
                                updates_m01['FIELD34'] = pan_val
                                
                            if updates_m01:
                                dbf.write(row, **self.clean_record_dict(updates_m01))
                            break
                finally:
                    t01.close()
                    
        if updated_m02:
            print(f"Dynamically updated details for party {party_code} in RKACCM02/01.")
            
    def get_or_create_gst_commodity(self, hsn: str, gst_pct: float, is_service: bool, year_folder: str | None = None) -> str:
        """
        Checks if HSN code is already registered in RKACCM14.DBF.
        If not, creates it and registers it in RKACCM18.DBF and RKACCGID.DBF.
        Returns the commodity code.
        """

        if not year_folder:
            year_folder = self.get_latest_year_folder()
            
        m14_path = self._get_table_path('RKACCM14.DBF', year_folder)
        if not os.path.exists(m14_path): m14_path = self._get_table_path('rkaccm14.dbf', year_folder)
        m18_path = self._get_table_path('RKACCM18.DBF', year_folder)
        if not os.path.exists(m18_path): m18_path = self._get_table_path('rkaccm18.dbf', year_folder)
        
        if not os.path.exists(m14_path) or not os.path.exists(m18_path):
            print("Warning: Commodity tables not found, falling back to generic commodity")
            return "CNGT" if gst_pct <= 0 else "C004"
            
        import dbf
        import random
        import string
        from datetime import date
        
        hsn_clean = hsn.strip()
        if not hsn_clean or hsn_clean == 'XXXXXXXX':
            return "CNGT" if gst_pct <= 0 else "C004"
            
        # 1. Search for existing commodity matching this HSN in RKACCM14
        try:
            m14 = dbf.Table(m14_path)
            m14.open(mode=dbf.READ_WRITE)
            for r in m14:
                if dbf.is_deleted(r): continue
                if str(r['M14F04']).strip() == hsn_clean:
                    code = str(r['M14F01']).strip()
                    m14.close()
                    return code
            m14.close()
        except Exception as e:
            print(f"Error searching RKACCM14: {e}")
            
        # 2. Fallback to standard, fully-supported pre-existing commodity codes in Miracle.
        # This prevents invalid commodity code errors and completely eliminates red text bugs.
        pct = gst_pct
        if pct <= 0:
            commodity_code = "CNGT"
        elif pct <= 3:
            commodity_code = "C006"
        elif pct <= 5:
            commodity_code = "C002"
        elif pct <= 12:
            commodity_code = "C003"
        elif pct <= 18:
            commodity_code = "C004"
        else:
            commodity_code = "C005"
            
        print(f"Fallback standard GST Commodity selected for HSN {hsn_clean}: {commodity_code} (GST: {pct}%)")
        return commodity_code

    def find_dynamic_product_for_gst(self, gst_pct: float, module: str = "Purchases", year_folder: str | None = None) -> str:
        """Finds a product in RKACCM21.DBF matching the given GST rate."""
        products = self.read_products(year_folder=year_folder)
        if products:
            g_int = str(int(gst_pct))
            # 1. Match product name containing GST percentage string (e.g. "5%", "GST 5", "(5%)")
            for prod in products:
                p_name = prod.get("name", "").strip()
                p_up = p_name.upper()
                if f"{g_int}%" in p_up or f"GST {g_int}" in p_up or f"GST{g_int}" in p_up or f" {g_int}%" in p_up or f"({g_int}%)" in p_up:
                    return p_name
            # 2. Match product by commodity code corresponding to gst_pct (e.g. C002 for 5%, C004 for 18%)
            expected_comm = "CNGT" if gst_pct <= 0 else ("C002" if gst_pct <= 5 else ("C003" if gst_pct <= 12 else ("C004" if gst_pct <= 18 else "C005")))
            for prod in products:
                comm = str(prod.get("commodity") or prod.get("commodity_code") or prod.get("M21F27") or "").strip().upper()
                if comm == expected_comm:
                    p_name = prod.get("name", "").strip()
                    if p_name: return p_name
        default_base = "SALES" if module == "Sales" else "PURCHASES"
        return f"{default_base} GST {int(gst_pct)}%" if gst_pct > 0 else f"{default_base} EXEMPT"

    def get_or_create_product(self, product_name: str, hsn: str = "", uom: str = "", gst_pct: float = 18.0, year_folder: str | None = None) -> str:
        """Finds a product by name in RKACCM21 or auto-creates it if it doesn't exist."""
        # Extract explicit GST percentage from product name if present (e.g. footwear Gst 0 -> 0.0)
        extracted_pct = self._extract_gst_from_name(product_name)
        pct_to_use = gst_pct if extracted_pct is None else extracted_pct

        if not year_folder:
            year_folder = self.get_latest_year_folder()
            
        m21_path = self._get_table_path('RKACCM21.DBF', year_folder)
        if not os.path.exists(m21_path): m21_path = self._get_table_path('rkaccm21.dbf', year_folder)
        
        if not os.path.exists(m21_path):
            return 'P0000001'
            
        import dbf
        import random
        import string

        if not product_name or product_name.upper() in ("AUTO_CREATE_PRODUCT", "AUTO_CREATE", "AUTO_CREATE_PRODUCT_B2B", "AUTO_CREATE_PRODUCT_B2C") or product_name.upper().startswith("UNKNOWN_ITEM"):
            resolved_prod = self.find_dynamic_product_for_gst(pct_to_use, module="Purchases", year_folder=year_folder)
            search_name = (resolved_prod or f"PURCHASES GST {int(pct_to_use)}%").strip().upper()[:40]
        else:
            search_name = product_name.strip().upper()[:40]
        
        # UQC Mapping dictionary
        UQC_MAPPING = {
            "NOS": "NOS-NUMBERS",
            "NUMBER": "NOS-NUMBERS",
            "NUMBERS": "NOS-NUMBERS",
            "PCS": "PCS-PIECES",
            "PIECE": "PCS-PIECES",
            "PIECES": "PCS-PIECES",
            "KG": "KGS-KILOGRAMS",
            "KGS": "KGS-KILOGRAMS",
            "KILOGRAM": "KGS-KILOGRAMS",
            "KILOGRAMS": "KGS-KILOGRAMS",
            "BOX": "BOX-BOX",
            "BOXES": "BOX-BOX",
            "BAG": "BAG-BAGS",
            "BAGS": "BAG-BAGS",
            "BTL": "BTL-BOTTLES",
            "BOTTLE": "BTL-BOTTLES",
            "BOTTLES": "BTL-BOTTLES",
            "LTR": "LTR-LITRES",
            "LITRE": "LTR-LITRES",
            "LITRES": "LTR-LITRES",
            "MTR": "MTR-METERS",
            "METER": "MTR-METERS",
            "METERS": "MTR-METERS",
            "SET": "SET-SETS",
            "SETS": "SET-SETS",
            "TON": "TON-TONNES",
            "TONS": "TON-TONNES",
            "TONNES": "TON-TONNES",
            "UNT": "UNT-UNITS",
            "UNIT": "UNT-UNITS",
            "UNITS": "UNT-UNITS",
            "OTH": "OTH-OTHERS",
            "OTHERS": "OTH-OTHERS",
            "SAC": "OTH-OTHERS"
        }
        
        uom_clean = uom.strip().upper()
        hsn_clean = hsn.strip()
        is_service = False
        if hsn_clean.startswith("99"):
            is_service = True
        else:
            service_keywords = ["SERVICE", "FEES", "CHARGE", "LABOUR", "AMC", "RENT", "MAINTENANCE", "TRANSPORT", "CONSULTING", "COMMISSION"]
            if any(keyword in search_name for keyword in service_keywords):
                is_service = True
                
        comm_type = 'S' if is_service else 'G'
        
        if uom_clean:
            uqc_str = UQC_MAPPING.get(uom_clean, "OTH-OTHERS" if is_service else "UNT-UNITS")
        else:
            uqc_str = "OTH-OTHERS" if is_service else "UNT-UNITS"
            
        short_uom = uom_clean if uom_clean in ["PCS", "NOS", "KG", "KGS", "BAG", "BOX", "BTL", "LTR", "MTR", "SET", "TON", "UNT"] else ("OTH" if is_service else "UNT")

        pct = pct_to_use
        if hsn_clean and hsn_clean != 'XXXXXXXX':
            commodity_code = self.get_or_create_gst_commodity(hsn_clean, pct, is_service, year_folder)
        else:
            if pct <= 0:
                commodity_code = "CNGT"
            elif pct <= 3:
                commodity_code = "C006"
            elif pct <= 5:
                commodity_code = "C002"
            elif pct <= 12:
                commodity_code = "C003"
            elif pct <= 18:
                commodity_code = "C004"
            else:
                commodity_code = "C005"

        # 1. Search for existing product (Exact or Space/Punctuation-insensitive) safely under CDX bypass
        def clean_an(s): return re.sub(r'[^A-Z0-9]', '', str(s).upper())
        search_an = clean_an(search_name)
        
        existing_code = None
        with self.safe_cdx_context(m21_path):
            try:
                m21 = dbf.Table(m21_path)
                m21.open(mode=dbf.READ_WRITE)
                for r in m21:
                    try:
                        if dbf.is_deleted(r): continue
                        r_name = str(r['FIELD02']).strip().upper()
                        r_an = clean_an(r_name)
                        
                        if r_name == search_name or (search_an and r_an == search_an):
                            existing_code = str(r['FIELD01']).strip()
                            
                            # Check if existing product fields are empty, CNGT, or mismatching, and update them
                            current_commodity = str(r['M21F27']).strip()
                            current_uqc = str(r['M21F28']).strip()
                            current_m21f26 = str(r['M21F26']).strip()
                            current_m21f31 = str(r['M21F31']).strip()
                            current_field52 = str(r['FIELD52']).strip()
                            current_field53 = str(r['FIELD53']).strip()
                            current_m21f07 = str(r['M21F07']).strip() if 'M21F07' in m21.field_names else ''
                            current_m21f08 = str(r['M21F08']).strip() if 'M21F08' in m21.field_names else ''
                            
                            needs_update = False
                            update_kwargs = {}
                            
                            if extracted_pct is not None:
                                if current_commodity != commodity_code:
                                    update_kwargs['M21F27'] = commodity_code
                                    needs_update = True
                            else:
                                if current_commodity == '':
                                    update_kwargs['M21F27'] = commodity_code
                                    needs_update = True
                                
                            if current_uqc == '' or current_uqc != uqc_str:
                                update_kwargs['M21F28'] = uqc_str.ljust(25)
                                needs_update = True
                                
                            if current_m21f26 == '' or current_m21f26 != comm_type:
                                update_kwargs['M21F26'] = comm_type
                                needs_update = True

                            if 'M21F07' in m21.field_names and current_m21f07 == '':
                                update_kwargs['M21F07'] = 'L0000001'
                                needs_update = True

                            if 'M21F08' in m21.field_names and current_m21f08 == '':
                                update_kwargs['M21F08'] = 'L0000005'
                                needs_update = True
                                
                            if hsn and (current_m21f31 == '' or current_m21f31 == 'XXXXXXXX' or current_m21f31 != hsn):
                                update_kwargs['M21F31'] = hsn.ljust(8)
                                needs_update = True

                            if current_field52 != 'N':
                                update_kwargs['FIELD52'] = 'N'
                                needs_update = True

                            if current_field53 != 'N':
                                update_kwargs['FIELD53'] = 'N'
                                needs_update = True
                                
                            if needs_update:
                                dbf.write(r, **self.clean_record_dict(update_kwargs))
                                print(f"Updated existing product '{search_name}' fields: {update_kwargs}")
                                
                            break
                    except Exception as ex:
                        print(f"Error processing record during M21 search: {ex}")
                        continue
                m21.close()
            except Exception as e:
                print(f"Error searching/updating M21: {e}")
                
        if existing_code:
            return existing_code

        # 2. Create new product with sequential Miracle code structure (e.g. P0000001)
        try:
            with self.safe_cdx_context(m21_path):
                m21 = dbf.Table(m21_path)
                m21.open(mode=dbf.READ_WRITE)
                try:
                    max_num = 0
                    pfx = 'P'
                    template_rec = None
                    for r in m21:
                        if not dbf.is_deleted(r):
                            if template_rec is None: template_rec = r
                            c_val = str(r['FIELD01']).strip().upper()
                            if len(c_val) >= 2 and c_val[0] in ('P', 'I') and c_val[1:].isdigit():
                                pfx = c_val[0]
                                max_num = max(max_num, int(c_val[1:]))
                    
                    new_code = f"{pfx}{max_num + 1:07d}"
                    
                    new_rec = {
                        'FIELD01': new_code,
                        'FIELD02': search_name,
                        'FIELD05': "".ljust(20),
                        'FIELD06': "".ljust(20),
                        'FIELD07': 1.0,
                        'FIELD10': 1.0,
                        'FIELD13': 'F',
                        'FIELD18': 1.0,
                        'FIELD20': template_rec['FIELD20'] if template_rec else 'VIB00001',
                        'M21F23': 'I',
                        'M21F24': 'N',
                        'FIELD28': 0.0,
                        'M21F29': 'D',
                        'M21F30': 'Y',
                        'FIELD34': 'N',
                        'FIELD40': "".ljust(15), # Empty Alias
                        'FIELD51': 'N',
                        'FIELD52': 'N',
                        'FIELD53': 'N',
                        'FIELD57': 'N',
                        'FIELD58': 'Y',
                        'FIELD59': 'N',
                        'FIELD65': 'N',
                        'FIELD72': 'N',
                        'FIELD76': 'CL_STOCK',
                        'FIELD77': 'G000030G',
                        'M21F07': 'L0000001',
                        'M21F08': 'L0000005',
                        'M21F27': commodity_code,
                        'M21F26': comm_type,
                        'M21F28': uqc_str.ljust(25),
                        'M21F31': hsn.ljust(8) if hsn else 'XXXXXXXX'
                    }
                    m21.append(self.clean_record_dict(new_rec, table=m21)) # type: ignore
                finally:
                    m21.close()
                    
            # Register in RKACCGID
            self._register_guid('YRM21', new_code, is_header=False)
            
            print(f"Created new Product: {search_name} -> {new_code} (HSN: {hsn}, UOM: {short_uom}, UQC: {uqc_str}, Commodity: {commodity_code})")
            return new_code
            
        except Exception as e:
            print(f"Failed to create Product {search_name}: {e}")
            return 'P0000001'

    def detect_format_settings(self, year_folder: str, voucher_types: list) -> dict:
        """
        Scans current and historical year folders to find the most common FIELD14 (format template)
        and T41F83 (format series option) used by the client for the specified voucher types.
        This ensures custom layouts or changes in formatting are automatically aligned with backdata.
        """
        import dbf
        import os
        from collections import Counter

        format_counter = Counter()
        f83_counter = Counter()

        # Build list of year folders to scan, current first, then descending
        current_yf = year_folder.upper() if year_folder else self.get_latest_year_folder().upper()
        all_folders = self._get_all_year_folders()
        other_folders = [y for y in all_folders if y.upper() != current_yf]
        other_folders.sort(reverse=True)
        folders_to_scan = [current_yf] + other_folders

        v_types_upper = [vt.upper() for vt in voucher_types]

        for yr in folders_to_scan:
            t41_path = self._get_table_path('RKACCT41.DBF', yr)
            if not os.path.exists(t41_path):
                t41_path = self._get_table_path('rkacct41.dbf', yr)
            if not os.path.exists(t41_path):
                continue

            try:
                with self.safe_cdx_context(t41_path):
                    table = dbf.Table(t41_path)
                    table.open(mode=dbf.READ_ONLY)
                    for r in table:
                        if dbf.is_deleted(r):
                            continue
                        f98 = str(r['FIELD98']).strip().upper()
                        # Match prefix (e.g. 'SS') or exact type
                        if f98[:2] in v_types_upper or f98 in v_types_upper:
                            f14 = str(r['FIELD14']).strip().upper() if 'FIELD14' in table.field_names else 'N'
                            f83 = str(r['T41F83']).strip() if 'T41F83' in table.field_names else ''
                            if f14 and f14 in ('A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'N'):
                                format_counter[f14] += 1
                            if f83:
                                f83_counter[f83] += 1
                    table.close()
            except Exception as e:
                print(f"Error scanning format in {yr}: {e}")

            # If we found at least some records, stop scanning older years
            if format_counter or f83_counter:
                break

        # Defaults if no history found
        detected_format = format_counter.most_common(1)[0][0] if format_counter else 'N'
        detected_f83 = f83_counter.most_common(1)[0][0] if f83_counter else '2'

        # Ensure correct FoxPro padding for T41F83 (length 4 string)
        if len(detected_f83) < 4:
            detected_f83 = f"{detected_f83:>4}"

        return {
            "format": detected_format,
            "f83": detected_f83
        }

    def auto_discover_prefixes(self, year_folder: str | None = None, force_separate: bool = False) -> dict:
        """
        Scans the DBF files to auto-discover the most used sales and purchase prefixes.
        
        Args:
            year_folder: If provided, only scan that year. Otherwise scans all years.
            force_separate: If True, scan ALL year folders to find separate sales and
                            purchase prefixes (instead of stopping at first year with data).
                            Use this when a company has only purchase history in recent years
                            but may have sales entries in older years.
        """
        import dbf
        from collections import Counter
        
        sales_counter = Counter()
        purchase_counter = Counter()
        sales_f03_counter = Counter()
        purchase_f03_counter = Counter()

        folders_to_scan = [year_folder] if year_folder else self._get_all_year_folders()
        # Sort folders descending (YR27, YR26, YR25) to scan newest first
        folders_to_scan.sort(reverse=True)
        
        for yr in folders_to_scan:
            t41_path = self._get_table_path('RKACCT41.DBF', yr)
            if not os.path.exists(t41_path):
                t41_path = self._get_table_path('rkacct41.dbf', yr)
                
            if not os.path.exists(t41_path):
                continue
                
            try:
                table = dbf.Table(t41_path)
                table.open(mode=dbf.READ_ONLY)
                
                # Read backwards to get the most recent data quickly
                # Scan last 3000 records (increased from 2000 for better coverage)
                total_records = len(table)
                start_idx = max(0, total_records - 3000)
                
                for i in range(total_records - 1, start_idx - 1, -1):
                    try:
                        r = table[i]
                    except Exception:
                        continue
                    
                    try:
                        if dbf.is_deleted(r):
                            continue
                    except:
                        pass
                        
                    try:
                        field03 = r['FIELD03']
                    except Exception:
                        continue
                        
                    if field03 is None:
                        continue
                        
                    try:
                        f3_val = int(str(field03).strip() or 0)
                    except (ValueError, TypeError):
                        continue
                        
                    try:
                        f98 = str(r['FIELD98']).strip()
                        f99 = str(r['FIELD99']).strip()
                    except Exception:
                        continue
                        
                    if not f98:
                        continue
                        
                    prefix = f"{f98},{f99}" if f99 else f"{f98},{f98}"
                    
                    if f98[:2] in ('SS', 'SL', 'SR', 'SA', 'SB', 'SC', 'SD'):
                        sales_counter[prefix] += 1
                    elif f98[:2] in ('PP', 'PB', 'PU', 'PI', 'PO', 'PA'):
                        purchase_counter[prefix] += 1
                        
                table.close()
            except Exception as e:
                print(f"Error scanning {yr} DBF for auto-discovery: {e}")

            if not force_separate:
                # Stop at first year that has ANY data (original behaviour)
                if sales_counter or purchase_counter:
                    break
            else:
                # In force_separate mode: keep scanning all years to find both separately.
                # Stop only when BOTH sales and purchase prefixes are found.
                if sales_counter and purchase_counter:
                    break

        # ── Detect FIELD03 setup IDs (per-client) ────────────────────────────
        # Scan all year folders to find the actual FIELD03 used by SS-prefix sales
        # and PP-prefix purchases in this company's history.
        SALES_STARTS_F03 = ('SS', 'SL', 'SR', 'SA', 'SB', 'SC', 'SD')
        PURCH_STARTS_F03 = ('PP', 'PB', 'PU', 'PI', 'PO', 'PA')
        for yr in folders_to_scan:
            t41_p2 = self._get_table_path('RKACCT41.DBF', yr)
            if not os.path.exists(t41_p2):
                t41_p2 = self._get_table_path('rkacct41.dbf', yr)
            if not os.path.exists(t41_p2):
                continue
            try:
                import dbf as _dbf2
                tbl2 = _dbf2.Table(t41_p2)
                tbl2.open(mode=_dbf2.READ_ONLY)
                total2 = len(tbl2)
                start2 = max(0, total2 - 2000)
                for i in range(total2 - 1, start2 - 1, -1):
                    try:
                        r2 = tbl2[i]
                        if _dbf2.is_deleted(r2): continue
                    except:
                        continue
                    try:
                        f98_2 = str(r2['FIELD98']).strip().upper()
                        f3_2  = r2['FIELD03']
                        if f3_2 is None: continue
                        f3i_2 = int(f3_2) # type: ignore
                        if f98_2[:2] in SALES_STARTS_F03 and f3i_2 != 2:
                            sales_f03_counter[f3i_2] += 1
                        elif f98_2[:2] in PURCH_STARTS_F03 and f3i_2 != 2:
                            purchase_f03_counter[f3i_2] += 1
                    except:
                        continue
                tbl2.close()
            except Exception as e2:
                print(f"FIELD03 detection error in {yr}: {e2}")

        # Pick the most common FIELD03 setup ID for each module type
        sales_setup_id = sales_f03_counter.most_common(1)[0][0] if sales_f03_counter else 5
        # Default for purchase is 6 (confirmed from native Miracle data across all CMP clients)
        purchase_setup_id = purchase_f03_counter.most_common(1)[0][0] if purchase_f03_counter else 6

        # Safety clamps removed to allow custom setup IDs
        # ─────────────────────────────────────────────────────────────────────

        # Get the most common prefix for each module separately.
        # SAFETY: Never return a purchase-pattern prefix as the sales_prefix, and vice versa.
        PURCHASE_STARTS = ('PP', 'PB', 'PU', 'PI', 'PO', 'PA')
        SALES_STARTS = ('SS', 'SL', 'SR', 'SA', 'SB', 'SC', 'SD')

        def _pick_best(counter, preferred_starts, fallback):
            """Pick best prefix from counter that starts with preferred patterns."""
            # First try to find a match with preferred starts
            for prefix, _ in counter.most_common():
                parts = [p.strip().upper() for p in prefix.split(',')]
                if any(p[:2] in preferred_starts for p in parts if len(p) >= 2):
                    return prefix
            # If no preferred match, return most common regardless
            if counter:
                return counter.most_common(1)[0][0]
            return fallback

        sales_prefix = _pick_best(sales_counter, SALES_STARTS, "SS,SS")
        purchase_prefix = _pick_best(purchase_counter, PURCHASE_STARTS, "PP,PP")
        
        print(f"Auto-discovered: sales_prefix='{sales_prefix}' purchase_prefix='{purchase_prefix}' "
              f"sales_setup_id={sales_setup_id} purchase_setup_id={purchase_setup_id} "
              f"(from {sum(sales_counter.values())} sales + {sum(purchase_counter.values())} purchase records)")
        
        return {
            "sales_prefix": sales_prefix,
            "purchase_prefix": purchase_prefix,
            "sales_setup_id": sales_setup_id,
            "purchase_setup_id": purchase_setup_id
        }

    def detect_bill_formats(self) -> dict:
        """
        Scans the most recent DBF entries to detect the bill number format pattern 
        (e.g. PSPL/{num}/2026-27) and the highest sequence number for Sales and Purchases.
        """
        import re
        from collections import defaultdict
        
        sales_bills = set()
        purch_bills = set()
        
        folders_to_scan = self._get_all_year_folders()
        folders_to_scan.sort(reverse=True)
        
        SALES_STARTS = ('SS', 'SL', 'SR', 'SA', 'SB', 'SC', 'SD')
        PURCH_STARTS = ('PP', 'PB', 'PU', 'PI', 'PO', 'PA')

        for yr in folders_to_scan:
            t41_path = self._get_table_path('RKACCT41.DBF', yr)
            if not os.path.exists(t41_path):
                t41_path = self._get_table_path('rkacct41.dbf', yr)
            if not os.path.exists(t41_path):
                continue
                
            try:
                import dbf
                table = dbf.Table(t41_path)
                table.open(mode=dbf.READ_ONLY)
                
                total = len(table)
                start_idx = max(0, total - 1000)
                
                for i in range(total - 1, start_idx - 1, -1):
                    try:
                        r = table[i]
                        if dbf.is_deleted(r): continue
                    except: continue
                    
                    try:
                        f98 = str(r['FIELD98']).strip().upper()
                        f3 = r['FIELD03']
                        if f3 is None: continue
                        f3i = int(f3) # type: ignore
                        b_no = str(r['T41FVNO']).strip()
                        if not b_no: continue
                        
                        if f98[:2] in SALES_STARTS and f3i not in [2]:
                            sales_bills.add(b_no)
                        elif f98[:2] in PURCH_STARTS and f3i not in [2]:
                            purch_bills.add(b_no)
                            
                    except Exception:
                        continue
                        
                table.close()
                
                # If we have enough bills from the newest year, stop scanning older years
                if len(sales_bills) >= 5 and len(purch_bills) >= 5:
                    break
            except Exception as e:
                print(f"Error scanning {yr} for bill formats: {e}")

        def extract_pattern(bills):
            if not bills:
                return "{num}", 0
            
            def tokenize(s):
                return re.split(r'(\d+)', s)
                
            tokenized_bills = [tokenize(b) for b in bills]
            
            lengths = defaultdict(list)
            for tb in tokenized_bills:
                lengths[len(tb)].append(tb)
                
            if not lengths:
                return "{num}", 0
                
            best_len = max(lengths.keys(), key=lambda k: len(lengths[k]))
            common_bills = lengths[best_len]
            
            if len(common_bills) < 2:
                tb = common_bills[0]
                idx_to_replace = -1
                for i in range(len(tb)-1, -1, -1):
                    if tb[i].isdigit():
                        idx_to_replace = i
                        break
                if idx_to_replace == -1:
                    return "{num}", 0
                
                prefix = "".join(tb[:idx_to_replace])
                suffix = "".join(tb[idx_to_replace+1:])
                seq = int(tb[idx_to_replace])
                padding = len(tb[idx_to_replace])
                if tb[idx_to_replace].startswith('0'):
                    return f"{prefix}{{num:0{padding}d}}{suffix}", seq
                return f"{prefix}{{num}}{suffix}", seq
                
            variances = {}
            for i in range(best_len):
                if common_bills[0][i].isdigit():
                    vals = [int(b[i]) for b in common_bills]
                    variances[i] = max(vals) - min(vals)
                    
            if not variances:
                return "{num}", 0
                
            seq_idx = max(variances.keys(), key=lambda k: variances[k])
            
            latest_bill = max(common_bills, key=lambda b: int(b[seq_idx]))
            
            prefix = "".join(latest_bill[:seq_idx])
            suffix = "".join(latest_bill[seq_idx+1:])
            seq = int(latest_bill[seq_idx])
            
            padding = len(latest_bill[seq_idx])
            if latest_bill[seq_idx].startswith('0'):
                pattern = f"{prefix}{{num:0{padding}d}}{suffix}"
            else:
                pattern = f"{prefix}{{num}}{suffix}"
                
            return pattern, seq

        sales_pattern, sales_last_no = extract_pattern(sales_bills)
        purch_pattern, purch_last_no = extract_pattern(purch_bills)
        
        print(f"Detected Sales Bill Format: pattern='{sales_pattern}', last_no={sales_last_no}")
        print(f"Detected Purch Bill Format: pattern='{purch_pattern}', last_no={purch_last_no}")

        return {
            "sales_bill_format": sales_pattern,
            "sales_last_bill_number": sales_last_no,
            "purchase_bill_format": purch_pattern,
            "purchase_last_bill_number": purch_last_no
        }

    def _get_all_year_folders(self) -> list:
        if not os.path.exists(self.client_path):
            return []
        import re
        folders = []
        try:
            for item in os.listdir(self.client_path):
                full_path = os.path.join(self.client_path, item)
                if os.path.isdir(full_path) and re.match(r'^YR\d+$', item, re.IGNORECASE):
                    folders.append(item.upper())
        except Exception:
            pass
        return folders

    def get_year_folder_for_date(self, d: date) -> str:
        """Determines the correct YRxx folder based on Indian Financial Year start year (Miracle naming convention)."""
        if d.month >= 4:
            fy_start = d.year
        else:
            fy_start = d.year - 1
            
        target_yr = f"YR{str(fy_start)[-2:]}"
        all_yrs = self._get_all_year_folders()
        if target_yr in all_yrs:
            return target_yr
            
        latest = self.get_latest_year_folder()
        return latest if latest else target_yr

    def _open_table_with_retry(self, table, mode, max_retries=5, base_delay=0.2):
        """
        Opens a dbf.Table instance with exponential backoff retries if it is locked.
        """
        import time
        for attempt in range(max_retries):
            try:
                table.open(mode=mode)
                return
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                delay = base_delay * (2 ** attempt)
                print(f"⚠️ Table {table.filename} is locked by another process (Wine/Miracle). Retrying open in {delay:.2f}s... (Attempt {attempt+1}/{max_retries})")
                time.sleep(delay)

    @contextlib.contextmanager
    def safe_cdx_context(self, dbf_path):
        """
        Temporarily clears bit 0 (CDX flag 0x01) from byte 28 of a DBF header
        during python DBF writes, so python's dbf library doesn't corrupt or complain
        about CDX index files. Restores the exact original byte 28 value upon exit.
        
        Upgraded to preserve FPT memo file flags (0x02) and support multi-byte table flags (0x03).
        """
        import time
        if not os.path.exists(dbf_path):
            yield
            return

        cdx_path = dbf_path.replace('.DBF', '.CDX').replace('.dbf', '.cdx')
        has_cdx = os.path.exists(cdx_path)
        orig_byte28 = None
        
        max_retries = 5
        base_delay = 0.2  # 200ms
        
        if has_cdx:
            for attempt in range(max_retries):
                try:
                    with open(dbf_path, 'r+b') as f:
                        f.seek(28)
                        orig_byte28 = f.read(1)
                        if orig_byte28 and (orig_byte28[0] & 0x01):
                            # Temporarily strip ONLY the CDX bit (0x01) while preserving FPT bit (0x02)
                            new_byte28 = bytes([orig_byte28[0] & ~0x01])
                            f.seek(28)
                            f.write(new_byte28)
                    break  # Success, exit retry loop
                except (IOError, PermissionError) as e:
                    if attempt == max_retries - 1:
                        print(f"❌ Failed to acquire lock for CDX flag modification on {dbf_path} after {max_retries} attempts.")
                        raise RuntimeError(f"Miracle DBF table '{os.path.basename(dbf_path)}' is currently open in Miracle Accounting desktop software. Please close the company window in Miracle desktop software and try again.")
                    delay = base_delay * (2 ** attempt)
                    print(f"⚠️ File {dbf_path} is locked by Wine/Miracle. Retrying CDX bypass in {delay:.2f}s... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(delay)
                    
        try:
            yield
        finally:
            if orig_byte28 and (orig_byte28[0] & 0x01) and os.path.exists(dbf_path):
                for attempt in range(max_retries):
                    try:
                        with open(dbf_path, 'r+b') as f:
                            f.seek(28)
                            f.write(orig_byte28)  # Restore EXACT original byte28 value (e.g. 0x03 or 0x01)
                        break
                    except (IOError, PermissionError) as e:
                        if attempt == max_retries - 1:
                            print(f"❌ Failed to restore CDX flag on {dbf_path} after {max_retries} attempts. Database might require manual re-indexing.")
                        delay = base_delay * (2 ** attempt)
                        time.sleep(delay)

    def heal_cdx_header_flags(self, year_folder: str = None) -> int:
        return self.ensure_cdx_flags_active(year_folder)

    def ensure_cdx_flags_active(self, year_folder: str = None) -> int:
        """
        Scans all DBF files in a year folder (and client root) and ensures that
        bit 0x01 in byte 28 is active for all tables that have a corresponding .CDX file.
        For tables with .FPT memo files (like RKACCT40.DBF), sets byte 28 to 0x03.
        Returns the number of DBF headers healed.
        """
        yr = year_folder or self.active_year_folder
        target_paths = []
        if yr:
            year_path = os.path.join(self.client_path, yr)
            if os.path.exists(year_path):
                target_paths.append(year_path)
        if self.client_path and os.path.exists(self.client_path) and self.client_path not in target_paths:
            target_paths.append(self.client_path)
            
        healed_count = 0
        for dir_path in target_paths:
            for f in os.listdir(dir_path):
                if f.upper().endswith('.DBF'):
                    dbf_p = os.path.join(dir_path, f)
                    cdx_upper = f.upper().replace('.DBF', '.CDX')
                    cdx_lower = f.lower().replace('.dbf', '.cdx')
                    fpt_upper = f.upper().replace('.DBF', '.FPT')
                    fpt_lower = f.lower().replace('.dbf', '.fpt')
                    
                    has_cdx = os.path.exists(os.path.join(dir_path, cdx_upper)) or os.path.exists(os.path.join(dir_path, cdx_lower))
                    has_fpt = os.path.exists(os.path.join(dir_path, fpt_upper)) or os.path.exists(os.path.join(dir_path, fpt_lower))
                    
                    if has_cdx:
                        expected = (1 if has_cdx else 0) | (2 if has_fpt else 0)
                        try:
                            with open(dbf_p, 'r+b') as fp:
                                fp.seek(28)
                                raw_b = fp.read(1)
                                if raw_b:
                                    b28 = ord(raw_b)
                                    if b28 != expected:
                                        fp.seek(28)
                                        fp.write(bytes([expected]))
                                        healed_count += 1
                        except Exception as e:
                            print(f"⚠️ Could not check/heal CDX flag for {f}: {e}")
        if healed_count > 0:
            print(f"✅ [CDX Flag Self-Healer] Restored active CDX index flags on {healed_count} DBF table(s).")
        return healed_count

    def cleanup_old_backups(self, max_days: int = 14):
        """
        Scans year directories for lingering .BAK or .bak_trans files older than max_days (default 14 days)
        and safely removes them to prevent disk bloat.
        """
        try:
            import time
            now = time.time()
            max_age_seconds = max_days * 86400
            for yr_folder in self.get_available_year_folders():
                yr_path = yr_folder.get('path')
                if yr_path and os.path.exists(yr_path):
                    for filename in os.listdir(yr_path):
                        if filename.lower().endswith(('.bak', '.bak_trans')):
                            file_path = os.path.join(yr_path, filename)
                            try:
                                if os.path.isfile(file_path):
                                    mtime = os.path.getmtime(file_path)
                                    if (now - mtime) > max_age_seconds:
                                        os.remove(file_path)
                                        print(f"🧹 [Auto Backup Cleanup] Deleted old backup file ({max_days}+ days): {filename}")
                            except Exception:
                                pass
        except Exception as e:
            print(f"⚠️ [Auto Backup Cleanup Error]: {e}")

    @contextlib.contextmanager
    def backup_transaction_context(self, dbf_paths: list):
        """
        Creates temporary backups (.bak_trans) of all specified DBF (and corresponding CDX/FPT) files before yield.
        If an exception is raised inside the context, all modified tables are rolled back to the backup state.
        Regardless of success/failure, the temporary backup files are cleaned up at the end.
        """
        import shutil
        self.cleanup_old_backups(max_days=14)
        backups = {}
        for path in dbf_paths:
            if not os.path.exists(path):
                continue
            
            # Target backup paths
            backup_dbf = path + ".bak_trans"
            try:
                shutil.copy2(path, backup_dbf)
                backups[path] = backup_dbf
            except Exception as backup_err:
                print(f"⚠️ [Transaction Warning] Failed to backup file '{path}': {backup_err}")
            
            # Handle CDX/FPT companion files if present
            for ext in [".CDX", ".cdx", ".FPT", ".fpt"]:
                comp_path = path.replace(".DBF", ext).replace(".dbf", ext)
                if os.path.exists(comp_path):
                    comp_bak = comp_path + ".bak_trans"
                    try:
                        shutil.copy2(comp_path, comp_bak)
                        backups[comp_path] = comp_bak
                    except Exception as comp_err:
                        print(f"⚠️ [Transaction Warning] Failed to backup companion file '{comp_path}': {comp_err}")
                    
        try:
            yield
        except Exception as e:
            print(f"⚠️ [Transaction Rollback] Error occurred during DBF write: {e}. Restoring database backups...")
            # Restore backups
            for original, backup in backups.items():
                try:
                    if os.path.exists(backup):
                        shutil.copy2(backup, original)
                except Exception as restore_err:
                    print(f"❌ Failed to restore backup from '{backup}' to '{original}': {restore_err}")
            raise e
        finally:
            # Clean up backup files
            for backup in backups.values():
                try:
                    if os.path.exists(backup):
                        os.remove(backup)
                except:
                    pass

    def _inject_sales(self, vouchers: list, year_folder: str = "", setup_id: int = 5, sales_prefix: str = "SS,SS") -> int:
        """Helper alias for injecting Sales vouchers directly."""
        return self.inject_vouchers("Sales", vouchers, year_folder=year_folder, sales_setup_id=setup_id, sales_prefix=sales_prefix)

    def _inject_purchases(self, vouchers: list, year_folder: str = "", setup_id: int = 6, purchase_prefix: str = "PP,PP") -> int:
        """Helper alias for injecting Purchase vouchers directly."""
        return self.inject_vouchers("Purchases", vouchers, year_folder=year_folder, purchase_setup_id=setup_id, purchase_prefix=purchase_prefix)

    def push_opening_balances(self, vouchers: list, year_folder: str = "") -> dict:
        """Helper alias for injecting opening balances."""
        return self.inject_opening_balances(vouchers, year_folder=year_folder)

    def inject_vouchers(self, module: str, vouchers: list, year_folder: str | None = None, sales_prefix: str = "SS,SS", purchase_prefix: str = "PP,PP", sales_setup_id: int = 5, purchase_setup_id: int = 6, sales_series: str = "", bill_format_pattern: str = "", last_bill_number: int = 0, format_override: str | None = None, bank_name: str | None = None, target_cash_code: str | None = None, force_push: bool = False) -> int:
        """Injects a list of vouchers directly into RKACCT41.DBF, RKACCT02.DBF, and RKACCT52.DBF."""
        from datetime import datetime, date

        if not year_folder and vouchers:
            # Group vouchers by their financial year
            grouped = {}
            for v in vouchers:
                date_str = v.get('date', '')
                try:
                    v_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except Exception:
                    v_date = date.today()
                yr_folder = self.get_year_folder_for_date(v_date)
                if yr_folder not in grouped:
                    grouped[yr_folder] = []
                grouped[yr_folder].append(v)

            total_injected = 0
            for yr, group in grouped.items():
                print(f"Routing {len(group)} vouchers to {yr}")
                total_injected += self.inject_vouchers(module, group, yr, sales_prefix, purchase_prefix, sales_setup_id, purchase_setup_id, sales_series, bill_format_pattern, last_bill_number, format_override, bank_name, target_cash_code, force_push=force_push)
                last_bill_number += len(group) # roughly advance for the next year group if needed
            return total_injected

        if module == 'Bank Statements':
            return self._inject_bank_statements(vouchers, bank_name or "Bank Account", year_folder, force_push=force_push) # type: ignore
        elif module == 'Cash Entries':
            return self._inject_cash_entries(vouchers, target_cash_code, year_folder) # type: ignore

        # ── SAFETY: Ensure the right prefix is used for the right module ────────
        # This prevents the bug where a company with only purchase history gets
        # PP prefix used for sales entries, making them appear as Purchases.
        PURCHASE_STARTS = ('PP', 'PB', 'PU', 'PI', 'PO', 'PA')
        SALES_STARTS = ('SS', 'SL', 'SR', 'SA', 'SB', 'SC', 'SD')

        if module == 'Sales':
            sp_upper = sales_prefix.split(',')[0].strip().upper()
            if len(sp_upper) >= 2 and sp_upper[:2] in PURCHASE_STARTS and sp_upper[:2] not in SALES_STARTS:
                print(f"🛡️ SAFETY OVERRIDE: sales_prefix '{sales_prefix}' looks like a purchase prefix. Forcing 'SS,SS'.")
                sales_prefix = "SS,SS"
        elif module == 'Purchases':
            pp_upper = purchase_prefix.split(',')[0].strip().upper()
            if len(pp_upper) >= 2 and pp_upper[:2] in SALES_STARTS and pp_upper[:2] not in PURCHASE_STARTS:
                print(f"🛡️ SAFETY OVERRIDE: purchase_prefix '{purchase_prefix}' looks like a sales prefix. Forcing 'PP,PP'.")
                purchase_prefix = "PP,PP"
        # ────────────────────────────────────────────────────────────────────────
        
        if not year_folder:
            year_folder = self.get_latest_year_folder()
            
        t41_path = self._get_table_path('RKACCT41.DBF', year_folder)
        t02_path = self._get_table_path('RKACCT02.DBF', year_folder)
        t52_path = self._get_table_path('RKACCT52.DBF', year_folder)
        t01_path = self._get_table_path('RKACCT01.DBF', year_folder)
        t40_path = self._get_table_path('RKACCT40.DBF', year_folder)
        
        # Check case variation
        if not os.path.exists(t41_path): t41_path = self._get_table_path('rkacct41.dbf', year_folder)
        if not os.path.exists(t02_path): t02_path = self._get_table_path('rkacct02.dbf', year_folder)
        if not os.path.exists(t52_path): t52_path = self._get_table_path('rkacct52.dbf', year_folder)
        if not os.path.exists(t01_path): t01_path = self._get_table_path('rkacct01.dbf', year_folder)
        if not os.path.exists(t40_path): t40_path = self._get_table_path('rkacct40.dbf', year_folder)
        if not os.path.exists(t41_path) or not os.path.exists(t02_path) or not os.path.exists(t52_path) or not os.path.exists(t01_path):
            raise FileNotFoundError("Miracle transaction tables not found. Please create at least one dummy manual entry in Miracle for this financial year.")
            
        m01_path = self._get_table_path('RKACCM01.DBF', year_folder)
        if not os.path.exists(m01_path):
            m01_path = self._get_table_path('rkaccm01.dbf', year_folder)
            
        # Load ledgers to map name -> code for safety
        ledgers = self.read_ledgers(year_folder)
        name_to_code = {led['name'].upper(): led['code'] for led in ledgers}
        name_to_code.update({led['print_name'].upper(): led['code'] for led in ledgers})
        existing_codes = {led['code'].upper() for led in ledgers}
        gstin_to_code = {led['gstin'].upper(): led['code'] for led in ledgers if led.get('gstin') and len(led['gstin']) >= 15}
        
        # Build normalized alphanumeric lookup map for space/dot-insensitive party matching
        def clean_alpha_num(s):
            return re.sub(r'[^A-Z0-9]', '', str(s).upper())

        alpha_num_to_code = {}
        for led_name, led_code in name_to_code.items():
            an_key = clean_alpha_num(led_name)
            if an_key and an_key not in alpha_num_to_code:
                alpha_num_to_code[an_key] = led_code

        # Helper to get code
        def get_ledger_code(val):
            if not val:
                return ''
            val_clean = val.strip().upper()
            if val_clean in existing_codes:
                return val_clean
                
            # 1. Exact string match
            exact_match = name_to_code.get(val_clean)
            if exact_match:
                return exact_match

            # 2. Space & Punctuation Insensitive Match (e.g. "S S R Footcare" -> "SSRFOOTCARE" -> matches "SSR Footcare")
            val_an = clean_alpha_num(val_clean)
            if val_an and val_an in alpha_num_to_code:
                matched_code = alpha_num_to_code[val_an]
                print(f"✅ Space/Punctuation-insensitive matched party: '{val}' -> code '{matched_code}' (key: {val_an})")
                return matched_code

            # 3. Smart Fuzzy Match (cutoff=0.78)
            import difflib
            matches = difflib.get_close_matches(val_clean, list(name_to_code.keys()), n=1, cutoff=0.78)
            if matches:
                print(f"✅ Fuzzy matched Sales/Purchase party: '{val}' -> '{matches[0]}'")
                return name_to_code[matches[0]]

            # 4. Alphanumeric Fuzzy Match (cutoff=0.80)
            an_matches = difflib.get_close_matches(val_an, list(alpha_num_to_code.keys()), n=1, cutoff=0.80)
            if an_matches:
                matched_code = alpha_num_to_code[an_matches[0]]
                print(f"✅ Alphanumeric fuzzy matched party: '{val}' -> code '{matched_code}' (key: {an_matches[0]})")
                return matched_code
            
            return val.strip()

        import dbf
        import random
        import string

        def gen_id(pfx):
            num = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
            return pfx[:2] + num

        def pad_bill_no(s):
            s = str(s).strip()
            if '/' in s:
                parts = s.split('/')
                prefix_part = '/'.join(parts[:-1]) + '/'
                num_part = parts[-1]
                total_len = 16
                spaces_needed = total_len - len(prefix_part) - len(num_part)
                if spaces_needed > 0:
                    return f"{prefix_part}{' ' * spaces_needed}{num_part}"
                return f"{prefix_part}{num_part}"
            elif '-' in s:
                parts = s.split('-')
                prefix_part = '-'.join(parts[:-1]) + '-'
                num_part = parts[-1]
                total_len = 16
                spaces_needed = total_len - len(prefix_part) - len(num_part)
                if spaces_needed > 0:
                    return f"{prefix_part}{' ' * spaces_needed}{num_part}"
            return s[:16].ljust(16)

        # Auto-discover Sales and Purchase ledger codes dynamically from the client's database
        sales_local_code = None
        sales_interstate_code = None
        purch_local_code = None
        purch_interstate_code = None

        for led in ledgers:
            g_code = led.get('group_code', '')
            l_name = led.get('name', '').upper()
            l_code = led.get('code', '')
            
            # G0000021 & G0000027 are Sales Accounts groups
            if g_code in ('G0000021', 'G0000027'):
                if any(x in l_name for x in ['IGST', 'INTER', 'IS ', 'I/S', 'EXPORT']):
                    sales_interstate_code = l_code
                else:
                    sales_local_code = l_code
            
            # G0000023 & G0000026 are Purchase Accounts groups
            elif g_code in ('G0000023', 'G0000026'):
                if any(x in l_name for x in ['IGST', 'INTER', 'IS ', 'I/S', 'IMPORT']):
                    purch_interstate_code = l_code
                else:
                    purch_local_code = l_code

        # Fallbacks if some are not found
        # Sales
        if not sales_local_code:
            for led in ledgers:
                if led.get('group_code') in ('G0000021', 'G0000027'):
                    sales_local_code = led['code']
                    break
            if not sales_local_code:
                sales_local_code = 'AGST0001'
        if not sales_interstate_code:
            sales_interstate_code = sales_local_code
            
        # Purchases
        if not purch_local_code:
            for led in ledgers:
                if led.get('group_code') in ('G0000023', 'G0000026'):
                    purch_local_code = led['code']
                    break
            if not purch_local_code:
                purch_local_code = 'AGST0003'
        if not purch_interstate_code:
            purch_interstate_code = purch_local_code

        # Determine module parameters
        if module == 'Purchases':
            parts = [p.strip() for p in purchase_prefix.split(',')]
            f98 = parts[0] if parts else 'PP'
            f99 = parts[1] if len(parts) > 1 else f98
            prefix = f98
            default_account_code = purch_local_code
            interstate_account_code = purch_interstate_code
        elif module == 'Sales':
            parts = [p.strip() for p in sales_prefix.split(',')]
            f98 = parts[0] if parts else 'SS'
            f99 = parts[1] if len(parts) > 1 else f98
            prefix = f98
            default_account_code = sales_local_code
            interstate_account_code = sales_interstate_code
        else:
            raise ValueError(f"Module {module} not supported for DBF injection yet.")

        t40 = None
        backup_list = [t41_path, t02_path, t52_path, t01_path]
        if os.path.exists(t40_path):
            backup_list.append(t40_path)

        # Open tables in read-write mode safely bypassing CDX
        with self.backup_transaction_context(backup_list), \
             self.safe_cdx_context(t41_path), self.safe_cdx_context(t02_path), self.safe_cdx_context(t52_path), self.safe_cdx_context(t01_path):
            t41 = dbf.Table(t41_path)
            t02 = dbf.Table(t02_path)
            t52 = dbf.Table(t52_path)
            t01 = dbf.Table(t01_path)
            
            self._open_table_with_retry(t41, mode=dbf.READ_WRITE)
            self._open_table_with_retry(t02, mode=dbf.READ_WRITE)
            self._open_table_with_retry(t52, mode=dbf.READ_WRITE)
            self._open_table_with_retry(t01, mode=dbf.READ_WRITE)

            if os.path.exists(t40_path):
                try:
                    t40 = dbf.Table(t40_path)
                    self._open_table_with_retry(t40, mode=dbf.READ_WRITE)
                except Exception as ex_t40:
                    print(f"⚠️ Warning: Could not open RKACCT40 memo table: {ex_t40}")
                    t40 = None
            
            existing_vouchers = set()
            existing_amounts = set()
            try:
                for r in t41:
                    if dbf.is_deleted(r):
                        continue
                    b_no = str(r['T41FVNO']).strip()
                    f10 = str(r['FIELD10']).strip()
                    f12 = str(r['FIELD12']).strip()
                    v_dt = str(r['FIELD02']).strip()
                    p_code = str(r['FIELD04']).strip()
                    amount = float(r['FIELD06'] or 0) # type: ignore
                    
                    if b_no:
                        existing_vouchers.add((b_no, v_dt, p_code))
                    if f10:
                        existing_vouchers.add((f10, v_dt, p_code))
                    if f12:
                        existing_vouchers.add((f12, v_dt, p_code))
                        
                    if amount > 0 and (f10 or f12 or b_no):
                        bill_key = (f10 or f12 or b_no).strip()
                        existing_amounts.add((amount, v_dt, p_code, bill_key))
            except Exception as e:
                print(f"Error indexing existing vouchers: {e}")
                    
            # ── Format and Print Option Auto-Detection from Backdata ────────────────────
            # Scans current year and previous years to match client's exact unique formats.
            SALES_STARTS = ('SS', 'SL', 'SR', 'SA', 'SB', 'SC', 'SD')
            PURCH_STARTS = ('PP', 'PB', 'PU', 'PI', 'PO', 'PA')
            
            v_types_to_scan = SALES_STARTS if module == 'Sales' else PURCH_STARTS
            detected_cfg = self.detect_format_settings(year_folder, v_types_to_scan) # type: ignore
            
            resolved_format = detected_cfg["format"]
            resolved_f83 = detected_cfg["f83"]
            
            # Allow manual override for FIELD14 if passed
            if format_override and format_override.strip().upper() in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'N']:
                resolved_format = format_override.strip().upper()
                print(f"Using forced format_override: {resolved_format}")
            else:
                print(f"Auto-detected {module} FIELD14 format: {resolved_format}, T41F83 option: {resolved_f83}")
            # ─────────────────────────────────────────────────────────────────────────────
                
            company_state = self.get_company_state_code()
            print(f"Company state code: {company_state}")

            # State code lookup helper
            def get_party_state_code(p_code, party_gstin=''):
                STATE_MIRACLE_TO_GST = {
                    "ST000014": "02", "ST000028": "03", "ST000013": "06", "ST000010": "07",
                    "ST000029": "08", "ST000033": "09", "ST000024": "15", "ST000004": "18",
                    "ST000035": "19", "ST000016": "20", "ST000007": "22", "ST000020": "23",
                    "ST000012": "24", "ST000021": "27", "ST000017": "29", "ST000011": "30",
                    "ST000031": "33", "ST000039": "38", "ST000041": "96"
                }
                try:
                    # Try to find ST code from RKACCM01
                    t01_lookup = dbf.Table(m01_path)
                    t01_lookup.open(mode=dbf.READ_ONLY)
                    for r in t01_lookup:
                        if not dbf.is_deleted(r) and str(r['FIELD01']).strip().upper() == p_code.upper():
                            st_val = str(r['FIELD51']).strip()
                            t01_lookup.close()
                            if st_val in STATE_MIRACLE_TO_GST:
                                return STATE_MIRACLE_TO_GST[st_val]
                            return ''
                    t01_lookup.close()
                except:
                    pass
                # Fallback to parsing from gstin if available
                if party_gstin and len(party_gstin) >= 2 and party_gstin[:2].isdigit():
                    return party_gstin[:2]
                return ''

            injected_count = 0
            guids_to_register = []  # BUG FIX: must be initialized before the voucher loop
            try:
                for v in vouchers:
                    # Strict Bill Number Logic: Respect explicit numbers, auto-generate if missing.
                    raw_bill_no = str(v.get('billNo') or v.get('bill_no', '')).strip()
                    
                    if raw_bill_no:
                        # The Excel or PDF provided a specific bill number. Use it exactly as is.
                        bill_no = raw_bill_no
                        if raw_bill_no.isdigit():
                            last_bill_number = max(last_bill_number, int(raw_bill_no))
                    else:
                        # No bill number provided. Auto-generate using the Miracle sequence.
                        last_bill_number += 1
                        if bill_format_pattern:
                            bill_no = bill_format_pattern.format(num=last_bill_number)
                        else:
                            bill_no = str(last_bill_number)
                            if module == 'Sales' and sales_series:
                                bill_no = f"{sales_series}{bill_no}"
                    
                    # Ensure we pass the incremented number back to the caller in some way, 
                    # but since ints are immutable in Python, we'll just set it on the handler 
                    # so the caller can retrieve it if they want.
                    self.latest_injected_bill_number = last_bill_number
                        
                    # Generate unique ID
                    v_id = gen_id(prefix)
                    
                    # Parse date
                    date_str = v.get('date', '')
                    try:
                        v_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                    except Exception:
                        v_date = date.today()
                        
                    year_num = int(year_folder[-2:]) if year_folder and year_folder[-2:].isdigit() else 27
                    
                    # Parse amounts
                    taxable = self._parse_float(v.get('taxable', 0) or v.get('taxable_amount', 0))
                    cgst = self._parse_float(v.get('cgst', 0))
                    sgst = self._parse_float(v.get('sgst', 0))
                    igst = self._parse_float(v.get('igst', 0))
                    total = self._parse_float(v.get('total', 0))
                    
                    discount = self._parse_float(v.get('discount', 0.0) or 0.0)
                    freight = self._parse_float(v.get('freight', 0.0) or 0.0)
                    tcs = self._parse_float(v.get('tcs', 0.0) or 0.0)
                    tds = self._parse_float(v.get('tds', 0.0) or 0.0)
                    # Resolve Party Code (Check party_name, party, party_code in order)
                    party_id = str(v.get('party_name') or v.get('party') or v.get('party_code') or '').strip()
                    if party_id.startswith('UNKNOWN_PARTY:'):
                        party_id = party_id.replace('UNKNOWN_PARTY:', '').strip()
                    elif party_id.startswith('UNKNOWN_NARRATION:'):
                        party_id = party_id.replace('UNKNOWN_NARRATION:', '').strip()
                    elif party_id.startswith('AUTO_CREATE_B2C:'):
                        party_id = party_id.replace('AUTO_CREATE_B2C:', '').strip()
                    elif party_id.startswith('AUTO_CREATE_B2B:'):
                        party_id = party_id.replace('AUTO_CREATE_B2B:', '').strip()
                    
                    gstin = str(v.get('party_gstin') or '').strip().upper()
                    address = v.get('party_address') or ''
                    city = v.get('party_city') or ''
                    pincode = v.get('party_pincode') or ''
                    
                    # 1. Match party by name (Space & Punctuation Insensitive)
                    if party_id:
                        party_code = get_ledger_code(party_id)

                    # 2. Fallback to GSTIN lookup only if name match is missing/unmapped
                    if (not party_code or party_code.upper() not in existing_codes) and gstin and len(gstin) >= 15 and gstin in gstin_to_code:
                        party_code = gstin_to_code[gstin]
                        print(f"✅ Matched party by GSTIN: {gstin} -> {party_code}")
                    
                    # Auto-create B2C/B2B ledger if missing from local database
                    is_existing_code = party_code.upper() in existing_codes
                    
                    if not is_existing_code:
                        party_code = self.create_party_ledger(party_id, module, gstin=gstin, address=address, city=city, pincode=pincode, year_folder=year_folder)
                        # Re-load local lookup map so subsequent vouchers can find it
                        ledgers = self.read_ledgers(year_folder)
                        name_to_code = {led['name'].upper(): led['code'] for led in ledgers}
                        name_to_code.update({led['print_name'].upper(): led['code'] for led in ledgers})
                        existing_codes = {led['code'].upper() for led in ledgers}
                        gstin_to_code = {led['gstin'].upper(): led['code'] for led in ledgers if led.get('gstin') and len(led['gstin']) >= 15}
                    elif is_existing_code:
                        # Dynamically update address details if they changed or were missing
                        self.update_party_ledger_details(party_code, gstin=gstin, address=address, city=city, pincode=pincode, year_folder=year_folder)
                    
                    # Prevent duplicate voucher insertion
                    bill_no_padded = pad_bill_no(bill_no).strip()
                    raw_b_no = bill_no.strip()
                    v_date_str = str(v_date)
                    
                    is_exact_dup = (bill_no_padded, v_date_str, party_code) in existing_vouchers or \
                                   (raw_b_no, v_date_str, party_code) in existing_vouchers
                    
                    is_fuzzy_dup = False
                    if not is_exact_dup and total > 0:
                        fuzzy_bill_key = bill_no_padded or raw_b_no
                        if (total, v_date_str, party_code, fuzzy_bill_key) in existing_amounts:
                            is_fuzzy_dup = True
                            
                    if is_exact_dup or is_fuzzy_dup:
                        dup_reason = "Exact Match (Bill No + Date + Party)" if is_exact_dup else "Fuzzy Match (Amount + Date + Party)"
                        print(f"Skipping duplicate voucher ({dup_reason}): Bill {bill_no} for Party {party_code} on {v_date}")
                        self.audit_report["duplicates"] += 1
                        # Record full details so the UI can show which entry to find in Miracle
                        self.audit_report["duplicate_details"].append({
                            "date": str(v_date),
                            "bill_no": bill_no.strip(),
                            "party": str(v.get('party') or v.get('party_name') or '').strip(),
                            "amount": total,
                            "reason": dup_reason,
                            "module": "Sales/Purchase"
                        })
                        continue
                    
                    # Record this voucher to prevent duplicates in the same batch
                    existing_vouchers.add((bill_no_padded, v_date_str, party_code))
                    existing_vouchers.add((raw_b_no, v_date_str, party_code))
                    if total > 0 and (bill_no_padded or raw_b_no):
                        fuzzy_bill_key = bill_no_padded or raw_b_no
                        existing_amounts.add((total, v_date_str, party_code, fuzzy_bill_key))
                    
                    # Determine if party is interstate
                    party_state = get_party_state_code(party_code, v.get('party_gstin', ''))
                    if party_state and company_state:
                        is_interstate = (party_state != company_state)
                    else:
                        is_interstate = (igst > 0)

                    # ⚖️ Self-healing GST alignment based on POS (place of supply / interstate status)
                    total_gst = cgst + sgst + igst
                    if is_interstate:
                        if igst == 0.0 and total_gst > 0:
                            igst = total_gst
                            cgst = 0.0
                            sgst = 0.0
                            print(f"⚖️ POS Align: Converted local GST ({total_gst}) to IGST for interstate bill {bill_no}")
                    else:
                        if igst > 0 and total_gst > 0:
                            cgst = round(total_gst / 2, 2)
                            sgst = round(total_gst - cgst, 2)
                            igst = 0.0
                            print(f"⚖️ POS Align: Split IGST ({total_gst}) to CGST/SGST for local bill {bill_no}")

                    is_registered = bool(v.get('party_gstin') or '')
                    account_code = default_account_code
                    if is_interstate:
                        account_code = interstate_account_code
    
                    
                    # Parse Items
                    items = v.get('items', [])
                    default_qty = float(v.get('qty') or 1.0)
                    if not items:
                        items = [{
                            "name": "CONSULTING SERVICE",
                            "qty": default_qty,
                            "rate": taxable,
                            "amount": taxable,
                            "gst_pct": 18.0
                        }]

                    # Process items and calculate values first (to allow exact matching/scaling)
                    processed_items = []
                    rate_groups = {}

                    # Determine if incoming item amounts are net or gross
                    sum_item_amounts = sum(float(item.get('amount') or 0.0) for item in items)
                    is_net_amounts = True
                    if discount > 0.0 and sum_item_amounts > 0.0:
                        diff_to_net = abs(sum_item_amounts - taxable)
                        diff_to_gross = abs(sum_item_amounts - (taxable + discount))
                        if diff_to_gross < diff_to_net:
                            is_net_amounts = False

                    # Determine if invoice is inclusive of tax by comparing sum of item net amounts
                    # to header total and header taxable amount.
                    if is_net_amounts:
                        sum_net_amounts = sum_item_amounts
                    else:
                        sum_net_amounts = sum_item_amounts - discount

                    header_taxable = taxable
                    header_total = total
                    header_tax = cgst + sgst + igst
                    
                    is_inclusive = False
                    if header_tax > 0 and sum_net_amounts > 0:
                        diff_to_total = abs(sum_net_amounts - header_total)
                        diff_to_taxable = abs(sum_net_amounts - header_taxable)
                        if diff_to_total < diff_to_taxable:
                            is_inclusive = True

                    # Pre-calculate item gross/net amounts for discount distribution
                    item_gross_amounts = []
                    for item in items:
                        qty_val = float(item.get('qty') or 1.0)
                        rate_val = float(item.get('rate') or 0.0)
                        amt_val = float(item.get('amount') or 0.0)
                        if amt_val == 0.0 and rate_val > 0.0:
                            amt_val = qty_val * rate_val
                        item_gross_amounts.append(amt_val)
                    
                    total_gross_items = sum(item_gross_amounts)
                    
                    # Distribute discount proportionally
                    item_discounts = []
                    if discount > 0.0 and total_gross_items > 0.0:
                        temp_sum = 0.0
                        for idx, amt_val in enumerate(item_gross_amounts):
                            it_disc = round(discount * (amt_val / total_gross_items), 2)
                            item_discounts.append(it_disc)
                            temp_sum += it_disc
                        
                        # Adjust rounding differences on the first item
                        diff = round(discount - temp_sum, 2)
                        if diff != 0.0 and len(item_discounts) > 0:
                            item_discounts[0] = round(item_discounts[0] + diff, 2)
                    else:
                        sum_item_discounts = sum(float(item.get('discount') or 0.0) for item in items)
                        if sum_item_discounts > 0.0:
                            discount = sum_item_discounts
                            item_discounts = [float(item.get('discount') or 0.0) for item in items]
                        else:
                            item_discounts = [0.0] * len(items)
                    
                    for item_idx, item in enumerate(items):
                        item_name = (item.get('name') or '').strip()
                        party_name_clean = (v.get('party_name') or v.get('party') or '').strip().upper()
                        
                        hsn_code = str(item.get('hsn_code') or '').strip()
                        uom_code = str(item.get('uom') or '').strip()
                        master_gst = self.get_product_master_gst_rate(item_name, year_folder)
                        if master_gst is not None:
                            item_gst_pct = master_gst
                        else:
                            raw_gst_pct = item.get('gst_pct')
                            if raw_gst_pct is not None:
                                item_gst_pct = float(raw_gst_pct)
                            else:
                                item_gst_pct = 18.0 if header_tax > 0.0 else 0.0

                        # Fall back to standard GST rate product if item_name is empty or matches party name
                        if not item_name or item_name.upper() == party_name_clean or item_name.upper() in ("AUTO_CREATE_PRODUCT", "CONSULTING SERVICE", "UNKNOWN_ITEM"):
                            default_base = "SALES" if module == "Sales" else "PURCHASES"
                            item_name = f"{default_base} GST {int(item_gst_pct)}%" if item_gst_pct > 0 else f"{default_base} EXEMPT"
                            
                        if item_gst_pct <= 0.0 and header_tax > 0 and header_taxable > 0:
                            item_gst_pct = round((header_tax / header_taxable) * 100)
                        
                        product_code = self.get_or_create_product(item_name, hsn=hsn_code, uom=uom_code, gst_pct=item_gst_pct, year_folder=year_folder)
                        
                        qty = float(item.get('qty') or 1.0)
                        rate = float(item.get('rate') or 0.0)
                        amount = float(item.get('amount') or 0.0)
                        item_discount = item_discounts[item_idx]
                        
                        # Fallbacks for empty item
                        if amount == 0 and rate > 0:
                            amount = qty * rate
                        if rate == 0 and qty > 0 and amount > 0:
                            rate = amount / qty
                        
                        if is_net_amounts:
                            item_taxable = amount
                            item_gross = round(item_taxable + item_discount, 2)
                        else:
                            item_gross = amount
                            item_taxable = round(item_gross - item_discount, 2)
                            
                        if is_inclusive:
                            item_taxable = round((item_gross - item_discount) / (1 + item_gst_pct / 100.0), 2)
                            item_gst = round((item_gross - item_discount) - item_taxable, 2)
                        else:
                            # Exclusive of tax: calculate GST on top
                            item_gst = round(item_taxable * (item_gst_pct / 100.0), 2)
                            
                        processed_items.append({
                            "product_code": product_code,
                            "qty": qty,
                            "rate": item_gross / qty if qty > 0 else rate,
                            "amount": item_gross,
                            "discount": item_discount,
                            "taxable": item_taxable,
                            "gst": item_gst,
                            "gst_pct": item_gst_pct,
                            "hsn_code": hsn_code,
                            "uom_code": uom_code
                        })

                    # 2. Adjust GST on processed items proportionally to match total voucher tax exactly
                    total_items_gst = sum(p["gst"] for p in processed_items)
                    total_voucher_tax = cgst + sgst + igst
                    
                    if total_items_gst > 0 and total_items_gst != total_voucher_tax:
                        factor = total_voucher_tax / total_items_gst
                        for p in processed_items:
                            p["gst"] = round(p["gst"] * factor, 2)
                            
                        # Adjust rounding differences on first item
                        new_sum = sum(p["gst"] for p in processed_items)
                        diff = round(total_voucher_tax - new_sum, 2)
                        if diff != 0 and len(processed_items) > 0:
                            processed_items[0]["gst"] = round(processed_items[0]["gst"] + diff, 2)
                    # Recalculate true header taxable from line items to fix PDF inconsistencies
                    taxable = sum(p["taxable"] for p in processed_items)
                    
                    # Calculate round-off based on the true item-derived taxable sum
                    net_taxable = taxable
                    sum_parts = net_taxable + cgst + sgst + igst + freight + tcs - tds
                    round_off = round(total - sum_parts, 2)
                    if abs(round_off) > 5.0:
                        party_name_for_audit = (v.get('party_name') or v.get('party') or '').strip()
                        self.audit_report["anomalies"] += 1
                        self.audit_report["messages"].append(f"⚠️ High Round-Off Anomaly: ₹{round_off} on Bill {bill_no} (Party: {party_name_for_audit})")
                    
                    has_gst = (cgst > 0 or sgst > 0 or igst > 0)
                    
                     # Count T01 lines for FIELD20: 2 = Party+SalesAc, more for each tax/extra line
                    t01_line_count = 2  # base: party + sales/purchase account
                    if cgst > 0: t01_line_count += 1
                    if sgst > 0: t01_line_count += 1
                    if igst > 0: t01_line_count += 1
                    if freight > 0: t01_line_count += 1
                    if tcs > 0: t01_line_count += 1
                    if tds > 0: t01_line_count += 1
                    if round_off != 0: t01_line_count += 1

                    t41_fvno_val = '' if module == 'Purchases' else pad_bill_no(bill_no)
                    t01_f12_val = '' if module == 'Purchases' else pad_bill_no(bill_no)
                    t01_f15_val = bill_no if module == 'Purchases' else ''
                    t01_f16_val = v_date if module == 'Purchases' else None

                    # Write Header Record (T41)
                    header_rec = {}
                    for f in t41.field_names:
                        if f.startswith(('EP', 'ED')):
                            header_rec[f] = 0.0
                        elif f.startswith('EA'):
                            header_rec[f] = ''
                    if 'FIELD51' in t41.field_names: header_rec['FIELD51'] = 0.0
                    if 'FIELD18' in t41.field_names: header_rec['FIELD18'] = 0.0

                    header_rec.update({
                        'FIELD98': f98,
                        'FIELD99': f99,
                        'FIELD01': v_id,
                        'FIELD02': v_date,
                        'FIELD03': purchase_setup_id if module == 'Purchases' else sales_setup_id,
                        'FIELD04': party_code,
                        'FIELD05': account_code,
                        'FIELD06': total,
                        'FIELD07': sum(p["amount"] for p in processed_items) if module == 'Sales' else taxable,
                        'FIELD14': resolved_format,
                        'FIELD16': 'D',
                        'FIELD17': 'U0000000',
                        'FIELD20': len(processed_items),  # Number of item lines in RKACCT02
                        'FIELD21': 'T',  # Always 'T' (Tax Invoice) even for Exempt/No-GST
                        'FIELD74': 'SP',
                        'FIELD75': '0',  # Always '0'
                        'T41F83': resolved_f83,
                        'T41F84': 'O',
                        'T41FVNO': t41_fvno_val,
                        'T41F45': year_num,
                        'T41F97': '01',  # Always '01'
                        'T41F96': 'G',
                        'EDGAS00001': cgst,
                        'EDGAS00002': sgst,
                        'EDGAS00003': igst,
                        'EDVAS00099': round_off,
                        'EAVAS00099': 'AVAUTO99'
                    })
                    if module == 'Purchases':
                        header_rec['FIELD13'] = 'IDGST003' if is_interstate else 'IDGST001'
                    else:
                        header_rec['FIELD13'] = 'IDGST053' if is_interstate else 'IDGST051'
                    
                    # Resolve charge slots from setup table (Miracle9070 compatibility)
                    slots = self._resolve_charge_slots(year_folder, module)
                    
                    def write_header_charge(charge_type, amount, ledger_code, pct=0.0):
                        info = slots.get(charge_type)
                        if not info:
                            return
                        key = info["key"]
                        if info["is_dynamic"]:
                            match = re.search(r'(\d+)$', key)
                            if match:
                                slot_num = int(match.group(1))
                                ed_field = f"ED0000000{slot_num}"
                                ep_field = f"EP0000000{slot_num}"
                                ea_field = f"EA0000000{slot_num}"
                                if ed_field in t41.field_names:
                                    header_rec[ed_field] = amount
                                if ep_field in t41.field_names:
                                    header_rec[ep_field] = pct
                                if ea_field in t41.field_names:
                                    header_rec[ea_field] = ledger_code
                        else:
                            ed_field = f"ED{key}"
                            ep_field = f"EP{key}"
                            ea_field = f"EA{key}"
                            if ed_field in t41.field_names:
                                header_rec[ed_field] = amount
                            if ep_field in t41.field_names:
                                header_rec[ep_field] = pct
                            if ea_field in t41.field_names:
                                header_rec[ea_field] = ledger_code

                    if discount > 0:
                        write_header_charge("discount", discount, "")

                    resolved_freight_ledger = ""
                    if freight > 0:
                        # Fallback for old transport ledgers, but use get_or_create for robustness
                        existing = self.find_ledger_by_keyword("TRANSPORT", year_folder)
                        if existing:
                            resolved_freight_ledger = existing
                        else:
                            resolved_freight_ledger = self.get_or_create_dynamic_ledger("FREIGHT", "FREIGHT & FORWARDING", "I0000001", "I0000001", year_folder)
                        write_header_charge("freight", freight, resolved_freight_ledger)

                    resolved_tcs_ledger = ""
                    if tcs > 0:
                        resolved_tcs_ledger = self.get_or_create_dynamic_ledger("TCS", "TCS PAYABLE", "L0000006", "L0000006", year_folder)
                        write_header_charge("tcs", tcs, resolved_tcs_ledger)
                        if 'FIELD76' in t41.field_names:
                            header_rec['FIELD76'] = str(tcs)

                    resolved_tds_ledger = ""
                    if tds > 0:
                        resolved_tds_ledger = self.get_or_create_dynamic_ledger("TDS", "TDS RECEIVABLE", "A0000008", "A0000008", year_folder)
                        write_header_charge("tds", -tds, resolved_tds_ledger)  # Negative to reduce bill total
                        if 'FIELD73' in t41.field_names:
                            header_rec['FIELD73'] = str(tds)

                    ro_ledger = slots["round_off"]["ledger_code"] or "AVAUTO99"
                    write_header_charge("round_off", round_off, ro_ledger)
                    
                    # Transporter and Lorry Receipt fields (Miracle9070 native transporter support)
                    eway_bill = v.get('U0000006', '') or v.get('eway_bill', '')
                    vehicle_no = v.get('U0000005', '') or v.get('vehicle_no', '')
                    transporter = v.get('transporter', '')
                    
                    if 'UTRANS' in t41.field_names:
                        if transporter:
                            header_rec['UTRANS'] = transporter
                        elif vehicle_no:
                            header_rec['UTRANS'] = vehicle_no
                    
                    if 'ULRNO' in t41.field_names:
                        if eway_bill:
                            header_rec['ULRNO'] = eway_bill
                        elif vehicle_no:
                            header_rec['ULRNO'] = vehicle_no
                            
                    if 'ULRDATE' in t41.field_names:
                        header_rec['ULRDATE'] = v_date
                        
                    # Older schema custom fields fallback
                    if 'U0000006' in t41.field_names and eway_bill:
                        header_rec['U0000006'] = eway_bill
                    if 'U0000005' in t41.field_names and vehicle_no:
                        header_rec['U0000005'] = vehicle_no
                    
                    if module == 'Purchases':
                        # FIELD10 = Supplier Invoice No (only for Purchases)
                        # FIELD11 = Supplier Invoice Date (only for Purchases)
                        header_rec['FIELD10'] = bill_no
                        header_rec['FIELD11'] = v_date
                        header_rec['FIELD12'] = ''
                    else:
                        # Sales: FIELD10 must be BLANK (not supplier invoice no)
                        # Only FIELD12 holds the Sales voucher number
                        header_rec['FIELD10'] = ''
                        header_rec['FIELD11'] = None
                        header_rec['FIELD12'] = bill_no
                    
                    # Narration text resolution for Sales & Purchases
                    narr_text = (v.get('narration') or v.get('remark') or v.get('description') or f"{module} Bill No {bill_no} - {party_id}").strip()
                    header_rec['FIELD82'] = self.fit_dbf_str(narr_text, 50)

                    self._append_record(t41, header_rec)
                    guids_to_register.append(('YRT41', v_id, True))

                    # Write narration to RKACCT40 memo table for Miracle UI
                    if t40:
                        t40_rec = {
                            'T40F01': v_id,
                            'T40F09': 'XXXX',
                            'T40F02': narr_text
                        }
                        self._append_record(t40, t40_rec)

# 3. Build rate groups and write line items to RKACCT02
                    for p in processed_items:
                        item_gst_pct = p["gst_pct"]
                        item_taxable = p["taxable"]
                        item_gst = p["gst"]
                        
                        if item_gst_pct not in rate_groups:
                            rate_groups[item_gst_pct] = {
                                "taxable": 0.0,
                                "gst": 0.0
                            }
                        rate_groups[item_gst_pct]["taxable"] += item_taxable
                        rate_groups[item_gst_pct]["gst"] += item_gst
                        
                    # Proportional adjustment of GST in rate groups to match voucher totals exactly
                    groups_list = list(rate_groups.items())
                    if groups_list:
                        total_group_gst = sum(g["gst"] for r, g in groups_list)
                        if total_group_gst > 0 and total_group_gst != total_voucher_tax:
                            factor = total_voucher_tax / total_group_gst
                            for r, g in groups_list:
                                g["gst"] = round(g["gst"] * factor, 2)
                        
                        # Adjust any minor rounding diffs in groups list
                        new_sum_gst = sum(g["gst"] for r, g in groups_list)
                        diff = round(total_voucher_tax - new_sum_gst, 2)
                        if diff != 0:
                            groups_list[0][1]["gst"] = round(groups_list[0][1]["gst"] + diff, 2)

                    # Helper to write dynamic surcharge/charges at item level
                    def write_detail_charge(t02_rec_dict, charge_type, amount, ledger_code, pct=0.0):
                        info = slots.get(charge_type)
                        if not info:
                            return
                        key = info["key"]
                        if info["is_dynamic"]:
                            match = re.search(r'(\d+)$', key)
                            if match:
                                slot_num = int(match.group(1))
                                id_field = f"ID0000000{slot_num}"
                                ip_field = f"IP0000000{slot_num}"
                                ia_field = f"IA0000000{slot_num}"
                                it_field = f"IT0000000{slot_num}"
                                if id_field in t02.field_names:
                                    t02_rec_dict[id_field] = amount
                                if ip_field in t02.field_names:
                                    t02_rec_dict[ip_field] = pct
                                if ia_field in t02.field_names:
                                    t02_rec_dict[ia_field] = ledger_code
                                if it_field in t02.field_names:
                                    t02_rec_dict[it_field] = ""
                        else:
                            id_field = f"ID{key}"
                            ip_field = f"IP{key}"
                            ia_field = f"IA{key}"
                            it_field = f"IT{key}"
                            if id_field in t02.field_names:
                                t02_rec_dict[id_field] = amount
                            if ip_field in t02.field_names:
                                t02_rec_dict[ip_field] = pct
                            if ia_field in t02.field_names:
                                t02_rec_dict[ia_field] = ledger_code
                            if it_field in t02.field_names:
                                t02_rec_dict[it_field] = ""

                    # Now, append line items to RKACCT02 (t02) with correct adjusted taxes
                    line_idx = 1
                    total_items = len(processed_items)
                    acc_cgst = 0.0
                    acc_sgst = 0.0
                    acc_igst = 0.0
                    for p in processed_items:
                        t02_rec = {}
                        for f in t02.field_names:
                            if f.startswith(('IP', 'ID')):
                                t02_rec[f] = 0.0
                            elif f.startswith(('IA', 'IT')):
                                t02_rec[f] = ''
                        
                        iavas_val = account_code
                        # Populate default ledger code fields for all slots to satisfy double-entry linkage
                        for charge_type in ["discount", "freight", "tcs", "tds"]:
                            info = slots.get(charge_type)
                            if info:
                                key = info["key"]
                                # Write empty string for discount ledger, iavas_val for other charges
                                led_val = "" if charge_type == "discount" else iavas_val
                                if info["is_dynamic"]:
                                    match = re.search(r'(\d+)$', key)
                                    if match:
                                        slot_num = int(match.group(1))
                                        ia_field = f"IA0000000{slot_num}"
                                        if ia_field in t02.field_names:
                                            t02_rec[ia_field] = led_val
                                else:
                                    ia_field = f"IA{key}"
                                    if ia_field in t02.field_names:
                                        t02_rec[ia_field] = led_val

                        t02_rec.update({
                            'FIELD98': f98,
                            'FIELD99': f99,
                            'FIELD01': v_id,
                            'FIELD02': v_date,
                            'FIELD03': p["product_code"],
                            # CRITICAL MIRACLE REQUIREMENT: FIELD04 must be 'N' for Purchases, 'I' for Sales
                            'FIELD04': 'N' if module == 'Purchases' else ('I' if has_gst else 'N'),
                            # CRITICAL MIRACLE REQUIREMENT: FIELD05 must be 'C' for Purchases, 'D' for Sales
                            'FIELD05': 'C' if module == 'Purchases' else 'D',
                            'FIELD06': p["qty"],
                            'FIELD07': p["rate"],
                            'FIELD08': p["amount"] if module == 'Sales' else p["taxable"],
                            'FIELD09': f"{line_idx:>4}",
                            'FIELD10': 1,
                            'FIELD12': party_code,
                            'FIELD16': account_code,
                            'T02F16': account_code,
                            'T02F11': account_code,
                            'FIELD34': line_idx,
                            'FIELD85': '0' if has_gst else '',
                            'T02F24': party_code,
                            'T02F97': '01' if has_gst else '',
                            'T02F37': 'D',
                            'FIELD38': 'N',
                            'T02F83': resolved_f83,
                            'T02F45': year_num,
                            # T02F46 = GROSS amount for Sales, NET taxable for Purchases.
                            # CRITICAL: For Sales, T02F46 drives the footer "Item Amount" display.
                            #   Footer = T02F46 - EDVAS00095 (header discount) + GST = Bill Amount.
                            #   If T02F46 = net (4628.57) AND EDVAS00095 = 514.29 → discount deducted TWICE → Bill = 4346 (WRONG).
                            #   If T02F46 = gross (5142.86) AND EDVAS00095 = 514.29 → discount deducted ONCE → Bill = 4860 (CORRECT).
                            # T52F13 (GSTR taxable) uses p["taxable"] separately in the T52 records — it is NOT driven by T02F46.
                            'T02F46': p["amount"] if module == 'Sales' else p["taxable"],
                            'T02F96': 'G',
                            'FIELD33': p["qty"],     # Alternate quantity field required by Miracle
                            'FIELD21': 0.0,
                            'FIELD22': 0.0,
                            'FIELD23': 0.0,
                            'FIELD25': 0.0,
                            'T02F28': 0.0,
                            'FIELD50': 0.0,
                            'FIELD52': 0.0
                        })
                        
                        if p.get("discount", 0) > 0:
                            write_detail_charge(t02_rec, "discount", p["discount"], "")
                        
                        item_gst = p["gst"]
                        item_gst_pct = p["gst_pct"]
                        item_has_gst = has_gst and (item_gst_pct > 0) and (item_gst > 0)
                        
                        t02_rec['T02F97'] = '01' if item_has_gst else ('02' if has_gst else '')
                        
                        if item_has_gst:
                            if igst > 0:
                                if 'IDGAS00003' in t02.field_names:
                                    igst_ac = 'AGST0007' if module == 'Purchases' else 'AGST0010'
                                    # Penny Reconciliation: adjust final line item to match header IGST exactly
                                    if line_idx == total_items:
                                        item_igst_amt = round(igst - acc_igst, 2)
                                    else:
                                        item_igst_amt = item_gst
                                        acc_igst += item_igst_amt
                                    t02_rec['IDGAS00003'] = max(0.0, item_igst_amt)
                                    t02_rec['IPGAS00003'] = item_gst_pct
                                    t02_rec['IAGAS00003'] = igst_ac
                            else:
                                if 'IDGAS00001' in t02.field_names:
                                    cgst_ac = 'AGST0005' if module == 'Purchases' else 'AGST0008'
                                    # Penny Reconciliation: adjust final line item to match header CGST exactly
                                    if line_idx == total_items:
                                        item_cgst_amt = round(cgst - acc_cgst, 2)
                                    else:
                                        item_cgst_amt = round(item_gst / 2.0, 2)
                                        acc_cgst += item_cgst_amt
                                    t02_rec['IDGAS00001'] = max(0.0, item_cgst_amt)
                                    t02_rec['IPGAS00001'] = round(item_gst_pct / 2.0, 2)
                                    t02_rec['IAGAS00001'] = cgst_ac
                                if 'IDGAS00002' in t02.field_names:
                                    sgst_ac = 'AGST0006' if module == 'Purchases' else 'AGST0009'
                                    # Penny Reconciliation: adjust final line item to match header SGST exactly
                                    if line_idx == total_items:
                                        item_sgst_amt = round(sgst - acc_sgst, 2)
                                    else:
                                        item_sgst_amt = round(item_gst / 2.0, 2)
                                        acc_sgst += item_sgst_amt
                                    t02_rec['IDGAS00002'] = max(0.0, item_sgst_amt)
                                    t02_rec['IPGAS00002'] = round(item_gst_pct / 2.0, 2)
                                    t02_rec['IAGAS00002'] = sgst_ac
                        else:
                            # Explicitly clear tax fields for 0% GST or Exempt items
                            if 'IDGAS00001' in t02.field_names: t02_rec['IDGAS00001'] = 0.0
                            if 'IDGAS00002' in t02.field_names: t02_rec['IDGAS00002'] = 0.0
                            if 'IDGAS00003' in t02.field_names: t02_rec['IDGAS00003'] = 0.0
                            if 'IPGAS00001' in t02.field_names: t02_rec['IPGAS00001'] = 0.0
                            if 'IPGAS00002' in t02.field_names: t02_rec['IPGAS00002'] = 0.0
                            if 'IPGAS00003' in t02.field_names: t02_rec['IPGAS00003'] = 0.0
                            if 'IAGAS00001' in t02.field_names: t02_rec['IAGAS00001'] = ''
                            if 'IAGAS00002' in t02.field_names: t02_rec['IAGAS00002'] = ''
                            if 'IAGAS00003' in t02.field_names: t02_rec['IAGAS00003'] = ''
                        if line_idx == 1 and tcs > 0:
                            if 'ID00000002' in t02.field_names:
                                tcs_ledger = resolved_tcs_ledger
                                t02_rec['ID00000002'] = tcs
                                t02_rec['IA00000002'] = tcs_ledger if tcs_ledger else ''
                                
                        self._append_record(t02, t02_rec, {'FIELD09': f"{line_idx:>4}"})
                        line_idx += 1

                    # Generate unique T52F27 key helper
                    def gen_t52f27():
                        import random
                        import string
                        chars = string.ascii_uppercase + string.digits
                        return "GS" + "".join(random.choices(chars, k=10))

                    # A. RKACCT52 Records (GST details summary & breakdown)
                    # 1. Summary Record (Row 1)
                    seq_idx = 1
                    party_state = get_party_state_code(party_code)
                    tax_type_flag = 'I' if is_interstate else 'S'
                    
                    t52_summary = {
                        'T52F01': v_id,
                        'T52F02': v_date,
                        'T52F03': str(seq_idx),
                        'T52F04': 'N',
                        # CRITICAL MIRACLE REQUIREMENTS FOR GST BOOKS:
                        # T52F05: 'C' (Purchases), 'T' (Sales)
                        # T52F22: 'C' (Purchases), 'D' (Sales)
                        # T52F28: 'C' (Purchases), 'T' (Sales)
                        # T52F30: '4' (Purchase Book), '3' (Sales Book)
                        # If these are wrong, entries vanish from GSTR returns or turn RED.
                        'T52F05': 'C' if module == 'Purchases' else 'T',
                        'T52F06': '1',
                        'T52F11': party_state,
                        'T52F12': 'R' if is_registered else 'U',
                        'T52F13': taxable,
                        # WHY taxable (not net_taxable):
                        # p["taxable"] already = amount - item_discount (per-item discount already deducted).
                        # net_taxable = taxable - header_discount = DOUBLE-DEDUCTION in GSTR Assessable column.
                        # Header discount (EDVAS00095) shows in the separate "Discount Amount" GSTR column.
                        # This makes Assessable Amount = GST 5% Assessable Amount (consistent, no mismatch).
                        'T52F15': cgst,
                        'T52F17': sgst,
                        'T52F19': igst,
                        # T52F20 must be 0.0 because T52F13 already holds NET taxable (after discount).
                        # Putting -discount here would deduct discount TWICE in GSTR reports.
                        # Rule: T52F13 = net taxable → T52F20 = 0. OR T52F13 = gross → T52F20 = -discount.
                        # We use net in T52F13, so T52F20 = 0.
                        'T52F20': 0.0,
                        'T52F22': 'C' if module == 'Purchases' else 'D',
                        'T52F23': 'T',
                        'T52F24': 'N',
                        'T52F25': cgst + sgst + igst,
                        'T52F27': gen_t52f27(),
                        'T52F28': 'C' if module == 'Purchases' else 'T',
                        'T52F29': 'O',
                        'T52F30': '4' if module == 'Purchases' else '3',
                        'T52F35': party_code,
                        'T52F43': 'N',
                        'T52F44': 'N',
                        'T52F45': 'S' if party_code.upper() == 'ACASHACT' else 'R',
                        'T52F46': tax_type_flag,
                        'T52F33': 'N',
                        'T52F75': '0',  # Always '0'
                        'T52F97': '01',
                        'T52F98': f98
                    }
                    self._append_record(t52, t52_summary)

                    # 2. Breakdown Records (Row 2, 3, etc. for each rate group)
                    if has_gst:
                        for r_pct, g_data in rate_groups.items():
                            seq_idx += 1
                            if r_pct <= 0:
                                g_code = "GNGT"
                                c_code = "CNGT"
                            elif r_pct <= 3:
                                g_code = "G006"
                                c_code = "C006"
                            elif r_pct <= 5:
                                g_code = "G002"
                                c_code = "C002"
                            elif r_pct <= 12:
                                g_code = "G003"
                                c_code = "C003"
                            elif r_pct <= 18:
                                g_code = "G004"
                                c_code = "C004"
                            else:
                                g_code = "G005"
                                c_code = "C005"

                            if is_interstate:
                                g_igst = g_data["gst"]
                                g_cgst = 0.0
                                g_sgst = 0.0
                                g_cgst_rate = 0.0
                                g_sgst_rate = 0.0
                                g_igst_rate = r_pct
                            else:
                                g_igst = 0.0
                                g_cgst = round(g_data["gst"] / 2.0, 2)
                                g_sgst = round(g_data["gst"] / 2.0, 2)
                                g_cgst_rate = round(r_pct / 2.0, 2)
                                g_sgst_rate = round(r_pct / 2.0, 2)
                                g_igst_rate = 0.0

                            g_discount = sum(p["discount"] for p in processed_items if p["gst_pct"] == r_pct)
                            t52_breakdown = {
                                'T52F01': v_id,
                                'T52F02': v_date,
                                'T52F09': '   1',
                                'T52F03': str(seq_idx),
                                'T52F04': 'T',
                                'T52F06': '1',
                                'T52F07': 'G',
                                'T52F10': g_code,
                                'T52F31': c_code,
                                'T52F11': party_state,
                                'T52F12': 'R' if is_registered else 'U',
                                'T52F13': g_data["taxable"],
                                'T52F14': g_cgst_rate,
                                'T52F15': g_cgst,
                                'T52F16': g_sgst_rate,
                                'T52F17': g_sgst,
                                'T52F18': g_cgst_rate + g_sgst_rate + g_igst_rate,
                                'T52F19': g_igst,
                                # T52F20 = 0.0: T52F13 (g_data["taxable"]) is already net per-item taxable.
                                # Adding negative discount here causes GSTR double deduction.
                                'T52F20': 0.0,
                                'T52F21': account_code,
                                'T52F22': 'C' if module == 'Purchases' else 'D',
                                'T52F23': 'T',
                                'T52F24': 'N',
                                'T52F25': g_cgst + g_sgst + g_igst,
                                'T52F27': gen_t52f27(),
                                'T52F28': 'C' if module == 'Purchases' else 'T',
                                'T52F29': 'O',
                                'T52F30': '4' if module == 'Purchases' else '3',
                                'T52F35': party_code,
                                'T52F43': 'N',
                                'T52F44': 'N',
                                'T52F45': 'S' if party_code.upper() == 'ACASHACT' else 'R',
                                'T52F46': tax_type_flag,
                                'T52F75': '0',
                                'T52F97': '01',
                                'T52F98': f98
                            }
                            self._append_record(t52, t52_breakdown)
                    else:
                        # For No-GST, append a breakdown record using GNGT and CNGT
                        seq_idx += 1
                        g_discount = sum(p["discount"] for p in processed_items)
                        t52_breakdown = {
                            'T52F01': v_id,
                            'T52F02': v_date,
                            'T52F09': '   1',
                            'T52F03': str(seq_idx),
                            'T52F04': 'T',
                            'T52F06': '1',
                            'T52F07': 'G',
                            'T52F10': 'GNGT',
                            'T52F31': 'CNGT',
                            'T52F11': party_state,
                            'T52F12': 'R' if is_registered else 'U',
                            'T52F13': taxable,
                            # Same rule: taxable (not net_taxable) so No-GST Assessable also doesn't double-deduct discount.
                            'T52F14': 0.0,
                            'T52F15': 0.0,
                            'T52F16': 0.0,
                            'T52F17': 0.0,
                            'T52F18': 0.0,
                            'T52F19': 0.0,
                            # T52F20 = 0.0: No-GST breakdown also uses net taxable in T52F13.
                            'T52F20': 0.0,
                            'T52F21': account_code,
                            'T52F22': 'C' if module == 'Purchases' else 'D',
                            'T52F23': 'T',
                            'T52F24': 'N',
                            'T52F25': 0.0,
                            'T52F27': gen_t52f27(),
                            'T52F28': 'C' if module == 'Purchases' else 'T',
                            'T52F29': 'O',
                            'T52F30': '4' if module == 'Purchases' else '3',
                            'T52F35': party_code,
                            'T52F43': 'N',
                            'T52F44': 'N',
                            'T52F45': 'S' if party_code.upper() == 'ACASHACT' else 'R',
                            'T52F46': tax_type_flag,
                            'T52F75': '0',
                            'T52F97': '01',
                            'T52F98': f98
                        }
                        self._append_record(t52, t52_breakdown)

                    # B. RKACCT01 Records (Double Entry General Ledger Lines)
                    setup_id = purchase_setup_id if module == 'Purchases' else sales_setup_id
                    
                    # 1. Party line (PR)
                    party_dr_cr = 'C' if module == 'Purchases' else 'D'
                    party_amount = round(total - tds, 2)
                    t01_rec_party = {
                        'FIELD98': f98,
                        'FIELD99': f99,
                        'FIELD01': v_id,
                        'FIELD02': v_date,
                        'FIELD03': party_code,
                        'FIELD04': account_code,
                        'FIELD05': party_amount,  # Adjusted for TDS
                        'FIELD06': party_dr_cr,
                        'FIELD09': '   1',
                        'FIELD11': setup_id,
                        'FIELD12': t01_f12_val,
                        'T41FVNO': t41_fvno_val,
                        'FIELD15': t01_f15_val,
                        'FIELD16': t01_f16_val,
                        'FIELD20': 'N',
                        'FIELD21': 'PR',
                        'T01F97': '01',
                        'FIELD75': '0',
                        'T01F96': 'G'
                    }
                    self._append_record(t01, t01_rec_party, {'FIELD09': '   1'})
                    
                    # 2. Sales/Purchase line (TS/TP)
                    sales_dr_cr = 'D' if module == 'Purchases' else 'C'
                    t01_rec_sales = {
                        'FIELD98': f98,
                        'FIELD99': f99,
                        'FIELD01': v_id,
                        'FIELD02': v_date,
                        'FIELD03': account_code,
                        'FIELD04': party_code,
                        'FIELD05': net_taxable,  # Set to net_taxable
                        'FIELD06': sales_dr_cr,
                        'FIELD09': '   2',
                        'FIELD11': setup_id,
                        'FIELD12': t01_f12_val,
                        'T41FVNO': t41_fvno_val,
                        'FIELD15': t01_f15_val,
                        'FIELD16': t01_f16_val,
                        'FIELD20': 'N',
                        'FIELD21': 'TP' if module == 'Purchases' else 'TS',
                        'T01F97': '01',
                        'FIELD75': '0',
                        'T01F96': 'G'
                    }
                    self._append_record(t01, t01_rec_sales, {'FIELD09': '   2'})
                    
                    # 3. Tax lines (TX)
                    line_idx_t01 = 3
                    if cgst > 0:
                        cgst_ac = 'AGST0005' if module == 'Purchases' else 'AGST0008'
                        t01_rec_cgst = {
                            'FIELD98': f98,
                            'FIELD99': f99,
                            'FIELD01': v_id,
                            'FIELD02': v_date,
                            'FIELD03': cgst_ac,
                            'FIELD04': party_code,
                            'FIELD05': cgst,
                            'FIELD06': sales_dr_cr,
                            'FIELD09': f"{line_idx_t01:>4}",
                            'FIELD11': setup_id,
                            'FIELD12': t01_f12_val,
                            'T41FVNO': t41_fvno_val,
                            'FIELD15': t01_f15_val,
                            'FIELD16': t01_f16_val,
                            'FIELD20': 'N',
                            'FIELD21': 'TX',
                            'T01F97': '01',
                            'FIELD75': '0',
                            'T01F96': 'G'
                        }
                        self._append_record(t01, t01_rec_cgst, {'FIELD09': f"{line_idx_t01:>4}"})
                        line_idx_t01 += 1
                        
                    if sgst > 0:
                        sgst_ac = 'AGST0006' if module == 'Purchases' else 'AGST0009'
                        t01_rec_sgst = {
                            'FIELD98': f98,
                            'FIELD99': f99,
                            'FIELD01': v_id,
                            'FIELD02': v_date,
                            'FIELD03': sgst_ac,
                            'FIELD04': party_code,
                            'FIELD05': sgst,
                            'FIELD06': sales_dr_cr,
                            'FIELD09': f"{line_idx_t01:>4}",
                            'FIELD11': setup_id,
                            'FIELD12': t01_f12_val,
                            'T41FVNO': t41_fvno_val,
                            'FIELD15': t01_f15_val,
                            'FIELD16': t01_f16_val,
                            'FIELD20': 'N',
                            'FIELD21': 'TX',
                            'T01F97': '01',
                            'FIELD75': '0',
                            'T01F96': 'G'
                        }
                        self._append_record(t01, t01_rec_sgst, {'FIELD09': f"{line_idx_t01:>4}"})
                        line_idx_t01 += 1
                        
                    if igst > 0:
                        igst_ac = 'AGST0007' if module == 'Purchases' else 'AGST0010'
                        t01_rec_igst = {
                            'FIELD98': f98,
                            'FIELD99': f99,
                            'FIELD01': v_id,
                            'FIELD02': v_date,
                            'FIELD03': igst_ac,
                            'FIELD04': party_code,
                            'FIELD05': igst,
                            'FIELD06': sales_dr_cr,
                            'FIELD09': f"{line_idx_t01:>4}",
                            'FIELD11': setup_id,
                            'FIELD12': t01_f12_val,
                            'T41FVNO': t41_fvno_val,
                            'FIELD15': t01_f15_val,
                            'FIELD16': t01_f16_val,
                            'FIELD20': 'N',
                            'FIELD21': 'TX',
                            'T01F97': '01',
                            'FIELD75': '0',
                            'T01F96': 'G'
                        }
                        self._append_record(t01, t01_rec_igst, {'FIELD09': f"{line_idx_t01:>4}"})
                        line_idx_t01 += 1

                    # 3.5. Extra double-entries for Freight, TCS, and TDS (if matched in RKACCM01)
                    if freight > 0:
                        freight_ledger = resolved_freight_ledger
                        if freight_ledger:
                            freight_rec = {
                                'FIELD98': f98,
                                'FIELD99': f99,
                                'FIELD01': v_id,
                                'FIELD02': v_date,
                                'FIELD03': freight_ledger,
                                'FIELD04': party_code,
                                'FIELD05': freight,
                                'FIELD06': sales_dr_cr,  # Credit for Sales, Debit for Purchases
                                'FIELD09': f"{line_idx_t01:>4}",
                                'FIELD11': setup_id,
                                'FIELD12': t01_f12_val,
                                'T41FVNO': t41_fvno_val,
                                'FIELD15': t01_f15_val,
                                'FIELD16': t01_f16_val,
                                'FIELD20': 'N',
                                'FIELD21': 'PT',
                                'T01F97': '01',
                                'FIELD75': '0',
                                'T01F96': 'G'
                            }
                            self._append_record(t01, freight_rec, {'FIELD09': f"{line_idx_t01:>4}"})
                            line_idx_t01 += 1
                        else:
                            print(f"Warning: Freight ledger not found in database. Omitted posting line.")
                            
                    if tcs > 0:
                        tcs_ledger = resolved_tcs_ledger
                        if tcs_ledger:
                            tcs_rec = {
                                'FIELD98': f98,
                                'FIELD99': f99,
                                'FIELD01': v_id,
                                'FIELD02': v_date,
                                'FIELD03': tcs_ledger,
                                'FIELD04': party_code,
                                'FIELD05': tcs,
                                'FIELD06': sales_dr_cr,  # Credit for Sales, Debit for Purchases
                                'FIELD09': f"{line_idx_t01:>4}",
                                'FIELD11': setup_id,
                                'FIELD12': t01_f12_val,
                                'T41FVNO': t41_fvno_val,
                                'FIELD15': t01_f15_val,
                                'FIELD16': t01_f16_val,
                                'FIELD20': 'N',
                                'FIELD21': 'PT',
                                'T01F97': '01',
                                'FIELD75': '0',
                                'T01F96': 'G'
                            }
                            self._append_record(t01, tcs_rec, {'FIELD09': f"{line_idx_t01:>4}"})
                            line_idx_t01 += 1
                        else:
                            print(f"Warning: TCS ledger not found in database. Omitted posting line.")

                    if tds > 0:
                        tds_ledger = resolved_tds_ledger
                        if tds_ledger:
                            tds_rec = {
                                'FIELD98': f98,
                                'FIELD99': f99,
                                'FIELD01': v_id,
                                'FIELD02': v_date,
                                'FIELD03': tds_ledger,
                                'FIELD04': party_code,
                                'FIELD05': tds,
                                'FIELD06': party_dr_cr,  # Debit for Sales, Credit for Purchases
                                'FIELD09': f"{line_idx_t01:>4}",
                                'FIELD11': setup_id,
                                'FIELD12': t01_f12_val,
                                'T41FVNO': t41_fvno_val,
                                'FIELD15': t01_f15_val,
                                'FIELD16': t01_f16_val,
                                'FIELD20': 'N',
                                'FIELD21': 'PT',
                                'T01F97': '01',
                                'FIELD75': '0',
                                'T01F96': 'G'
                            }
                            self._append_record(t01, tds_rec, {'FIELD09': f"{line_idx_t01:>4}"})
                            line_idx_t01 += 1
                        else:
                            print(f"Warning: TDS ledger not found in database. Omitted posting line.")

                    # 4. Round-off line (PT)
                    if round_off != 0:
                        if module == 'Purchases':
                            ro_dr_cr = 'D' if round_off > 0 else 'C'
                        else:
                            ro_dr_cr = 'C' if round_off > 0 else 'D'
                            
                        t01_rec_ro = {
                            'FIELD98': f98,
                            'FIELD99': f99,
                            'FIELD01': v_id,
                            'FIELD02': v_date,
                            'FIELD03': 'AVAUTO99',
                            'FIELD04': party_code,
                            'FIELD05': abs(round_off),
                            'FIELD06': ro_dr_cr,
                            'FIELD09': f"{line_idx_t01:>4}",
                            'FIELD11': setup_id,
                            'FIELD12': t01_f12_val,
                            'T41FVNO': t41_fvno_val,
                            'FIELD15': t01_f15_val,
                            'FIELD16': t01_f16_val,
                            'FIELD20': 'N',
                            'FIELD21': 'PT',
                            'T01F97': '01',
                            'FIELD75': '0',
                            'T01F96': 'G'
                        }
                        self._append_record(t01, t01_rec_ro, {'FIELD09': f"{line_idx_t01:>4}"})

                    injected_count += 1
                    self.audit_report["injected"] += 1
                
            finally:
                # Ensure CDX flags in byte 28 are 100% active
                self.ensure_cdx_flags_active(year_folder)
                t41.close()
                t02.close()
                t52.close()
                t01.close()
                if t40: t40.close()
            
        # Compact modified tables to reclaim space and prune deleted records
        for tbl in ['rkacct41.dbf', 'rkacct01.dbf', 'rkacct02.dbf', 'rkacct52.dbf', 'rkacct40.dbf']:
            self.compact_table(tbl, year_folder)
                
        # Trigger automated re-indexing (Fallback for Windows users if pyodbc works)
        self.reindex_tables(year_folder)
        
        # Self-healing narration repair pass
        try:
            self.repair_all_voucher_narrations(year_folder)
        except Exception as e:
            print(f"Warning: repair_all_voucher_narrations failed: {e}")

        return injected_count


    BANK_EXPENSE_KEYWORDS = {
        'BANK CHARGES', 'BANK CHARGE', 'BANK FEE', 'BANK FEES', 'BANK COMM', 'BANK COMMISSION',
        'BANK INTEREST', 'SMS CHARGES', 'SMS CHGS', 'SERVICE CHARGES', 'PROCESSING FEE',
        'PROCESSING FEES', 'MDR CHARGES', 'MDR RECOVERY', 'RUPAY MDR', 'CARD CHARGES',
        'POS CHARGES', 'MIN BAL', 'MINIMUM BALANCE', 'CHQ RET', 'CHEQUE RETURN', 'CHQ DEP RET',
        'DEBIT CARD FEE', 'ANNUAL FEE', 'FOREX CHARGES', 'GST ON BANK', 'PENALTY', 'INTEREST PAID'
    }

    def is_true_contra_entry(self, party_name: str, party_code: str, code_to_classification: dict, party_group_code: str = "") -> bool:
        """
        Determines if a transaction is a genuine Contra entry (fund transfer between OWN Cash/Bank accounts).
        
        STRICT ACCOUNTING RULES:
        1. Contra (BC/CV) is ONLY for movement of funds between OWN Cash and Bank accounts.
        2. Customer payments, vendor payments, expenses, and suspense entries are NEVER Contra!
        """
        if not party_code:
            return False

        if party_code == 'ACASHACT':
            return True

        party_class = code_to_classification.get(party_code, 'Other')
        grp_up = (party_group_code or "").strip().upper()

        # 1. HARD EXCLUSION: Debtors, Creditors, Expenses, Income, Taxes, Sales, Purchases, or Suspense -> NEVER Contra!
        if party_class in ('Expense', 'Indirect Expenses', 'Direct Expenses', 'Income', 'Indirect Income', 'Debtor', 'Sundry Debtors', 'Creditor', 'Sundry Creditors', 'Duties & Taxes'):
            return False
            
        if grp_up in ('G0000009', 'G0000013', 'G0000017', 'G0000016', 'G0000003', 'G0000011', 'G0000012', 'G0000028', 'SUNDRY DEBTORS', 'SUNDRY CREDITORS', 'INDIRECT EXPENSES', 'INDIRECT INCOME'):
            return False

        name_up = (party_name or "").strip().upper()
        
        # 2. HARD EXCLUSION: Any bank charge, fee, or expense keyword is NEVER Contra!
        if any(kw in name_up for kw in getattr(self, 'BANK_EXPENSE_KEYWORDS', [])):
            return False

        # 3. CASH ACCOUNT CONTRA: Only if classified as Cash/Cash-in-Hand (G0000005) or exact Cash name
        CASH_EXPACT = ('CASH ACCOUNT', 'CASH A/C', 'PETTY CASH', 'CASH IN HAND', 'CASH')
        if party_class in ('Cash', 'Cash-in-Hand') or grp_up == 'G0000005':
            return True
        if name_up in CASH_EXPACT and party_class != 'Expense':
            return True

        # 4. BANK-TO-BANK CONTRA: Only if explicitly classified as Bank Accounts (G0000004) AND NOT an expense/party
        if (party_class == 'Bank' or grp_up in ('G0000004', 'BANK ACCOUNTS')) and not any(exp in name_up for exp in ['EXP', 'FEE', 'CHG', 'COMM', 'INT', 'TAX', 'DUTY', 'CHARGE']):
            return True

        return False

    def _inject_bank_statements(self, vouchers: list, payload_bank_name: str = "Bank Account", year_folder: str = "", force_push: bool = False) -> int:
        if isinstance(payload_bank_name, str) and (payload_bank_name.upper().startswith("YR") or not year_folder):
            year_folder = payload_bank_name
            payload_bank_name = "Bank Account"
        import os
        import dbf
        import random
        import string
        from datetime import datetime, date

        injected_count = 0
        t41_path = self._get_table_path('rkacct41.dbf', year_folder)
        t01_path = self._get_table_path('rkacct01.dbf', year_folder)
        t40_path = self._get_table_path('rkacct40.dbf', year_folder)
        m01_path = self._get_table_path('rkaccm01.dbf', year_folder)
        
        # Auto-detect T41F83 print series option from backdata
        detected_cfg = self.detect_format_settings(year_folder, ['BR', 'BP', 'BC'])
        resolved_f83 = detected_cfg["f83"]

        # 1. Build CROSS-YEAR ledger lookup map.
        # CRITICAL FIX (Bug #15): read_ledgers() only reads the current year's RKACCM01.DBF.
        # When Miracle creates a new year, it copies the ledger master at that point in time.
        # Any party created in YR25 is NOT in YR26's copy → push code thinks it's new → creates duplicate.
        # Solution: merge ledgers from ALL year folders so we find any party added in any year.
        print(f"[bank push] Building cross-year ledger lookup for duplicate prevention...")
        all_ledgers = self.read_ledgers_all_years(active_year_folder=year_folder)
        
        # 1a. Resolve Bank Ledger — SMART 4-LEVEL MATCHING (Bug #16 fix)
        # Problem: bank statement says "HDFC Bank Ltd." but Miracle ledger is "HDFC BANK A/C"
        # Exact and substring matches both FAIL because "LTD" ≠ "A/C" and "LIMITED" ≠ "A/C"
        # Solution: extract the bank BRAND (HDFC, ICICI, SBI, AXIS...) and match on that
        
        KNOWN_BANK_BRANDS = [
            # Top Indian Private Banks
            'HDFC', 'ICICI', 'AXIS', 'KOTAK', 'INDUSIND', 'YES BANK', 'BANDHAN', 'FEDERAL', 
            'IDFC', 'IDFC FIRST', 'RBL', 'RATNAKAR', 'SOUTH INDIAN', 'KARNATAKA BANK', 
            'CITY UNION', 'CUB', 'KARUR VYSYA', 'KVB', 'TAMILNAD MERCANTILE', 'TMB', 
            'JAMMU & KASHMIR', 'J&K', 'CSB', 'CATHOLIC SYRIAN', 'DHANALAKSHMI',
            
            # Top Indian PSU / Public Sector Banks
            'SBI', 'STATE BANK', 'BANK OF BARODA', 'BOB', 'PNB', 'PUNJAB NATIONAL', 
            'CANARA', 'UNION BANK', 'UBI', 'INDIAN BANK', 'BANK OF INDIA', 'BOI', 
            'CENTRAL BANK', 'CBI', 'UCO', 'BANK OF MAHARASHTRA', 'BOM', 'IOB', 
            'INDIAN OVERSEAS', 'PUNJAB & SIND', 'PSB', 'IDBI', 'DENA', 'VIJAYA', 
            'SYNDICATE', 'OBC', 'ORIENTAL BANK', 'ALLAHABAD', 'ANDHRA BANK', 'CORPORATION BANK',
            
            # Small Finance & Payments Banks
            'AU SMALL', 'AU BANK', 'EQUITAS', 'UJJIVAN', 'SURYODAY', 'JANA', 'ESAF', 
            'UTKARSH', 'FINCARE', 'CAPITAL SMALL', 'PAYTM', 'PHONEPE', 'AIRTEL PAYMENTS', 
            'FINO', 'INDIA POST', 'IPPB',
            
            # Co-operative & Gujarat / Regional / Gramin Banks
            'SARASWAT', 'COSMOS', 'SVC', 'SHAMRAO VITHAL', 'BHARAT CO-OP', 'NKGSB', 
            'ABHYUDAYA', 'KALUPUR', 'GUJARAT STATE CO-OP', 'GSCB', 'NUTAN NAGARIK', 
            'SURAT NATIONAL', 'RAJKOT NAGARIK', 'REVENUE CO-OP', 'BARODA GUJARAT GRAMIN', 
            'SAURASHTRA GRAMIN', 'PRATHAMA', 'KERALA GRAMIN', 'MAHARASHTRA GRAMIN', 
            'KARNATAKA GRAMIN', 'COOPERATIVE', 'CO-OP', 'GRAMIN', 'NAGARIK', 'URBAN',
            
            # Foreign & International Banks
            'CITIBANK', 'CITI', 'STANDARD CHARTERED', 'STANCHAR', 'HSBC', 'DBS', 
            'BARCLAYS', 'DEUTSCHE', 'JP MORGAN', 'J P MORGAN', 'BANK OF AMERICA', 
            'BOLA', 'BNP PARIBAS', 'SOCIETE GENERALE', 'MUFG', 'SMBC', 'MIZUHO', 'SBERBANK'
        ]
        
        def extract_bank_brand(name: str) -> str:
            """Extract the core bank brand keyword from a ledger/bank name."""
            name_up = name.strip().upper()
            for brand in KNOWN_BANK_BRANDS:
                if brand in name_up:
                    return brand
            return ""
        
        bank_ledger_code = ""
        bank_name = payload_bank_name or "Suspense Bank A/c"
        bank_name_up = bank_name.strip().upper()
        input_brand = extract_bank_brand(bank_name)
        
        # Strictly filter ONLY genuine Bank Account ledgers (Group G0000004 or classification 'Bank')
        # Explicitly exclude non-bank system accounts like Profit & Loss (PROFLOSS), Trading, Capital, GST, etc.
        NON_BANK_KEYWORDS = ['PROFIT', 'P&L', 'LOSS', 'TRADING', 'CAPITAL', 'DRAWINGS', 'TAX', 'DUTY', 'GST', 'IGST', 'CGST', 'SGST']
        
        bank_classified_ledgers = [
            led for led in all_ledgers
            if (led.get('classification') == 'Bank'
                or led.get('group_code') == 'G0000004'
                or 'BANK' in (led.get('name') or '').upper()
                or 'BANK' in (led.get('group_name') or '').upper())
            and not any(bad in (led.get('name') or '').upper() for bad in NON_BANK_KEYWORDS)
            and led.get('code') != 'PROFLOSS'
        ]

        # Level 1: Exact name match (only among bank-classified ledgers)
        for led in bank_classified_ledgers:
            if led['name'].strip().upper() == bank_name_up:
                bank_ledger_code = led['code']
                print(f"[bank resolve] ✅ Level 1 (exact bank): '{bank_name}' → '{led['name']}' ({led['code']})")
                break
        
        # Level 2: Substring partial match (only among bank-classified ledgers)
        if not bank_ledger_code:
            for led in bank_classified_ledgers:
                led_name_up = led['name'].strip().upper()
                if bank_name_up in led_name_up or led_name_up in bank_name_up:
                    bank_ledger_code = led['code']
                    print(f"[bank resolve] ✅ Level 2 (substring bank): '{bank_name}' → '{led['name']}' ({led['code']})")
                    break
        
        # Level 3: Bank BRAND keyword match
        # "HDFC Bank Ltd" and "HDFC BANK A/C" both contain "HDFC" → same bank!
        if not bank_ledger_code and input_brand:
            for led in bank_classified_ledgers:
                led_brand = extract_bank_brand(led['name'])
                if led_brand and led_brand == input_brand:
                    bank_ledger_code = led['code']
                    print(f"[bank resolve] ✅ Level 3 (brand keyword '{input_brand}'): '{bank_name}' → '{led['name']}' ({led['code']})")
                    break
        
        # Level 4: Fuzzy string match (only among bank-classified ledgers, cutoff 0.60)
        if not bank_ledger_code:
            import difflib
            bank_names_only = [led['name'].upper() for led in bank_classified_ledgers]
            fuzzy_matches = difflib.get_close_matches(bank_name_up, bank_names_only, n=1, cutoff=0.60)
            if fuzzy_matches:
                matched_name = fuzzy_matches[0]
                for led in bank_classified_ledgers:
                    if led['name'].upper() == matched_name:
                        bank_ledger_code = led['code']
                        print(f"[bank resolve] ✅ Level 4 (fuzzy 0.60): '{bank_name}' → '{led['name']}' ({led['code']})")
                        break
        
        if not bank_ledger_code:
            # Level 5: If company has bank-classified ledgers in Miracle DBF, pick primary existing Bank Ledger
            if bank_classified_ledgers:
                first_bank = bank_classified_ledgers[0]
                bank_ledger_code = first_bank['code']
                print(f"[bank resolve] ⚡ Level 5 (existing bank fallback): Auto-selected primary company bank ledger '{first_bank['name']}' ({first_bank['code']})")
            else:
                print(f"[bank resolve] ⚠️ No match found for '{bank_name}' — creating new ledger.")
                bank_ledger_code = self.create_party_ledger(bank_name, 'Bank Statements', year_folder=year_folder)


        # 1b. Build name→code lookup from ALL years
        # If same name found in active year, that code takes priority (handled by read_ledgers_all_years)
        name_to_code = {led['name'].upper(): led['code'] for led in all_ledgers}
        ledger_sources = {led['code']: led.get('year_folder') for led in all_ledgers}
        
        # 1c. Also build a code→classification map from all_ledgers
        ledgers = all_ledgers  # use same merged list for everything below
        
        # 1d. Suspense logic
        suspense_name = "Suspense Account"
        suspense_code = ""
        for led in all_ledgers:
            if "SUSPENSE" in led['name'].upper():
                suspense_code = led['code']
                suspense_name = led['name']
                break
        if not suspense_code:
            suspense_code = self.create_party_ledger(suspense_name, 'Bank Statements', year_folder=year_folder)
            name_to_code[suspense_name.upper()] = suspense_code

        def gen_id(pfx):
            num = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
            return pfx[:2] + num

        # Let's find last voucher numbers for BR, BP, CV and build duplicate index
        last_br = 0
        last_bp = 0
        last_cv = 0
        existing_bank_entries = []  # Changed to list of dicts for robust fuzzy matching
        if os.path.exists(t41_path):
            with self.safe_cdx_context(t41_path):
                t41_lookup = dbf.Table(t41_path)
                t41_lookup.open(mode=dbf.READ_ONLY)
                for r in t41_lookup:
                    if dbf.is_deleted(r):
                        continue
                    v_type = str(r['FIELD98']).strip()
                    if v_type not in ['BR', 'BP', 'CV', 'BC']:
                        continue
                        
                    try:
                        v_num = int(str(r['T41FVNO']).strip())
                    except:
                        v_num = 0
                        
                    if v_type == 'BR':
                        last_br = max(last_br, v_num)
                    elif v_type == 'BP':
                        last_bp = max(last_bp, v_num)
                    elif v_type in ('CV', 'BC'):
                        last_cv = max(last_cv, v_num)
                        
                    # CRITICAL FIX: r.get() does NOT work on DBF records (always returns None).
                    # Must access fields directly in try/except.
                    try:
                        v_dt = str(r['FIELD02']).strip()
                        p_code = str(r['FIELD04']).strip()
                        b_code = str(r['FIELD05']).strip()
                        amt = float(str(r['FIELD06']).strip() or 0)
                        try:
                            ref_num = str(r['FIELD10']).strip().lower()
                        except:
                            ref_num = ''
                        try:
                            # Narration stored as first 50 chars in T41 FIELD82
                            narr = str(r['FIELD82']).strip().lower()[:50]
                        except:
                            narr = ''
                        
                        existing_bank_entries.append({
                            'v_dt': v_dt,
                            'amt': round(amt, 2),
                            'p_code': p_code,
                            'b_code': b_code,
                            'v_type': v_type,
                            'ref_num': ref_num,
                            'narr': narr,
                            'used': False
                        })
                    except Exception as e:
                        pass
                        
                t41_lookup.close()


        year_num = int(year_folder[-2:]) if year_folder and year_folder[-2:].isdigit() else 27

        # Read classifications for dynamic FIELD21 mapping
        code_to_classification = {led['code']: led.get('classification', 'Other') for led in ledgers}
        
        # intra_batch_seen: prevents the same entry from being written TWICE within
        # this single push call (the root cause of the doubled T41+T01 journal bug).
        intra_batch_seen = set()
        t40 = None
        backup_list_bank = [t41_path, t01_path]
        if os.path.exists(t40_path):
            backup_list_bank.append(t40_path)

        with self.backup_transaction_context(backup_list_bank), \
             self.safe_cdx_context(t41_path), self.safe_cdx_context(t01_path):
            t41 = dbf.Table(t41_path)
            t01 = dbf.Table(t01_path)
            self._open_table_with_retry(t41, mode=dbf.READ_WRITE)
            self._open_table_with_retry(t01, mode=dbf.READ_WRITE)

            if os.path.exists(t40_path):
                try:
                    t40 = dbf.Table(t40_path)
                    self._open_table_with_retry(t40, mode=dbf.READ_WRITE)
                except Exception as ex_t40:
                    print(f"⚠️ Warning: Could not open RKACCT40 for bank/cash write: {ex_t40}")
                    t40 = None
            
            guids_to_register = []
            try:
                for idx, v in enumerate(vouchers):
                    line_idx_t01 = 1
                    tx_type = (v.get('transaction_type') or 'Receipt').strip().capitalize()
                    # Normalize: frontend may send 'CV (Contra)' for contra entries; ensure only 'Receipt' or 'Payment'
                    if tx_type.lower() not in ('receipt', 'payment'):
                        tx_type = 'Receipt'  # Safe default
                    amount = self._parse_float(v.get('amount') or v.get('total') or 0.0)
                    party_name = (v.get('party_name') or v.get('party') or '').strip()
                    narration = (v.get('narration') or v.get('narr') or v.get('description') or v.get('raw_narration') or party_name).strip()
                    if not narration:
                        narration = f"Bank {tx_type} - {party_name if party_name else 'Suspense'}"

                    if not party_name or party_name.startswith('UNKNOWN') or "SUSPENSE" in party_name.upper():
                        party_code = suspense_code
                        if not party_name or party_name.startswith('UNKNOWN'):
                            self.audit_report["missing_parties"] += 1
                            self.audit_report["messages"].append(f"Mapped unknown party to Suspense Account (Amount: ₹{v.get('amount', 0)})")
                    else:
                        party_up = party_name.upper()
                        CASH_ALIASES = ('CASH', 'CASH ACCOUNT', 'CASH A/C', 'CASH AC', 'PETTY CASH', 'CASH-IN-HAND', 'CASH HAND', 'PETTY CASH ACCOUNT')
                        party_code = None
                        
                        # 1. Smart Cash ledger resolution: match any existing Cash-classified ledger in Miracle
                        if party_up in CASH_ALIASES or "CASH" in party_up:
                            for led in all_ledgers:
                                is_cash_cls = led.get('classification') == 'Cash' or led.get('group_code') == 'G0000005'
                                name_is_cash = led['name'].strip().upper() in CASH_ALIASES
                                if is_cash_cls or name_is_cash:
                                    party_code = led['code']
                                    print(f"✅ Resolved Cash Account to existing Miracle cash ledger: '{led['name']}' ({party_code})")
                                    break
                                    
                        if not party_code:
                            party_code = name_to_code.get(party_up)
                            
                        if not party_code:
                            import difflib
                            matches = difflib.get_close_matches(party_up, list(name_to_code.keys()), n=1, cutoff=0.80)
                            if matches:
                                party_code = name_to_code[matches[0]]
                                print(f"✅ Fuzzy matched Bank party: {party_name} -> {matches[0]} ({party_code})")
                            else:
                                party_code = self.create_party_ledger(party_name, 'Bank Statements', year_folder=year_folder, transaction_type=tx_type, group_hint=v.get('group_hint', ''))
                                name_to_code[party_up] = party_code
                                
                        # CRITICAL CROSS-YEAR SYNC FIX (Bug #28):
                        # If the resolved party code exists in another year but is missing in the current year,
                        # sync it from the source year to the current year immediately to prevent blank names in Miracle UI.
                        if party_code:
                            src_year = ledger_sources.get(party_code)
                            if src_year and src_year != year_folder:
                                current_m01 = self._get_table_path('rkaccm01.dbf', year_folder)
                                if not os.path.exists(current_m01): current_m01 = self._get_table_path('RKACCM01.DBF', year_folder)
                                
                                exists_in_current = False
                                if os.path.exists(current_m01):
                                    try:
                                        with self.safe_cdx_context(current_m01):
                                            t = dbf.Table(current_m01)
                                            t.open(mode=dbf.READ_ONLY)
                                            exists_in_current = any(str(r['FIELD01']).strip() == party_code for r in t if not dbf.is_deleted(r))
                                            t.close()
                                    except Exception as e:
                                        print(f"Error checking current year {year_folder} for {party_name}: {e}")
                                
                                if not exists_in_current:
                                    print(f"Syncing existing ledger {party_name} ({party_code}) from {src_year} to current year {year_folder}...")
                                    self._sync_party_to_other_years(party_name, party_code, src_year, target_year_folder=year_folder)

                        # USER GROUP OVERRIDE SYNC:
                        # If the user changed the group in the UI grid, ensure the group code in RKACCM01.DBF
                        # is updated and synced across all financial year directories!
                        user_gh = str(v.get('group_hint') or '').strip()
                        if party_code and user_gh and party_code != suspense_code:
                            target_grp = self.resolve_group_code_from_hint(user_gh)
                            if target_grp:
                                try:
                                    self.update_party_ledger(party_name, party_name, group_code=target_grp, year_folder=year_folder)
                                except Exception as grp_err:
                                    print(f"⚠️ Warning: Could not update group code for {party_name} ({party_code}): {grp_err}")
                    
                    if amount <= 0:
                        continue
                        
                    date_str = v.get('date', '')
                    try:
                        v_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                    except:
                        v_date = date.today()
                        
                    f98 = 'BR' if tx_type == 'Receipt' else 'BP'
                    party_class = code_to_classification.get(party_code, 'Other')
                    if self.is_true_contra_entry(party_name, party_code, code_to_classification, party_group_code=v.get('group_hint', '')):
                        f98 = 'BC'
                        self.audit_report["messages"].append(f"Auto-generated Contra Voucher (BC) for Cash/Bank {tx_type}: ₹{amount}")
                        
                    # Anomaly Detection (Rule of thumb > 5 Lakhs for Bank)
                    if amount > 500000:
                        self.audit_report["anomalies"] += 1
                        self.audit_report["messages"].append(f"High-Value Transaction Anomaly: ₹{amount} ({party_name})")
                    
                    ref_no = (v.get('reference_no') or v.get('bill_no') or '')[:16]
                    ref_no_clean = ref_no.strip().lower()
                    # CRITICAL FIX: narration key must match stored length (50 chars)
                    narration_clean = narration[:50].strip().lower()

                    # ── INTRA-BATCH DEDUP: Block identical rows within the same push ──────────
                    batch_key = (str(v_date), round(amount, 2), party_name.upper(), f98, ref_no_clean, narration_clean)
                    if batch_key in intra_batch_seen:
                        print(f"🚫 Intra-batch duplicate blocked: {party_name} {amount} {v_date}")
                        self.audit_report["duplicates"] += 1
                        self.audit_report["duplicate_details"].append({
                            "date": str(v_date),
                            "bill_no": ref_no.strip(),
                            "party": party_name,
                            "amount": amount,
                            "reason": "Duplicate row in same push batch",
                            "module": "Bank Statements"
                        })
                        continue
                    intra_batch_seen.add(batch_key)
                    # ────────────────────────────────────────────────────────────────────────

                    # Duplicate Detection vs EXISTING Miracle entries
                    # Robust Fuzzy Matching — consuming 1 matching entry per AI row
                    is_dup = False
                    dup_reason_str = ""
                    tx_label = 'Receipt' if f98 == 'BR' else ('Payment' if f98 == 'BP' else 'Contra')
                    v_date_str = str(v_date)
                    amount_rnd = round(amount, 2)
                    
                    # Pass 1: Exact Match
                    for ex in existing_bank_entries:
                        if not ex['used'] and ex['v_dt'] == v_date_str and ex['amt'] == amount_rnd and ex['b_code'] == bank_ledger_code and ex['v_type'] == f98 and ex['p_code'] == party_code and ex['ref_num'] == ref_no_clean and ex['narr'] == narration_clean:
                            is_dup = True
                            ex['used'] = True
                            dup_reason_str = f"Already in Miracle (Exact Match)"
                            break
                            
                    # Pass 2: Cheque No Match (Highly reliable)
                    if not is_dup and ref_no_clean:
                        for ex in existing_bank_entries:
                            if not ex['used'] and ex['v_dt'] == v_date_str and ex['amt'] == amount_rnd and ex['b_code'] == bank_ledger_code and ex['v_type'] == f98 and ex['ref_num'] == ref_no_clean:
                                is_dup = True
                                ex['used'] = True
                                dup_reason_str = f"Already in Miracle (Matched Cheque No)"
                                break
                                
                    # Pass 3: Party Match
                    if not is_dup:
                        for ex in existing_bank_entries:
                            # UTR/Cheque number mismatch guard: if both have different reference numbers, they are NOT duplicates!
                            if ex['ref_num'] and ref_no_clean and ex['ref_num'] != ref_no_clean:
                                continue
                            if not ex['used'] and ex['v_dt'] == v_date_str and ex['amt'] == amount_rnd and ex['b_code'] == bank_ledger_code and ex['v_type'] == f98 and ex['p_code'] == party_code:
                                is_dup = True
                                ex['used'] = True
                                dup_reason_str = f"Already in Miracle (Matched Party & Amount)"
                                break
                                
                    # Pass 4: Amount Match (Safe because of the 'used' flag!)
                    if not is_dup:
                        for ex in existing_bank_entries:
                            # UTR/Cheque number mismatch guard: if both have different reference numbers, they are NOT duplicates!
                            if ex['ref_num'] and ref_no_clean and ex['ref_num'] != ref_no_clean:
                                continue
                            if not ex['used'] and ex['v_dt'] == v_date_str and ex['amt'] == amount_rnd and ex['b_code'] == bank_ledger_code and ex['v_type'] == f98:
                                # ONLY match by amount if the party matches OR if at least one is Suspense
                                if ex['p_code'] == party_code or ex['p_code'] == suspense_code or party_code == suspense_code:
                                    is_dup = True
                                    ex['used'] = True
                                    dup_reason_str = f"Already in Miracle (Matched Amount)"
                                    break

                    if is_dup and not force_push:
                        self.audit_report["duplicates"] += 1
                        self.audit_report["duplicate_details"].append({
                            "date": v_date_str,
                            "bill_no": ref_no.strip(),
                            "party": party_name,
                            "amount": amount,
                            "reason": f"{dup_reason_str} [{tx_label}]",
                            "module": "Bank Statements"
                        })
                        continue
                        
                    if f98 == 'BR':
                        last_br += 1
                        vou_no = last_br
                    elif f98 == 'BP':
                        last_bp += 1
                        vou_no = last_bp
                    else:
                        last_cv += 1
                        vou_no = last_cv

                    v_id = gen_id(f98)
                    
                    # 1. T41 Header
                    t41_rec = {
                        'FIELD98': f98,
                        'FIELD99': f98,
                        'FIELD01': v_id,
                        'FIELD02': v_date,
                        'FIELD03': 2,       # Integer 2 matching native Miracle DBF specification
                        'FIELD04': party_code,
                        'FIELD05': bank_ledger_code,
                        'FIELD06': amount,
                        'FIELD07': amount,
                        'FIELD10': ref_no.strip(),  # Chq/DD No.
                        'FIELD11': v_date,  # Chq/DD Date
                        'FIELD12': str(vou_no),
                        'FIELD14': 'N',
                        'FIELD16': 'C' if f98 == 'BC' else ('R' if tx_type == 'Receipt' else 'P'),  # BC=Contra ('C'), BR=Receipt ('R'), BP=Payment ('P')
                        'FIELD17': 'UU000001', # Matching native Miracle DBF user/unit specification
                        'FIELD18': 0.0,
                        'FIELD20': 0,
                        'FIELD21': 'O',    # Aligned with native Cash/Bank voucher type
                        'FIELD51': 0.0,
                        'FIELD74': 'CB',   # Aligned with native Cash/Bank voucher type
                        'FIELD75': '0',
                        'FIELD82': self.fit_dbf_str(narration, 50), # Narration
                        'T41F83': '9   ' if f98 == 'BC' else '1   ',     # Native Miracle Contra flag ('9   ' for Contra, '1   ' for Bank)
                        'T41FVNO': str(vou_no),
                        'T41F45': year_num,
                        'T41F97': '01',
                        'T41F96': 'N',
                        'EDVAS00095': 0.0,
                        'EPVAS00095': 0.0,
                        'EDVAS00097': 0.0,
                        'EPVAS00097': 0.0,
                        'EDGAS00001': 0.0,
                        'EPGAS00001': 0.0,
                        'EDGAS00002': 0.0,
                        'EPGAS00002': 0.0,
                        'EDGAS00003': 0.0,
                        'EPGAS00003': 0.0,
                        'EDVAS00099': 0.0,
                        'EPVAS00099': 0.0
                    }
                    self._append_record(t41, t41_rec)
                    guids_to_register.append(('YRT41', v_id, True))
                    
                    # 2. T01 Line 1: Bank Ledger
                    # CRITICAL FIX (Bug #17): FIELD20 must be 'N' (not 'C') and T01F96 must be 'G' (not 'N')
                    # FIELD20='C' means Cleared/Cancelled — Miracle skips these in balance calculations → closing balance never updates
                    # T01F96='N' excludes the line from balance reports — must be 'G' (General) like Sales/Purchase T01 lines
                    is_contra = (f98 == 'BC')
                    t01_f96_val = 'N'
                    t01_f22_val = None if is_contra else v_date
                    bank_dr_cr = 'D' if tx_type == 'Receipt' else 'C'
                    t01_rec_bank = {
                        'FIELD98': f98,
                        'FIELD99': f98,
                        'FIELD01': v_id,
                        'FIELD02': v_date,
                        'FIELD03': bank_ledger_code,
                        'FIELD04': party_code,
                        'FIELD05': amount,
                        'FIELD06': bank_dr_cr,
                        'FIELD08': 0.0,
                        'FIELD09': f"{line_idx_t01:>4}",
                        'FIELD11': 2,        # Integer 2 matching native Miracle DBF specification
                        'FIELD12': str(vou_no),
                        'T41FVNO': str(vou_no),
                        'FIELD15': ref_no.strip(),
                        'FIELD16': v_date,
                        'FIELD20': 'N',   # 'N' = Normal active line (Native Miracle requirement so amounts display in Ledger reports)
                        'FIELD21': 'BK',
                        'FIELD22': t01_f22_val,  # Reconciliation / clearance date
                        'FIELD26': 0.0,
                        'FIELD29': 0.0,
                        'T01F97': '01',
                        'FIELD75': '0',
                        'T01F96': 'N'     # FIXED: 'N' for all Cash/Bank lines
                    }
                    self._append_record(t01, t01_rec_bank, {'FIELD09': f"{line_idx_t01:>4}"})
                    line_idx_t01 += 1
                    
                    # 3. T01 Line 2: Party Ledger
                    # Native Miracle uses 'PR' (Party) for Party, 'PT' (Payment/Receipt) for Expenses/Others
                    party_dr_cr = 'C' if tx_type == 'Receipt' else 'D'
                    other_class = code_to_classification.get(party_code, 'Other')
                    if not self.is_true_contra_entry(party_name, party_code, code_to_classification, party_group_code=v.get('group_hint', '')) and (other_class in ('Expense', 'Indirect Expenses', 'Direct Expenses') or any(kw in party_name.upper() for kw in self.BANK_EXPENSE_KEYWORDS)):
                        resolved_f21 = 'PT'
                    elif other_class == 'Bank':
                        resolved_f21 = 'BK'
                    elif other_class == 'Cash' or party_name.upper() in ('CASH ACCOUNT', 'CASH A/C', 'PETTY CASH'):
                        resolved_f21 = 'CS'
                    elif other_class in ('Debtor', 'Creditor'):
                        resolved_f21 = 'PR'
                    else:
                        resolved_f21 = 'PT'
                        
                    party_f16_val = None if is_contra else v_date
                    party_f22_val = None if is_contra else v_date
                    
                    t01_rec_party = {
                        'FIELD98': f98,
                        'FIELD99': f98,
                        'FIELD01': v_id,
                        'FIELD02': v_date,
                        'FIELD03': party_code,
                        'FIELD04': bank_ledger_code,
                        'FIELD05': amount,
                        'FIELD06': party_dr_cr,
                        'FIELD08': 0.0,
                        'FIELD09': f"{line_idx_t01:>4}",
                        'FIELD11': 2,        # Integer 2 matching native Miracle DBF specification
                        'FIELD12': str(vou_no),
                        'T41FVNO': str(vou_no),
                        'FIELD16': party_f16_val,
                        'FIELD20': 'N',   # 'N' = Normal active line (Native Miracle requirement so amounts display in Ledger reports)
                        'FIELD21': resolved_f21,  # Dynamic PT/PR/BK mapping
                        'FIELD22': party_f22_val,  # Reconciliation / clearance date
                        'FIELD26': 0.0,
                        'FIELD29': 0.0,
                        'T01F97': '01',
                        'FIELD75': '0',
                        'T01F96': 'N'     # FIXED: 'N' for all Cash/Bank lines
                    }
                    self._append_record(t01, t01_rec_party, {'FIELD09': f"{line_idx_t01:>4}"})
                    line_idx_t01 += 1
                    
                    # 4. T40 Narration Record (Full narration lookup for Miracle UI)
                    t40_rec = {
                        'T40F01': v_id,
                        'T40F09': 'XXXX',
                        'T40F02': narration
                    }
                    self._append_record(t40, t40_rec)
                    

                    injected_count += 1
                    self.audit_report["injected"] += 1
                    
            finally:
                t41.close()
                t01.close()
                t40.close()
            
            self._register_guids_batch(guids_to_register)
            self.repair_unregistered_guids(year_folder)

        # Compact modified tables to reclaim space and prune deleted records
        for tbl in ['rkacct41.dbf', 'rkacct01.dbf', 'rkacct40.dbf']:
            self.compact_table(tbl, year_folder)
        self.ensure_cdx_flags_active(year_folder)
                
        # Trigger reindexing
        self.reindex_tables(year_folder)

        if injected_count > 0:
            # try:
            #     self.sync_closing_balances_to_next_year(year_folder)
            # except Exception as sy_err:
            #     print(f"[carry-forward] Non-critical sync notice: {sy_err}")
            
            y_label = year_folder
            if "YR25" in year_folder.upper(): y_label = "2025–2026 (YR25)"
            elif "YR26" in year_folder.upper(): y_label = "2026–2027 (YR26)"
            self.audit_report["messages"].append(
                f"ℹ️ Vouchers injected into Financial Year: {y_label}. In Miracle Software, please switch active year to {y_label} or set Date Filter (01/04/2025 – 31/03/2026) to view individual voucher rows."
            )

        return injected_count

    def _find_gid_path(self) -> str | None:
        """Locates RKACCGID.DBF in year folder or parent company folder."""
        candidates = [
            os.path.join(self.client_path, 'RKACCGID.DBF'),
            os.path.join(self.client_path, 'rkaccgid.dbf'),
            os.path.join(os.path.dirname(self.client_path), 'RKACCGID.DBF'),
            os.path.join(os.path.dirname(self.client_path), 'rkaccgid.dbf'),
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
        return None

    def _register_guids_batch(self, records: list):
        """Registers multiple records in RKACCGID.DBF in a single open/close cycle for speed."""
        import uuid
        import dbf
        
        if not records:
            return
            
        gid_path = self._find_gid_path()
        if not gid_path:
            print(f"Warning: RKACCGID.DBF not found at {self.client_path}")
            return
                
        with self.safe_cdx_context(gid_path):
            table = dbf.Table(gid_path)
            table.open(mode=dbf.READ_WRITE)
            try:
                for record_type, record_id, is_header in records:
                    guid_str = uuid.uuid4().hex.upper()
                    if is_header:
                        pfx = record_id[:2].upper()
                        if pfx in ('SS', 'PP'):
                            field04_val = 'HE'.ljust(25)
                        elif pfx in ('BR', 'BP', 'CR', 'CP', 'BC', 'CV'):
                            field04_val = 'W'.ljust(25)
                        else:
                            field04_val = 'H'.ljust(25)
                    else:
                        field04_val = ''.ljust(25)
                    
                    table.append(self.clean_record_dict({
                        'FIELD01': record_type,
                        'FIELD02': record_id.ljust(12),
                        'FIELD03': guid_str,
                        'FIELD04': field04_val,
                        'FIELD05': 'E',
                        'GIDF07': '01',
                        'GIDF08': '1'
                    }, table=table))
                print(f"Batch registered {len(records)} GUIDs in RKACCGID.DBF")
            except Exception as e:
                print(f"Error in batch GUID registration: {e}")
            finally:
                table.close()

    def repair_unregistered_guids(self, year_folder: str):
        """Scans RKACCT41.DBF and registers any missing voucher GUIDs in RKACCGID.DBF."""
        import uuid
        import dbf
        
        gid_path = self._find_gid_path()
        if not gid_path:
            return
            
        t41_path = self._get_table_path('RKACCT41.DBF', year_folder)
        if not os.path.exists(t41_path):
            t41_path = self._get_table_path('rkacct41.dbf', year_folder)
            if not os.path.exists(t41_path):
                return

        try:
            with self.safe_cdx_context(gid_path):
                gid_tbl = dbf.Table(gid_path)
                gid_tbl.open(mode=dbf.READ_WRITE)
                try:
                    existing_ids = {str(r.field02).strip() for r in gid_tbl if str(r.field01).strip() == 'YRT41'}
                    
                    t41_tbl = dbf.Table(t41_path)
                    t41_tbl.open(mode=dbf.READ_ONLY)
                    to_add = []
                    try:
                        for r in t41_tbl:
                            v_id = str(r.field01).strip()
                            if v_id and v_id not in existing_ids:
                                pfx = v_id[:2].upper()
                                if pfx in ('SS', 'PP'):
                                    field04_val = 'HE'.ljust(25)
                                elif pfx in ('BR', 'BP', 'CR', 'CP', 'BC', 'CV'):
                                    field04_val = 'W'.ljust(25)
                                else:
                                    field04_val = 'H'.ljust(25)
                                to_add.append((v_id, field04_val))
                                existing_ids.add(v_id)
                    finally:
                        t41_tbl.close()

                    if to_add:
                        for v_id, f04_val in to_add:
                            guid_str = uuid.uuid4().hex.upper()
                            gid_tbl.append(self.clean_record_dict({
                                'FIELD01': 'YRT41',
                                'FIELD02': v_id.ljust(12),
                                'FIELD03': guid_str,
                                'FIELD04': f04_val,
                                'FIELD05': 'E',
                                'GIDF07': '01',
                                'GIDF08': '1'
                            }, table=gid_tbl))
                        print(f"🔧 Auto-repaired {len(to_add)} missing voucher GUIDs in RKACCGID.DBF")
                finally:
                    gid_tbl.close()
        except Exception as e:
            print(f"Repair GUID error: {e}")

    def _register_guid(self, record_type: str, record_id: str, is_header: bool = False):
        """Registers a record in RKACCGID.DBF to prevent Miracle's parser from ignoring it."""
        import uuid
        import dbf
        
        gid_path = self._find_gid_path()
        if not gid_path:
            print(f"Warning: RKACCGID.DBF not found at {self.client_path}")
            return
                
        guid_str = uuid.uuid4().hex.upper()
        if is_header:
            pfx = record_id[:2].upper()
            if pfx in ('SS', 'PP'):
                field04_val = 'HE'.ljust(25)
            elif pfx in ('BR', 'BP', 'CR', 'CP', 'BC', 'CV'):
                field04_val = 'W'.ljust(25)
            else:
                field04_val = 'H'.ljust(25)
        else:
            field04_val = ''.ljust(25)
        
        with self.safe_cdx_context(gid_path):
            table = dbf.Table(gid_path)
            table.open(mode=dbf.READ_WRITE)
            try:
                table.append(self.clean_record_dict({ # type: ignore
                    'FIELD01': record_type,
                    'FIELD02': record_id.ljust(12),
                    'FIELD03': guid_str,
                    'FIELD04': field04_val,
                    'FIELD05': 'E',
                    'GIDF07': '01',
                    'GIDF08': '1'
                }, table=table))
                print(f"Registered GUID {guid_str} for {record_type} ID: {record_id}")
            except Exception as e:
                print(f"Error registering GUID for {record_id}: {e}")
            finally:
                table.close()

    def get_product_master_gst_rate(self, product_name: str, year_folder: str | None = None) -> float | None:
        """
        Looks up a product in RKACCM21.DBF. If found, resolves its linked commodity
        code (M21F27) to determine its configured GST percentage.
        """
        # Highest priority: parse explicit GST rate from the product name (e.g. footwear Gst 0 -> 0.0)
        extracted_pct = self._extract_gst_from_name(product_name)
        if extracted_pct is not None:
            return extracted_pct

        if not year_folder:
            year_folder = self.get_latest_year_folder()
            
        m21_path = self._get_table_path('RKACCM21.DBF', year_folder)
        if not os.path.exists(m21_path): m21_path = self._get_table_path('rkaccm21.dbf', year_folder)
        if not os.path.exists(m21_path):
            return None
            
        search_name = product_name.strip().upper()[:40]
        comm_code = None
        
        import dbf
        with self.safe_cdx_context(m21_path):
            try:
                m21 = dbf.Table(m21_path)
                m21.open(mode=dbf.READ_ONLY)
                for r in m21:
                    if not dbf.is_deleted(r) and str(r['FIELD02']).strip().upper() == search_name:
                        comm_code = str(r['M21F27']).strip().upper()
                        break
                m21.close()
            except Exception as e:
                print(f"Error reading RKACCM21 for GST rate: {e}")
                
        if not comm_code:
            return None
            
        # Standard commodity resolution fallback
        if comm_code in ['CNGT', 'C001']:
            return 0.0
        elif comm_code == 'C006':
            return 3.0
        elif comm_code == 'C002':
            return 5.0
        elif comm_code == 'C003':
            return 12.0
        elif comm_code == 'C004':
            return 18.0
        elif comm_code == 'C005':
            return 28.0
            
        # Try to resolve dynamically from RKACCM18 (Commodity-Tax Group mapping) and RKACCM13 (Tax Master)
        m18_path = self._get_table_path('RKACCM18.DBF', year_folder)
        if not os.path.exists(m18_path): m18_path = self._get_table_path('rkaccm18.dbf', year_folder)
        tax_group = None
        if os.path.exists(m18_path):
            try:
                m18 = dbf.Table(m18_path)
                m18.open(mode=dbf.READ_ONLY)
                for r in m18:
                    if not dbf.is_deleted(r) and str(r['M18F01']).strip().upper() == comm_code:
                        tax_group = str(r['M18F02']).strip().upper()
                        break
                m18.close()
            except Exception as e:
                print(f"Error reading RKACCM18 for commodity rate: {e}")

        if tax_group:
            # Look up tax percentage from RKACCM13.DBF (Tax Master)
            m13_path = self._get_table_path('RKACCM13.DBF', year_folder)
            if not os.path.exists(m13_path): m13_path = self._get_table_path('rkaccm13.dbf', year_folder)
            if os.path.exists(m13_path):
                try:
                    m13 = dbf.Table(m13_path)
                    m13.open(mode=dbf.READ_ONLY)
                    for r in m13:
                        if not dbf.is_deleted(r) and str(r['M13F01']).strip().upper() == tax_group:
                            rate = float(r['M13F06'] or 0.0) # Total IGST Rate column
                            m13.close()
                            return rate
                    m13.close()
                except Exception as e:
                    print(f"Error reading RKACCM13 for tax group rate: {e}")

            # Fallback for standard Miracle Tax Group Codes
            tax_group_map = {
                'G001': 0.0, 'GNGT': 0.0, 'G006': 3.0, 'G002': 5.0,
                'G003': 12.0, 'G004': 18.0, 'G005': 28.0
            }
            if tax_group in tax_group_map:
                return tax_group_map[tax_group]
                
        return None

    def heal_blank_hsn_records(self, year_folder: str | None = None):
        """Self-healing HSN routine: finds any products in rkaccm21 with blank or 'XXXXXXXX' HSN,
        and resolves them from their linked commodity in rkaccm14."""
        import dbf

        if not year_folder:
            year_folder = self.get_latest_year_folder()
            
        m14_path = self._get_table_path('RKACCM14.DBF', year_folder)
        if not os.path.exists(m14_path):
            m14_path = self._get_table_path('rkaccm14.dbf', year_folder)
            
        m21_path = self._get_table_path('RKACCM21.DBF', year_folder)
        if not os.path.exists(m21_path):
            m21_path = self._get_table_path('rkaccm21.dbf', year_folder)
            
        if not os.path.exists(m14_path) or not os.path.exists(m21_path):
            print("Warning: HSN self-healing skipped (RKACCM14 or RKACCM21 not found).")
            return
            
        try:
            # 1. Load commodities to build HSN mapping
            comm_to_hsn = {}
            with self.safe_cdx_context(m14_path):
                m14 = dbf.Table(m14_path)
                m14.open(mode=dbf.READ_ONLY)
                for r in m14:
                    if not dbf.is_deleted(r):
                        comm_code = str(r['M14F01']).strip()
                        hsn = str(r['M14F04']).strip()
                        if hsn and hsn != 'XXXXXXXX':
                            comm_to_hsn[comm_code] = hsn
                m14.close()
                
            # 2. Iterate products and heal if HSN is missing
            # 2. Iterate products and heal if HSN is missing or commodity is C001
            with self.safe_cdx_context(m21_path):
                m21 = dbf.Table(m21_path)
                m21.open(mode=dbf.READ_WRITE)
                updated_count = 0
                healed_comm_count = 0
                for r in m21:
                    if not dbf.is_deleted(r):
                        prod_name = str(r['FIELD02']).strip()
                        comm_code = str(r['M21F27']).strip()
                        hsn_curr = str(r['M21F31']).strip()
                    # Fix blank/placeholder HSN
                        if hsn_curr in ['', 'XXXXXXXX'] and comm_code in comm_to_hsn:
                            hsn_new = comm_to_hsn[comm_code]
                            dbf.write(r, M21F31=hsn_new.ljust(8))
                            print(f"Self-healed product HSN '{prod_name}': Set M21F31 to '{hsn_new}' (from commodity '{comm_code}')")
                            updated_count += 1
                            
                        # Fix C001 mapped to CNGT for Non-GST
                        if comm_code == 'C001':
                            dbf.write(r, M21F27='CNGT')
                            print(f"Self-healed product commodity for '{prod_name}': Set M21F27 to 'CNGT' (from 'C001')")
                            healed_comm_count += 1
                            
                m21.close()
                if updated_count > 0:
                    print(f"HSN Self-Healing complete. Updated {updated_count} products.")
                if healed_comm_count > 0:
                    print(f"Product Commodity Self-Healing complete. Updated {healed_comm_count} products.")
        except Exception as e:
            print(f"Error running HSN and Commodity self-healing: {e}")

    def repair_bank_closing_flags(self, year_folder: str | None = None):
        """Alias helper for repair_bank_entry_flags."""
        res = self.repair_bank_entry_flags(year_folder=year_folder)
        return res.get("repaired", 0) if isinstance(res, dict) else res

    def repair_missing_narrations(self, year_folder: str | None = None):
        """Alias helper for repair_all_voucher_narrations."""
        return self.repair_all_voucher_narrations(year_folder=year_folder)

    def repair_bank_entry_flags(self, year_folder: str | None = None) -> dict:
        """
        UPGRADED REPAIR & HEALING TOOL (Bug #17, Bug #24, Bug #26).
        Converts old 'CV' vouchers to native 'BC' (Contra) type, aligns header and line flags,
        and initializes numeric columns to 0.0 to prevent database corruption.
        """
        import dbf as dbf_lib
        import os
        
        BANK_CASH_VOUCHER_TYPES = {'BR', 'BP', 'CV', 'BC', 'CR', 'CP', 'CB'}
        
        result = {
            'repaired_headers': 0,
            'repaired_lines': 0,
            'skipped': 0,
            'errors': [],
            'folders': []
        }
        
        if year_folder:
            folders_to_repair = [year_folder]
        else:
            all_folders = self.get_available_year_folders()
            folders_to_repair = [f['name'] for f in all_folders]
            
        for yr in folders_to_repair:
            t41_path = self._get_table_path('rkacct41.dbf', yr)
            if not os.path.exists(t41_path):
                t41_path = self._get_table_path('RKACCT41.DBF', yr)
            t01_path = self._get_table_path('rkacct01.dbf', yr)
            if not os.path.exists(t01_path):
                t01_path = self._get_table_path('RKACCT01.DBF', yr)
                
            if not os.path.exists(t41_path) or not os.path.exists(t01_path):
                result['errors'].append(f"{yr}: RKACCT41.DBF or RKACCT01.DBF not found")
                continue
                
            yr_repaired_h = 0
            yr_repaired_l = 0
            yr_skipped = 0
            
            try:
                # Load T40 memos if table exists
                t40_path = self._get_table_path('rkacct40.dbf', yr)
                if not os.path.exists(t40_path):
                    t40_path = self._get_table_path('RKACCT40.DBF', yr)
                
                memos = {}
                if os.path.exists(t40_path):
                    try:
                        with self.safe_cdx_context(t40_path):
                            t40_temp = dbf_lib.Table(t40_path, codepage='cp1252')
                            t40_temp.open(mode=dbf_lib.READ_ONLY)
                            try:
                                for row in t40_temp:
                                    if dbf_lib.is_deleted(row):
                                        continue
                                    vid = str(row['T40F01']).strip()
                                    memo_text = str(row['T40F02']).strip()
                                    if vid and memo_text:
                                        memos[vid] = memo_text
                            finally:
                                t40_temp.close()
                    except Exception as e:
                        print(f"Warning: Failed to load T40 memos for {yr}: {e}")

                # First open T01 read-only to load line direction mapping for T41 repair
                line_directions = {}
                with self.safe_cdx_context(t01_path):
                    t01_temp = dbf_lib.Table(t01_path, codepage='cp1252')
                    t01_temp.open(mode=dbf_lib.READ_ONLY)
                    try:
                        for row in t01_temp:
                            if dbf_lib.is_deleted(row):
                                continue
                            vid = str(row['FIELD01']).strip()
                            f21 = str(row['FIELD21']).strip()
                            drcr = str(row['FIELD06']).strip()
                            if vid not in line_directions:
                                line_directions[vid] = []
                            line_directions[vid].append((f21, drcr))
                    finally:
                        t01_temp.close()

                # 1. Repair T41 Headers
                with self.safe_cdx_context(t41_path):
                    t41 = dbf_lib.Table(t41_path, codepage='cp1252')
                    t41.open(mode=dbf_lib.READ_WRITE)
                    try:
                        for record in t41:
                            if dbf_lib.is_deleted(record):
                                continue
                            
                            try:
                                v_type = str(record['FIELD98']).strip().upper()
                            except:
                                continue
                                
                            is_cv = (v_type == 'CV')
                            is_cash_contra = (v_type in ('BR', 'BP') and str(record['FIELD04']).strip() == 'ACASHACT')
                            vid = str(record['FIELD01']).strip()
                            
                            updates = {}
                            if is_cv or is_cash_contra:
                                # Determine direction R/P from matching lines
                                dr_cr_direction = 'R'
                                if vid in line_directions:
                                    for f21, drcr in line_directions[vid]:
                                        if f21 == 'BK':
                                            dr_cr_direction = 'R' if drcr == 'D' else 'P'
                                            break
                                        elif f21 == 'CS':
                                            dr_cr_direction = 'R' if drcr == 'D' else 'P'
                                            break
                                            
                                updates['FIELD98'] = 'BC'
                                updates['FIELD99'] = 'BC'
                                updates['T41F83'] = '9'
                                updates['FIELD16'] = dr_cr_direction

                            # Repair blank FIELD82 narration from T40 memo table
                            try:
                                f82 = str(record['FIELD82']).strip()
                                if not f82 and vid in memos:
                                    target_f82 = memos[vid][:50].strip()
                                    if target_f82:
                                        updates['FIELD82'] = target_f82
                            except Exception:
                                pass

                            # Repair FIELD74 and FIELD21 flags for BR, BP, BC, CB
                            try:
                                target_v_type = updates.get('FIELD98') or v_type
                                if target_v_type in ('BR', 'BP', 'BC', 'CB'):
                                    f74 = str(record['FIELD74']).strip().upper()
                                    f21 = str(record['FIELD21']).strip().upper()
                                    if f74 != 'CB':
                                        updates['FIELD74'] = 'CB'
                                    if f21 not in ('O', ' '):
                                        updates['FIELD21'] = 'O'
                            except Exception:
                                pass
                                
                            if updates:
                                try:
                                    with record:
                                        for uk, uv in updates.items():
                                            record[uk] = uv
                                    yr_repaired_h += 1
                                except Exception as e:
                                    result['errors'].append(f"{yr} header {vid}: Failed to update header fields — {e}")
                    finally:
                        t41.close()

                # 2. Repair T01 Lines
                with self.safe_cdx_context(t01_path):
                    t01 = dbf_lib.Table(t01_path, codepage='cp1252')
                    t01.open(mode=dbf_lib.READ_WRITE)
                    try:
                        for record in t01:
                            if dbf_lib.is_deleted(record):
                                yr_skipped += 1
                                continue
                                
                            try:
                                v_type = str(record['FIELD98']).strip().upper()
                                f21 = str(record['FIELD21']).strip().upper()
                            except:
                                yr_skipped += 1
                                continue
                                
                            if v_type not in BANK_CASH_VOUCHER_TYPES:
                                yr_skipped += 1
                                continue
                                
                            # Convert CV or Cash Account BR/BP to BC if found
                            is_cv_line = (v_type == 'CV')
                            p_code = str(record['FIELD04']).strip()
                            m_code = str(record['FIELD03']).strip()
                            is_cash_contra_line = (v_type in ('BR', 'BP') and (p_code == 'ACASHACT' or m_code == 'ACASHACT'))
                            
                            try:
                                f20 = str(record['FIELD20']).strip()
                                f96 = str(record['T01F96']).strip()
                                f16 = record['FIELD16']
                                f22 = record['FIELD22']
                                f02 = record['FIELD02']
                                f08 = record['FIELD08']
                                f26 = record['FIELD26']
                                f29 = record['FIELD29']
                            except:
                                yr_skipped += 1
                                continue
                                
                            # Check what flags need fixing
                            target_type = 'BC' if (is_cv_line or is_cash_contra_line) else v_type
                            is_contra = (target_type == 'BC')
                            needs_type_fix = (is_cv_line or is_cash_contra_line)
                            needs_flag_fix = False
                            
                            # Standardize Contra flags vs Regular flags (Native Miracle requires T01F96='N' and FIELD20='C' for all bank/cash lines)
                            target_f96 = 'N'
                            target_f20 = 'C'
                            
                            # Standardize FIELD16 (Date field) and FIELD22 (Reconciliation Date)
                            if target_type in ('BR', 'BP'):
                                target_f16 = f02
                                target_f22 = None if is_contra else f02
                            elif target_type in ('CR', 'CP'):
                                target_f16 = None
                                target_f22 = None
                            else:  # BC
                                target_f16 = f02 if f21 == 'BK' else None
                                target_f22 = None
                            
                            # Force numeric columns to 0.0 if None
                            try:
                                target_f08 = float(f08) if f08 is not None else 0.0
                            except:
                                target_f08 = 0.0
                            try:
                                target_f26 = float(f26) if f26 is not None else 0.0
                            except:
                                target_f26 = 0.0
                            try:
                                target_f29 = float(f29) if f29 is not None else 0.0
                            except:
                                target_f29 = 0.0
                                
                            if (f20 != target_f20 or f96 != target_f96 or f16 != target_f16 or 
                                f22 != target_f22 or f08 != target_f08 or f26 != target_f26 or 
                                f29 != target_f29 or needs_type_fix):
                                needs_flag_fix = True
                                
                            if needs_flag_fix:
                                try:
                                    with record:
                                        if needs_type_fix:
                                            record['FIELD98'] = 'BC'
                                            record['FIELD99'] = 'BC'
                                        record['FIELD20'] = target_f20
                                        record['T01F96'] = target_f96
                                        record['FIELD16'] = target_f16
                                        record['FIELD22'] = target_f22
                                        record['FIELD08'] = target_f08
                                        record['FIELD26'] = target_f26
                                        record['FIELD29'] = target_f29
                                    yr_repaired_l += 1
                                except Exception as e:
                                    result['errors'].append(f"{yr} line: Failed to update flags — {e}")
                            else:
                                yr_skipped += 1
                    finally:
                        t01.close()
                        
                result['folders'].append({
                    'year': yr,
                    'repaired_headers': yr_repaired_h,
                    'repaired_lines': yr_repaired_l,
                    'skipped': yr_skipped
                })
                result['repaired_headers'] += yr_repaired_h
                result['repaired_lines'] += yr_repaired_l
                result['skipped'] += yr_skipped
                print(f"[repair] {yr}: repaired_headers={yr_repaired_h}, repaired_lines={yr_repaired_l}, skipped={yr_skipped}")
                
                # Trigger reindex after repair
                try:
                    self.reindex_tables(yr)
                except Exception as e:
                    result['errors'].append(f"{yr}: Reindex warning — {e}")
                    
            except Exception as e:
                result['errors'].append(f"{yr}: Critical error — {e}")
                print(f"[repair] ❌ {yr} failed: {e}")
                
        print(f"[repair] Complete. Total repaired_headers={result['repaired_headers']}, repaired_lines={result['repaired_lines']}, errors={len(result['errors'])}")
        return result

    def repair_all_voucher_narrations(self, year_folder: str | None = None) -> dict:
        """
        Self-healing engine to repair missing narrations across all vouchers.
        1. Ensures FIELD82 in RKACCT41.DBF contains up to 50 characters of narration.
        2. Ensures EVERY voucher ID in RKACCT41.DBF has a corresponding narration record in RKACCT40.DBF.
        """
        import dbf as dbf_lib
        import os
        
        result = {"status": "success", "repaired_headers": 0, "repaired_memos": 0, "repaired_flags": 0, "errors": []}
        
        # First repair line flags (FIELD20='C', T01F96='N') for Miracle ledger linkage
        try:
            flag_res = self.repair_bank_entry_flags(year_folder=year_folder)
            result["repaired_flags"] = flag_res.get("repaired_lines", 0)
        except Exception as flag_err:
            print(f"Warning: Flag repair in repair_all_voucher_narrations failed: {flag_err}")
        
        folders_to_repair = []
        if year_folder:
            folders_to_repair = [year_folder]
        else:
            all_folders = self.get_available_year_folders()
            folders_to_repair = [f['name'] for f in all_folders]

        for yr in folders_to_repair:
            # Ensure CDX flags in byte 28 are 100% active (0x03 for RKACCT40 with memo, 0x01 for RKACCT41/01)
            self.ensure_cdx_flags_active(yr)
            t41_path = self._get_table_path('rkacct41.dbf', yr)
            if not os.path.exists(t41_path): t41_path = self._get_table_path('RKACCT41.DBF', yr)
            t40_path = self._get_table_path('rkacct40.dbf', yr)
            if not os.path.exists(t40_path): t40_path = self._get_table_path('RKACCT40.DBF', yr)
            m01_path = self._get_table_path('rkaccm01.dbf', yr)
            if not os.path.exists(m01_path): m01_path = self._get_table_path('RKACCM01.DBF', yr)

            if not os.path.exists(t41_path) or not os.path.exists(t40_path):
                continue

            # Load party names for fallback narration construction
            code_to_name = {}
            if os.path.exists(m01_path):
                try:
                    with self.safe_cdx_context(m01_path):
                        t_m01 = dbf_lib.Table(m01_path, codepage='cp1252')
                        t_m01.open(mode=dbf_lib.READ_ONLY)
                        for r in t_m01:
                            if not dbf_lib.is_deleted(r):
                                code_to_name[str(r['FIELD01']).strip()] = str(r['FIELD02']).strip()
                        t_m01.close()
                except Exception as e:
                    print(f"Warning: Failed to load party names for {yr}: {e}")

            # Load existing T40 narrations
            memos = {}
            try:
                with self.safe_cdx_context(t40_path):
                    t40_temp = dbf_lib.Table(t40_path, codepage='cp1252')
                    t40_temp.open(mode=dbf_lib.READ_ONLY)
                    try:
                        for row in t40_temp:
                            if dbf_lib.is_deleted(row):
                                continue
                            vid = str(row['T40F01']).strip()
                            memo_text = str(row['T40F02']).strip()
                            if vid and memo_text:
                                memos[vid] = memo_text
                    finally:
                        t40_temp.close()
            except Exception as e:
                print(f"Warning: Failed to load T40 memos for {yr}: {e}")

            # 1. Open T41 to repair FIELD82 and find vouchers needing T40 records
            new_memos_to_add = {}
            with self.safe_cdx_context(t41_path):
                t41 = dbf_lib.Table(t41_path, codepage='cp1252')
                t41.open(mode=dbf_lib.READ_WRITE)
                try:
                    for record in t41:
                        if dbf_lib.is_deleted(record):
                            continue
                        
                        vid = str(record['FIELD01']).strip()
                        if not vid:
                            continue
                        
                        v_type = str(record['FIELD98']).strip().upper()
                        f82 = str(record['FIELD82']).strip()
                        existing_memo = memos.get(vid, '').strip()

                        p_code = str(record['FIELD04']).strip()
                        p_name = code_to_name.get(p_code, p_code)
                        f12_val = str(record['FIELD12']).strip() if 'FIELD12' in t41.field_names else ''
                        f10_val = str(record['FIELD10']).strip() if 'FIELD10' in t41.field_names else ''
                        fvno_val = str(record['T41FVNO']).strip() if 'T41FVNO' in t41.field_names else ''
                        v_no = f12_val or f10_val or fvno_val

                        # Determine best available narration
                        if existing_memo:
                            best_narr = existing_memo
                        elif f82:
                            best_narr = f82
                        else:
                            if v_type in ('SS', 'SL', 'SR'):
                                best_narr = f"Sales Invoice {v_no} - {p_name}".strip()
                            elif v_type in ('PP', 'PB', 'PU'):
                                best_narr = f"Purchase Bill {v_no} - {p_name}".strip()
                            elif v_type in ('BR', 'CR'):
                                best_narr = f"Receipt from {p_name}".strip()
                            elif v_type in ('BP', 'CP'):
                                best_narr = f"Payment to {p_name}".strip()
                            elif v_type in ('BC', 'CV'):
                                best_narr = f"Contra Transfer - {p_name}".strip()
                            else:
                                best_narr = f"Voucher {v_no} - {p_name}".strip()

                        # Repair FIELD82 in RKACCT41 if blank
                        if not f82 and best_narr:
                            try:
                                with record:
                                    record['FIELD82'] = self.fit_dbf_str(best_narr, 50)
                                result['repaired_headers'] += 1
                            except Exception as e:
                                pass

                        # Queue for T40 insert if missing
                        if vid not in memos and best_narr:
                            new_memos_to_add[vid] = best_narr
                finally:
                    t41.close()

            # 2. Append missing narration records to RKACCT40.DBF
            if new_memos_to_add:
                with self.safe_cdx_context(t40_path):
                    t40 = dbf_lib.Table(t40_path, codepage='cp1252')
                    t40.open(mode=dbf_lib.READ_WRITE)
                    try:
                        for vid, narr in new_memos_to_add.items():
                            t40_rec = {
                                'T40F01': vid,
                                'T40F09': 'XXXX',
                                'T40F02': narr
                            }
                            t40.append(self.clean_record_dict(t40_rec, table=t40))
                            result['repaired_memos'] += 1
                    finally:
                        t40.close()

            print(f"[repair-narrations] {yr}: repaired_headers={result['repaired_headers']}, repaired_memos={result['repaired_memos']}")
                        
        return result

    def compact_table(self, table_name: str, year_folder: str | None = None):
        """Compacts a DBF table and its memos by removing deleted records and shrinking the FPT file."""
        import dbf
        import shutil
        from pathlib import Path
        
        dbf_path = Path(self._get_table_path(table_name, year_folder))
        if not dbf_path.exists():
            return
            
        temp_dir = dbf_path.parent / "TEMP"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_file = temp_dir / f"temp_{dbf_path.name}"
        
        table = dbf.Table(str(dbf_path))
        try:
            self._open_table_with_retry(table, mode=dbf.READ_WRITE)
        except Exception as e:
            print(f"⚠️ Warning: Could not open {table_name} for compaction: {e}")
            return
            
        has_memos = len(table._meta.memofields) > 0
        has_deleted = any(dbf.is_deleted(rec) for rec in table)
        
        if not has_memos and not has_deleted:
            table.close()
            return
            
        print(f"[compact] Compacting {table_name} (has_memos={has_memos}, has_deleted={has_deleted})...")
        try:
            new_table = table.new(str(temp_file))
            self._open_table_with_retry(new_table, mode=dbf.READ_WRITE)
            
            copied = 0
            for record in table:
                if not dbf.is_deleted(record):
                    new_table.append(dbf.scatter(record))
                    copied += 1
                    
            new_table.close()
            table.close()
            
            # Replace original files with robust case-variant unlinking
            for base_ext in [".dbf", ".fpt", ".cdx"]:
                temp_ext_path = temp_file.with_suffix(base_ext)
                if not temp_ext_path.exists():
                    temp_ext_path = temp_file.with_suffix(base_ext.upper())
                    
                if temp_ext_path.exists():
                    for ext_var in [base_ext.lower(), base_ext.upper()]:
                        target_var = dbf_path.with_suffix(ext_var)
                        if target_var.exists():
                            try: target_var.unlink()
                            except Exception: pass
                    dest_path = dbf_path.with_suffix(temp_ext_path.suffix)
                    shutil.move(str(temp_ext_path), str(dest_path))
            print(f"[compact] Compacted {table_name} successfully, retained {copied} active records.")
                    
        except Exception as e:
            print(f"⚠️ Warning: Compaction failed for {table_name}: {e}")
            try: table.close()
            except: pass
            try: new_table.close()
            except: pass
            for ext in [".dbf", ".DBF", ".fpt", ".FPT", ".cdx", ".CDX"]:
                temp_ext_path = temp_file.with_suffix(ext)
                if temp_ext_path.exists():
                    try: temp_ext_path.unlink()
                    except: pass

    def reindex_tables(self, year_folder: str | None = None) -> bool:

        """
        Generates a VFP reindex.prg script and attempts execution via pyodbc OLEDB.
        """
        import os

        if not year_folder:
            year_folder = self.get_latest_year_folder()
            
        # Run HSN self-healing before reindexing
        self.heal_blank_hsn_records(year_folder)
            
        year_path = os.path.join(self.client_path, year_folder)
        prg_path = os.path.join(year_path, "reindex.prg")
        
        prg_content = """* reindex.prg
SET SAFETY OFF
SET EXCLUSIVE ON

REINDEX_TABLE("RKACCT41")
REINDEX_TABLE("RKACCT01")
REINDEX_TABLE("RKACCT02")
REINDEX_TABLE("RKACCT52")
REINDEX_TABLE("RKACCT40")
REINDEX_TABLE("RKACCM01")
REINDEX_TABLE("RKACCM02")
REINDEX_TABLE("RKACCM21")
REINDEX_TABLE("RKACCM14")
REINDEX_TABLE("RKACCM18")

IF FILE("../RKACCGID.DBF")
    TRY
        USE ../RKACCGID EXCLUSIVE
        REINDEX
        USE
    CATCH
    ENDTRY
ENDIF

CLOSE DATABASES
QUIT

PROCEDURE REINDEX_TABLE(tcTable)
    IF FILE(tcTable + ".DBF")
        TRY
            USE (tcTable) IN 0 EXCLUSIVE
            SELECT (tcTable)
            REINDEX
            USE
        CATCH TO oErr
            ? "Error reindexing " + tcTable
        ENDTRY
    ENDIF
ENDPROC
"""
        try:
            with open(prg_path, "w") as f:
                f.write(prg_content)
            print(f"Generated reindex.prg VFP script at {prg_path}")
        except Exception as e:
            print(f"Failed to generate reindex.prg: {e}")
            
        # Optional pyodbc execution
        try:
            import pyodbc # type: ignore
            cnxn = pyodbc.connect(f"DSN=Visual FoxPro Tables;SourceDB={year_path};SourceType=DBF;Exclusive=Yes;")
            cursor = cnxn.cursor()
            for tbl in ["RKACCT41", "RKACCT01", "RKACCT02", "RKACCT52", "RKACCT40", "RKACCM01", "RKACCM02", "RKACCM21"]:
                try:
                    cursor.execute(f"USE {tbl} EXCLUSIVE")
                    cursor.execute("REINDEX")
                except Exception:
                    pass
            cnxn.close()
            print("Successfully reindexed via VFP pyodbc connection.")
            return True
        except Exception as e:
            print(f"Automated reindexing via pyodbc skipped/failed: {e}")
            return False

    def find_matching_bill(self, party_name: str, amount: float, year_folder: str | None = None) -> str:
        """
        Phase 6: Scans RKACCT41.DBF for a Sales or Purchase bill exactly matching the amount
        and the party name, returning the invoice number.
        """
        import dbf
        if not year_folder:
            year_folder = self.get_latest_year_folder()
        if not year_folder:
            return ""

        t41_path = self._get_table_path('RKACCT41.DBF', year_folder)
        if not os.path.exists(t41_path): t41_path = self._get_table_path('rkacct41.dbf', year_folder)
        if not os.path.exists(t41_path):
            return ""

        ledgers = self.read_ledgers(year_folder)
        target_code = None
        clean_target = party_name.upper().strip()
        for led in ledgers:
            if led['name'].upper() == clean_target or led['print_name'].upper() == clean_target:
                target_code = led['code']
                break
                
        if not target_code:
            return ""

        matched_bill_no = ""
        try:
            with self.safe_cdx_context(t41_path):
                table = dbf.Table(t41_path)
                table.open(mode=dbf.READ_ONLY)
                for record in table:
                    if dbf.is_deleted(record): continue
                    
                    v_type = str(record['FIELD98']).strip()
                    if v_type not in ['SS', 'PP', 'SL', 'SR', 'SA', 'SB', 'SC', 'SD', 'PB', 'PU', 'PI', 'PO', 'PA']:
                        continue
                        
                    r_party = str(record['FIELD04']).strip()
                    if r_party != target_code:
                        continue
                        
                    r_amt = float(record['FIELD06']) # type: ignore
                    if abs(r_amt - amount) < 0.1: # float tolerance
                        if v_type.startswith('S'):
                            matched_bill_no = str(record['FIELD12']).strip()
                        else:
                            matched_bill_no = str(record['FIELD10']).strip()
                        break
                table.close()
        except Exception as e:
            print(f"Error in find_matching_bill: {e}")
            
        return matched_bill_no

    def inject_opening_balances(self, entries: list, year_folder: str | None = None) -> dict:
        """
        Injects opening balances for general/account ledgers into RKACAMB1.DBF.
        
        entries = [{
            'ledger_code': 'ACASHACT',
            'balance': 150000.0,
            'dr_cr': 'D' or 'C'
        }]
        
        For Assets/Debtors (D): value is positive.
        For Liabilities/Creditors (C): value is negative.
        Writes to MB1F90 (Original OB) and MB1F99 (Net OB).
        """
        if not year_folder:
            year_folder = self.get_latest_year_folder()
        if not year_folder:
            return {"status": "error", "message": "No active client year found"}

        amb1_path = self._get_table_path('RKACAMB1.DBF', year_folder)
        if not os.path.exists(amb1_path):
            amb1_path = self._get_table_path('rkacamb1.dbf', year_folder)
        if not os.path.exists(amb1_path):
            return {"status": "error", "message": f"RKACAMB1.DBF not found in {year_folder}"}
            
        import dbf
        import datetime

        # In Miracle, the date for the opening balance of the current year
        # is the last day of the previous financial year.
        # So if YR27 is 2026-2027, the date is 2026-03-31.
        # Let's derive it by taking the year of the folder (e.g. YR27 means 2000+27-1? No, YR27 started 2026. 
        # But a safer way is to find an existing date in RKACAMB1 for this year, or fallback to parsing year_folder.
        # Actually, let's just find the max date in RKACAMB1.DBF and use it, or fallback.
        
        ob_date = None
        try:
            with self.safe_cdx_context(amb1_path):
                table = dbf.Table(amb1_path)
                table.open(mode=dbf.READ_ONLY)
                dates = set(rec.MB1F02 for rec in table if rec.MB1F02)
                table.close()
                if dates:
                    ob_date = max(dates) # type: ignore
        except Exception as e:
            print(f"Error determining ob_date from AMB1: {e}")
            
        if not ob_date:
            try:
                yr_val = int(year_folder.replace("YR", ""))
                # YR27 -> 2026 start. So 2026-03-31
                ob_date = datetime.date(2000 + yr_val - 1, 3, 31)
            except:
                ob_date = datetime.date.today().replace(month=3, day=31)

        print(f"Using opening balance date: {ob_date}")

        processed = 0
        updated = 0
        inserted = 0

        with self.safe_cdx_context(amb1_path):
            table = dbf.Table(amb1_path)
            table.open(mode=dbf.READ_WRITE)
            try:
                for entry in entries:
                    l_code = entry.get('ledger_code')
                    if not l_code: continue
                    
                    l_code = l_code.strip()
                    raw_bal = float(entry.get('balance', 0.0))
                    dr_cr = entry.get('dr_cr', 'D').upper()
                    
                    # Positive for Debit (Asset), Negative for Credit (Liability)
                    final_bal = raw_bal if dr_cr == 'D' else -raw_bal

                    # Check if record exists for this ledger code AND date
                    existing_record = None
                    for rec in table:
                        if dbf.is_deleted(rec): continue
                        if str(rec['MB1F01']).strip() == l_code and rec['MB1F02'] == ob_date:
                            existing_record = rec
                            break
                            
                    if existing_record:
                        # Update existing
                        dbf.write(existing_record, MB1F90=final_bal, MB1F99=final_bal, MB1F97=0.0, MB1F98=0.0)
                        updated += 1
                    else:
                        # Insert new
                        new_rec = {
                            'MB1F01': l_code,
                            'MB1F02': ob_date,
                            'MB1F90': final_bal,
                            'MB1F99': final_bal,
                            'MB1F97': 0.0,
                            'MB1F98': 0.0
                        }
                        table.append(self.clean_record_dict(new_rec, table=table)) # type: ignore
                        inserted += 1
                    
                    processed += 1
                    
            finally:
                table.close()

        print(f"Opening balances injected: {processed} (Updated: {updated}, Inserted: {inserted})")
        return {
            "status": "success", 
            "processed": processed,
            "updated": updated,
            "inserted": inserted
        }


    def _inject_cash_entries(self, vouchers: list, target_cash_code: str = "ACASHACT", year_folder: str = "") -> int:
        if isinstance(target_cash_code, str) and (target_cash_code.upper().startswith("YR") or not year_folder):
            year_folder = target_cash_code
            target_cash_code = "ACASHACT"
        import os
        import dbf
        import random
        import string
        from datetime import datetime, date

        injected_count = 0
        t41_path = self._get_table_path('rkacct41.dbf', year_folder)
        t01_path = self._get_table_path('rkacct01.dbf', year_folder)
        t40_path = self._get_table_path('rkacct40.dbf', year_folder)
        m01_path = self._get_table_path('rkaccm01.dbf', year_folder)
        
        # Auto-detect T41F83 print series option from backdata
        detected_cfg = self.detect_format_settings(year_folder, ['CR', 'CP', 'BC'])
        resolved_f83 = detected_cfg["f83"]

        # Build CROSS-YEAR ledger lookup map.
        print(f"[cash push] Building cross-year ledger lookup for duplicate prevention...")
        all_ledgers = self.read_ledgers_all_years(active_year_folder=year_folder)
        name_to_code = {led['name'].upper(): led['code'] for led in all_ledgers}
        code_to_classification = {led['code']: led.get('classification', 'Other') for led in all_ledgers}
        ledger_sources = {led['code']: led.get('year_folder') for led in all_ledgers}
        ledgers = all_ledgers

        cash_ledger_code = target_cash_code
        if not cash_ledger_code:
            CASH_ALIASES = ('CASH', 'CASH ACCOUNT', 'CASH A/C', 'CASH AC', 'PETTY CASH', 'CASH-IN-HAND', 'CASH HAND')
            for led in all_ledgers:
                if led.get('classification') == 'Cash' or led.get('group_code') == 'G0000005' or led['name'].strip().upper() in CASH_ALIASES:
                    cash_ledger_code = led['code']
                    print(f"✅ Auto-resolved target_cash_code: '{led['name']}' ({cash_ledger_code})")
                    break
            if not cash_ledger_code:
                cash_ledger_code = self.create_party_ledger("Cash Account", 'Cash Entries', year_folder=year_folder)
        
        # Suspense logic
        suspense_name = "Suspense Account"
        suspense_code = ""
        for led in ledgers:
            if "SUSPENSE" in led['name'].upper():
                suspense_code = led['code']
                suspense_name = led['name']
                break
        if not suspense_code:
            suspense_code = self.create_party_ledger(suspense_name, 'Bank Statements', year_folder=year_folder)
            name_to_code[suspense_name.upper()] = suspense_code

        def gen_id(pfx):
            num = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
            return pfx[:2] + num

        # Let's find last voucher numbers for BR, BP, CV and build duplicate index
        last_cr = 0
        last_cp = 0
        last_cv = 0
        existing_cash_entries = {}
        if os.path.exists(t41_path):
            with self.safe_cdx_context(t41_path):
                t41_lookup = dbf.Table(t41_path)
                t41_lookup.open(mode=dbf.READ_ONLY)
                for r in t41_lookup:
                    if dbf.is_deleted(r):
                        continue
                    v_type = str(r['FIELD98']).strip()
                    if v_type not in ['CR', 'CP', 'CV', 'BC']:
                        continue
                        
                    try:
                        v_num = int(str(r['T41FVNO']).strip())
                    except:
                        v_num = 0
                        
                    if v_type == 'CR':
                        last_cr = max(last_cr, v_num)
                    elif v_type == 'CP':
                        last_cp = max(last_cp, v_num)
                    elif v_type in ('CV', 'BC'):
                        last_cv = max(last_cv, v_num)
                        
                    # Build duplicate key: (Date, Amount, PartyCode, BankCode, Type)
                    try:
                        v_dt = str(r['FIELD02']).strip()
                        p_code = str(r['FIELD04']).strip()
                        b_code = str(r['FIELD05']).strip()
                        amt = float(str(r['FIELD06']).strip() or 0)
                        ref_num = str(r.get('FIELD10') or '').strip().lower() # type: ignore
                        narr = str(r.get('FIELD82') or '').strip().lower() # type: ignore
                        
                        key = (v_dt, amt, p_code, b_code, v_type, ref_num, narr)
                        existing_cash_entries[key] = existing_cash_entries.get(key, 0) + 1
                    except Exception as e:
                        pass
                        
                t41_lookup.close()


        year_num = int(year_folder[-2:]) if year_folder and year_folder[-2:].isdigit() else 27

        with self.backup_transaction_context([t41_path, t01_path, t40_path]), \
             self.safe_cdx_context(t41_path), self.safe_cdx_context(t01_path), self.safe_cdx_context(t40_path):
            t41 = dbf.Table(t41_path)
            t01 = dbf.Table(t01_path)
            t40 = dbf.Table(t40_path)
            self._open_table_with_retry(t41, mode=dbf.READ_WRITE)
            self._open_table_with_retry(t01, mode=dbf.READ_WRITE)
            self._open_table_with_retry(t40, mode=dbf.READ_WRITE)
            
            guids_to_register = []
            intra_batch_seen = set()
            try:
                for idx, v in enumerate(vouchers):
                    line_idx_t01 = 1
                    tx_type = (v.get('transaction_type') or 'Receipt').strip().capitalize()
                    if tx_type.lower() not in ('receipt', 'payment'):
                        tx_type = 'Receipt'
                        
                    # Resolve Party
                    party_name = (v.get('party_name') or v.get('party') or '').strip()
                    amount = self._parse_float(v.get('amount', 0))
                    if not party_name or party_name.startswith('UNKNOWN') or "SUSPENSE" in party_name.upper():
                        party_code = suspense_code
                        if not party_name or party_name.startswith('UNKNOWN'):
                            self.audit_report["missing_parties"] += 1
                            self.audit_report["messages"].append(f"Mapped unknown party to Suspense Account (Amount: ₹{amount})")
                    else:
                        party_code = name_to_code.get(party_name.upper())
                        if not party_code:
                            import difflib
                            matches = difflib.get_close_matches(party_name.upper(), list(name_to_code.keys()), n=1, cutoff=0.85)
                            if matches:
                                party_code = name_to_code[matches[0]]
                                print(f"✅ Fuzzy matched Bank party: {party_name} -> {matches[0]} ({party_code})")
                            else:
                                party_code = self.create_party_ledger(party_name, 'Cash Entries', year_folder=year_folder, transaction_type=tx_type, group_hint=v.get('group_hint', ''))
                                name_to_code[party_name.upper()] = party_code
                                
                        # CRITICAL CROSS-YEAR SYNC FIX (Bug #28):
                        # If the resolved party code exists in another year but is missing in the current year,
                        # sync it from the source year to the current year immediately to prevent blank names in Miracle UI.
                        if party_code:
                            src_year = ledger_sources.get(party_code)
                            if src_year and src_year != year_folder:
                                current_m01 = self._get_table_path('rkaccm01.dbf', year_folder)
                                if not os.path.exists(current_m01): current_m01 = self._get_table_path('RKACCM01.DBF', year_folder)
                                
                                exists_in_current = False
                                if os.path.exists(current_m01):
                                    try:
                                        with self.safe_cdx_context(current_m01):
                                            t = dbf.Table(current_m01)
                                            t.open(mode=dbf.READ_ONLY)
                                            exists_in_current = any(str(r['FIELD01']).strip() == party_code for r in t if not dbf.is_deleted(r))
                                            t.close()
                                    except Exception as e:
                                        print(f"Error checking current year {year_folder} for {party_name}: {e}")
                                
                                if not exists_in_current:
                                    print(f"Syncing existing ledger {party_name} ({party_code}) from {src_year} to current year {year_folder}...")
                                    self._sync_party_to_other_years(party_name, party_code, src_year, target_year_folder=year_folder)

                        # USER GROUP OVERRIDE SYNC:
                        # If the user changed the group in the UI grid, ensure the group code in RKACCM01.DBF
                        # is updated and synced across all financial year directories!
                        user_gh = str(v.get('group_hint') or '').strip()
                        if party_code and user_gh and party_code != suspense_code:
                            target_grp = self.resolve_group_code_from_hint(user_gh)
                            if target_grp:
                                try:
                                    self.update_party_ledger(party_name, party_name, group_code=target_grp, year_folder=year_folder)
                                except Exception as grp_err:
                                    print(f"⚠️ Warning: Could not update group code for {party_name} ({party_code}): {grp_err}")
                    
                    amount = self._parse_float(v.get('amount') or v.get('total') or 0.0)
                    narration = (v.get('narration') or v.get('narr') or v.get('description') or v.get('raw_narration') or party_name).strip()
                    if not narration:
                        narration = f"Cash {tx_type} - {party_name if party_name else 'Suspense'}"
                    
                    if amount <= 0:
                        continue
                        
                    date_str = v.get('date', '')
                    try:
                        v_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                    except:
                        v_date = date.today()
                        
                    f98 = 'CR' if tx_type == 'Receipt' else 'CP'
                    party_class = code_to_classification.get(party_code, 'Other')
                    if self.is_true_contra_entry(party_name, party_code, code_to_classification, party_group_code=v.get('group_hint', '')):
                        f98 = 'BC'
                        self.audit_report['messages'].append(f'Auto-generated Contra Voucher (BC) for Cash/Bank {tx_type}: ₹{amount}')
                    # Anomaly Detection (Rule of thumb > 5 Lakhs for Bank)
                    if amount > 500000:
                        self.audit_report["anomalies"] += 1
                        self.audit_report["messages"].append(f"High-Value Transaction Anomaly: ₹{amount} ({party_name})")
                    
                    # Duplicate Detection: Prevent double-injecting or overwriting manual entries
                    ref_no = (v.get('reference_no') or v.get('bill_no') or '')[:16]
                    ref_no_clean = ref_no.strip().lower()
                    narration_clean = narration[:50].strip().lower()
                    # ── INTRA-BATCH DEDUP: Block identical rows within the same push ──────────
                    batch_key = (str(v_date), round(amount, 2), party_code, cash_ledger_code, f98, ref_no_clean, narration_clean)
                    if batch_key in intra_batch_seen:
                        print(f"🚫 Intra-batch duplicate blocked: {party_name} {amount} {v_date}")
                        self.audit_report["duplicates"] += 1
                        self.audit_report["duplicate_details"].append({
                            "date": str(v_date),
                            "bill_no": ref_no.strip(),
                            "party": party_name,
                            "amount": amount,
                            "reason": "Duplicate row in same push batch",
                            "module": "Cash Entries"
                        })
                        continue
                    intra_batch_seen.add(batch_key)
                    # ────────────────────────────────────────────────────────────────────────

                    dup_key = (str(v_date), amount, party_code, cash_ledger_code, f98, ref_no_clean, narration_clean)
                    if existing_cash_entries.get(dup_key, 0) > 0:
                        existing_cash_entries[dup_key] -= 1
                        self.audit_report["duplicates"] += 1
                        continue
                        
                    if f98 == 'CR':
                        last_cr += 1
                        vou_no = last_cr
                    elif f98 == 'CP':
                        last_cp += 1
                        vou_no = last_cp
                    else:
                        last_cv += 1
                        vou_no = last_cv

                    v_id = gen_id(f98)
                    
                    # 1. T41 Header
                    t41_rec = {
                        'FIELD98': f98,
                        'FIELD99': f98,
                        'FIELD01': v_id,
                        'FIELD02': v_date,
                        'FIELD03': '2',
                        'FIELD04': party_code,
                        'FIELD05': cash_ledger_code,
                        'FIELD06': amount,
                        'FIELD07': amount,
                        'FIELD10': ref_no.strip(),  # Chq/DD No.
                        'FIELD11': v_date,  # Chq/DD Date
                        'FIELD12': str(vou_no),
                        'FIELD14': 'N',
                        'FIELD16': 'C' if f98 == 'BC' else ('R' if tx_type == 'Receipt' else 'P'),  # BC=Contra ('C'), CR=Receipt ('R'), CP=Payment ('P')
                        'FIELD17': 'U0000000',
                        'FIELD18': 0.0,
                        'FIELD20': 0,
                        'FIELD21': 'O',  # Corrected: Match native Cash/Bank 'O' value
                        'FIELD51': 0.0,
                        'FIELD74': 'CB',
                        'FIELD75': '0',
                        'FIELD82': self.fit_dbf_str(narration, 50),  # Narration
                        'T41F83': resolved_f83,
                        'T41FVNO': str(vou_no),
                        'T41F45': year_num,
                        'T41F97': '01',
                        'T41F96': 'N',
                        'EDVAS00095': 0.0,
                        'EPVAS00095': 0.0,
                        'EDVAS00097': 0.0,
                        'EPVAS00097': 0.0,
                        'EDGAS00001': 0.0,
                        'EPGAS00001': 0.0,
                        'EDGAS00002': 0.0,
                        'EPGAS00002': 0.0,
                        'EDGAS00003': 0.0,
                        'EPGAS00003': 0.0,
                        'EDVAS00099': 0.0,
                        'EPVAS00099': 0.0
                    }
                    self._append_record(t41, t41_rec)
                    guids_to_register.append(('YRT41', v_id, True))
                    
                    # 2. T01 Line 1: Cash Ledger
                    is_contra = (f98 == 'BC')
                    t01_f96_val = 'N'
                    cash_dr_cr = 'D' if tx_type == 'Receipt' else 'C'
                    t01_rec_cash = {
                        'FIELD98': f98,
                        'FIELD99': f98,
                        'FIELD01': v_id,
                        'FIELD02': v_date,
                        'FIELD03': cash_ledger_code,
                        'FIELD04': party_code,
                        'FIELD05': amount,
                        'FIELD06': cash_dr_cr,
                        'FIELD08': 0.0,
                        'FIELD09': f"{line_idx_t01:>4}",
                        'FIELD11': '2',
                        'FIELD12': str(vou_no),
                        'T41FVNO': str(vou_no),
                        'FIELD15': '',
                        'FIELD16': None,
                        'FIELD20': 'N',   # 'N' = Normal active line (Native Miracle requirement so amounts display in Ledger reports)
                        'FIELD21': 'CS',
                        'FIELD22': None,
                        'FIELD26': 0.0,
                        'FIELD29': 0.0,
                        'T01F97': '01',
                        'FIELD75': '0',
                        'T01F96': 'N'     # FIXED: 'N' for all Cash/Bank lines
                    }
                    self._append_record(t01, t01_rec_cash, {'FIELD09': f"{line_idx_t01:>4}"})
                    line_idx_t01 += 1
                    
                    # 3. T01 Line 2: Party Ledger
                    # Native Miracle uses 'PR' (Party) for Party, 'PT' (Payment/Receipt) for Expenses/Others
                    party_dr_cr = 'C' if tx_type == 'Receipt' else 'D'
                    other_class = code_to_classification.get(party_code, 'Other')
                    if not self.is_true_contra_entry(party_name, party_code, code_to_classification, party_group_code=v.get('group_hint', '')) and (other_class in ('Expense', 'Indirect Expenses', 'Direct Expenses') or any(kw in party_name.upper() for kw in self.BANK_EXPENSE_KEYWORDS)):
                        resolved_f21 = 'PT'
                    elif other_class == 'Bank':
                        resolved_f21 = 'BK'
                    elif other_class == 'Cash' or party_name.upper() in ('CASH ACCOUNT', 'CASH A/C', 'PETTY CASH'):
                        resolved_f21 = 'CS'
                    elif other_class in ('Debtor', 'Creditor'):
                        resolved_f21 = 'PR'
                    else:
                        resolved_f21 = 'PT'
                        
                    party_f16_val = v_date if (is_contra or resolved_f21 == 'BK') else None
                    
                    t01_rec_party = {
                        'FIELD98': f98,
                        'FIELD99': f98,
                        'FIELD01': v_id,
                        'FIELD02': v_date,
                        'FIELD03': party_code,
                        'FIELD04': cash_ledger_code,
                        'FIELD05': amount,
                        'FIELD06': party_dr_cr,
                        'FIELD08': 0.0,
                        'FIELD09': f"{line_idx_t01:>4}",
                        'FIELD11': '2',
                        'FIELD12': str(vou_no),
                        'T41FVNO': str(vou_no),
                        'FIELD16': party_f16_val,
                        'FIELD20': 'N',   # 'N' = Normal active line (Native Miracle requirement so amounts display in Ledger reports)
                        'FIELD21': resolved_f21,  # Dynamic PT/PR/CS mapping
                        'FIELD22': None,
                        'FIELD26': 0.0,
                        'FIELD29': 0.0,
                        'T01F97': '01',
                        'FIELD75': '0',
                        'T01F96': 'N'     # FIXED: 'N' for all Cash/Bank lines
                    }
                    self._append_record(t01, t01_rec_party, {'FIELD09': f"{line_idx_t01:>4}"})
                    line_idx_t01 += 1
                    
                    # 4. T40 Narration Record (Full narration lookup for Miracle UI)
                    t40_rec = {
                        'T40F01': v_id,
                        'T40F09': 'XXXX',
                        'T40F02': narration
                    }
                    self._append_record(t40, t40_rec)
                    

                    injected_count += 1
                    self.audit_report["injected"] += 1
                    
            finally:
                t41.close()
                t01.close()
                t40.close()
            
            self._register_guids_batch(guids_to_register)
                
        # Compact modified tables and restore CDX flags
        for tbl in ['rkacct41.dbf', 'rkacct01.dbf', 'rkacct40.dbf']:
            self.compact_table(tbl, year_folder)
        self.ensure_cdx_flags_active(year_folder)
                
        # Trigger reindexing
        self.reindex_tables(year_folder)
        return injected_count
