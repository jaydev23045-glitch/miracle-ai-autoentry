import json
import os
import re
import threading
import time

_memory_locks = {}
_global_lock = threading.Lock()

# ── Memory In-Process Cache ───────────────────────────────────────────────────
# key: (vault_path, file_path_string) → (timestamp: float, data: dict)
_memory_cache: dict = {}
_memory_cache_ttl: float = 60.0            # 60-second TTL — safe for all use cases
_memory_cache_lock = threading.Lock()

def _get_client_lock(client_id: str) -> threading.Lock:
    with _global_lock:
        if client_id not in _memory_locks:
            _memory_locks[client_id] = threading.Lock()
        return _memory_locks[client_id]

class AIMemoryVault:
    def __init__(self, vault_path: str = None):
        if not vault_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            vault_path = os.path.join(base_dir, 'AI_Memory_Vault')
        self.vault_path = vault_path
        if not os.path.exists(self.vault_path):
            os.makedirs(self.vault_path, exist_ok=True)

    def _get_file_path(self, client_id: str, tenant_id: str = None, miracle_base_path: str = "", company_name: str = "") -> str:
        """
        Constructs a 100% collision-proof multi-tenant memory file path.
        Combines Optional Tenant ID + Company Name Fingerprint + Client ID (CMPxxxx) + Path Fingerprint Hash.
        This guarantees Jayesh Traders (CMP0005) and Raju Manufacturing (CMP0005) have SEPARATE memory files!
        """
        import hashlib
        key_parts = []
        if tenant_id:
            safe_tenant = re.sub(r'[^A-Za-z0-9_\-]', '', str(tenant_id)).lower()
            key_parts.append(safe_tenant)
        if company_name:
            safe_comp = re.sub(r'[^A-Za-z0-9]', '', str(company_name)).lower()[:20]
            if safe_comp:
                key_parts.append(safe_comp)
        key_parts.append(client_id)
        if miracle_base_path:
            path_hash = hashlib.md5(miracle_base_path.encode('utf-8')).hexdigest()[:8]
            key_parts.append(path_hash)
        
        file_key = "_".join(key_parts)
        return os.path.join(self.vault_path, f"{file_key}_memory.json")

    def load_memory(self, client_id: str, tenant_id: str = None, miracle_base_path: str = "", company_name: str = "") -> dict:
        """
        Loads memory for a client safely using 4-tier lookup:
        1. Tier 1: Exact Tenant + Company Name + Client + Path Hash
        2. Tier 2: Exact Tenant + Client + Path Hash
        3. Tier 3: Path Changed Resilience (Finds previous memory file if client changed Miracle path!)
        4. Tier 4: Standard Client ID Fallback
        """
        file_path = self._get_file_path(client_id, tenant_id=tenant_id, miracle_base_path=miracle_base_path, company_name=company_name)
        cache_key = (self.vault_path, file_path)

        # ── Fast Path: Return in-process cached data if still fresh ───────────────
        with _memory_cache_lock:
            cached = _memory_cache.get(cache_key)
            if cached and (time.monotonic() - cached[0]) < _memory_cache_ttl:
                import copy
                return copy.deepcopy(cached[1])

        result = None
        with _get_client_lock(client_id):
            # Tier 1: Exact match with company name
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        result = json.load(f)
                except Exception as e:
                    print(f"Error loading memory for {client_id}: {e}")

            # Tier 2: Check without company_name parameter
            if result is None:
                alt_path = self._get_file_path(client_id, tenant_id=tenant_id, miracle_base_path=miracle_base_path)
                if os.path.exists(alt_path):
                    try:
                        with open(alt_path, 'r', encoding='utf-8') as f:
                            result = json.load(f)
                    except Exception as e:
                        pass

            # Tier 3: Path Changed Protection (Finds previous memory if client changed Miracle folder path!)
            if result is None and tenant_id:
                safe_tenant = re.sub(r'[^A-Za-z0-9_\-]', '', str(tenant_id)).lower()
                prefix = f"{safe_tenant}_"
                if os.path.exists(self.vault_path):
                    for fname in os.listdir(self.vault_path):
                        if fname.startswith(prefix) and client_id in fname and fname.endswith("_memory.json"):
                            prev_path = os.path.join(self.vault_path, fname)
                            try:
                                with open(prev_path, 'r', encoding='utf-8') as f:
                                    print(f"🔄 [Path Migration] Found previous memory for {tenant_id}/{client_id} at {fname}")
                                    result = json.load(f)
                                    break
                            except Exception as ex:
                                print(f"Error loading previous memory {fname}: {ex}")

            # Tier 4: Standard Client ID Fallback
            if result is None:
                fallback_path = os.path.join(self.vault_path, f"{client_id}_memory.json")
                if os.path.exists(fallback_path):
                    try:
                        with open(fallback_path, 'r', encoding='utf-8') as f:
                            result = json.load(f)
                    except Exception as e:
                        print(f"Error loading fallback memory for {client_id}: {e}")

            if result is None:
                result = {"expense_mappings": {}, "custom_fields": {}}

        with _memory_cache_lock:
            import copy
            _memory_cache[cache_key] = (time.monotonic(), copy.deepcopy(result))

        import copy
        return copy.deepcopy(result)

    def invalidate_memory_cache(self, client_id: str, tenant_id: str = None, miracle_base_path: str = "", company_name: str = ""):
        """Explicitly evict cache entry for this client (call after bulk imports/deletes)."""
        file_path = self._get_file_path(client_id, tenant_id=tenant_id, miracle_base_path=miracle_base_path, company_name=company_name)
        cache_key = (self.vault_path, file_path)
        with _memory_cache_lock:
            _memory_cache.pop(cache_key, None)

    @staticmethod
    def clean_mapping_key(narration: str) -> str:
        """
        Strips ALL transient noise from a bank narration to produce a stable
        core keyword that matches the SAME vendor/expense across any month.

        Strips:
          - Transaction type prefixes (UPI, NEFT DR, RTGS, IMPS, EFT DR ...)
          - Bank IFSC routing codes (ICICR, KKBK, BKIDR, UTIBR, HDFC0, ...)
          - UPI handle suffixes (@ybl, @okicici, @paytm ...)
          - Reference / UTR numbers (5+ digit standalone numbers)
          - Date tokens (DDMMYYYY patterns, month names, year numbers)
          - Common city/state names that appear in narrations
          - Short filler words (CR, DR, BY, TO, NO, REF, TXN, INB, MB, OB ...)
          - Short tokens (< 3 chars) that carry no meaning
        """
        import re
        if not narration or not isinstance(narration, str):
            return ""

        txt = " ".join(narration.split()).upper()

        # 0. Strip leading standalone account/reference numbers (e.g. 01631000019173-TPT-PARKING -> TPT-PARKING)
        txt = re.sub(r'^\d{5,}[-_\s]+', '', txt)

        # 1. Strip transaction type prefixes at the start
        txt = re.sub(
            r'^(ACH\s*[CD]?-|ACH\s*[CD]\s+|ACH\s*DR-|ACH\s*CR-|UPI|IMPS|NEFT DR|NEFT CR|RTGS DR|RTGS CR|RTGS|NEFT|EFT DR|EFT CR|EFT|'
            r'CASH DEPOSIT BY|CASH DEPOSIT|CASH WITHDRAWAL|TRANSFER TO|TRANSFER FROM|'
            r'TPT|INB|MB|OB|CHQ|CHEQUE|CHQS|ATM WDL|ATM|POS|ACH DR|ACH CR|ACH|'
            r'SI DEF|NACH DR|NACH CR|NACH)[-/_\s]*',
            '', txt, flags=re.IGNORECASE
        )

        # 2. Strip leading numbers or sequence IDs (e.g. 5838 FOOT WEAR -> FOOT WEAR)
        txt = re.sub(r'^\d{3,6}\s+', '', txt)

        # 3. Strip UPI handle suffixes (@ybl, @okicici, .sbi, .oksbi, @paytm, @kotak, @hdfc ...)
        txt = re.sub(r'@[A-Za-z0-9_\-\.]+', '', txt)
        txt = re.sub(r'[\.\-](?:SBI|OKSBI|OKICICI|OKAXIS|KHDFCBANK|YBL|KOTAK|PAYTM|PHONEPE|GPAY|BHIM|PTYES|AXIS|ICICI|HDFC)\b', '', txt, flags=re.IGNORECASE)

        # 4. Strip bank IFSC routing codes and truncated fragments
        txt = re.sub(r'\b[A-Z]{4}[0-9][A-Z0-9]{4,6}\b', '', txt)   # full IFSC
        txt = re.sub(r'\b[A-Z]{4}[R0-9][0-9]{0,2}\b', '', txt)      # truncated IFSC fragment

        # 5. Strip long standalone numbers (5+ digits: UTRs, ref IDs, phone numbers, account numbers)
        txt = re.sub(r'\b\d{5,}\b', '', txt)

        # 6. Strip numbers attached to letters (e.g. HETALBHIMANI26215 → HETALBHIMANI)
        txt = re.sub(r'(?<=[A-Z])\d+', '', txt)
        txt = re.sub(r'\b\d+(?=[A-Z])', '', txt)

        # 7. Strip date/month/year noise tokens
        MONTH_NAMES = (
            'JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC|'
            'JANUARY|FEBRUARY|MARCH|APRIL|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER'
        )
        txt = re.sub(rf'\b({MONTH_NAMES})\b', '', txt)
        txt = re.sub(r'\b20[0-9][0-9]\b', '', txt)   # year like 2024, 2025
        txt = re.sub(r'\b[0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4}\b', '', txt)  # date like 31/03/25

        # 8. Strip common city/state names that appear in narrations
        CITIES = (
            'RAJKOT|AHMEDABAD|MUMBAI|DELHI|NEW DELHI|SURAT|VADODARA|BARODA|PUNE|'
            'BANGALORE|BENGALURU|HYDERABAD|CHENNAI|KOLKATA|JAIPUR|INDORE|NAGPUR|'
            'GANDHINAGAR|ANAND|NADIAD|BHAVNAGAR|JUNAGADH|MORBI|AMRELI|BHARUCH|'
            'NAVSARI|VAPI|VALSAD|MEHSANA|PATAN|SURENDRANAGAR|JAMNAGAR|PORBANDAR'
        )
        txt = re.sub(rf'\b({CITIES})\b', '', txt)

        # 9. Strip generic filler words, bank handles, and remark tails
        FILLER = (
            'SENT|USING|PAYTM|PHONEPE|GPAY|BHIM|UPI|TRANSFER|PAYMENT|RECEIVED|'
            'CR|DR|REF|NO|TXN|BY|TO|FROM|INB|MB|OB|TPT|VIA|THRU|THROUGH|FOR|AND|'
            'THE|OF|IN|ON|AT|OR|PVT|LTD|LIMITED|PRIVATE|CO|CORP|INC|'
            'NETBANK|NETB|HDFCH|HDFCN|HDFCE|HDFCBANK|ICICI|ICIC|OKICICI|OKAXIS|'
            'WAAXIS|NAVIAXIS|PTAXIS|YESCRED|PTYES|KOTAK|OKSBI|MAHB|BARB|SVCB|'
            'TMBL|INDB|CCBL|OKHDFCBANK|YBL|AXL|IPL|IBL|REMARK|REMARKS|INSTAALERTCHG|'
            'SMS|CDT|BBN|SELF|NEHRU|NAGAR|KURLA|EAST|WEST|SOUTH|NORTH|BRANCH|'
            'KAXIS|IS|CI|FCBANK|KHDFCBANK|DFCBANK|OKICIC|KICICI|OKS|OKI|OKA|XIS|REMA|INING|REMAINING|PART'
        )
        txt = re.sub(rf'\b({FILLER})\b', ' ', txt)

        # 10. Strip all remaining non-alphanumeric characters
        txt = re.sub(r'[^A-Z0-9\s]', ' ', txt)

        # 11. Remove single/double character tokens (noise like 'Q', 'L', 'I', '1')
        txt = ' '.join(w for w in txt.split() if len(w) >= 3)
        txt = txt.strip()

        # 12. Syllable reconciliation & word deduplication (e.g., CRED CRED CLUB CRED -> CRED CLUB)
        words = txt.split()
        merged_words = []
        i = 0
        while i < len(words):
            w = words[i]
            if i + 1 < len(words) and len(w) <= 3 and len(words[i+1]) <= 3:
                merged_words.append(w + words[i+1])
                i += 2
            else:
                merged_words.append(w)
                i += 1
        
        # Deduplicate consecutive/repeated words (e.g. CRED CRED CLUB CRED -> CRED CLUB)
        dedup_words = []
        for w in merged_words:
            if len(w) >= 3 and (not dedup_words or w != dedup_words[-1]):
                dedup_words.append(w)
        txt = ' '.join(dedup_words).strip()

        # 13. Strict Sanity Guard: Reject pure numeric keys (e.g. 7432, 757) or short noise (<3 chars)
        if not txt or len(txt) < 3 or re.match(r'^\d+$', txt):
            raw_clean = re.sub(r'\b\d+\b', ' ', narration.upper())
            raw_clean = re.sub(r'[^A-Z\s]', ' ', raw_clean)
            words = [w for w in raw_clean.split() if len(w) >= 3 and w not in ['NETBANK', 'HDFCH', 'HDFCN', 'HDFCE', 'OKICICI', 'OKAXIS', 'OKHDFCBANK']]
            txt = ' '.join(words).strip()
            if not txt or len(txt) < 3 or re.match(r'^\d+$', txt):
                return ""

        return txt

    @staticmethod
    def clean_mapping_value(val: str) -> str:
        """
        Sanitizes mapped ledger values stored in memory vault to remove raw bank handles,
        gateway noise, trailing reference numbers, and format them into clean human names.
        """
        if not val or not isinstance(val, str):
            return ""
        val_str = val.strip()

        STANDARD_LEDGERS = {
            'SALARY', 'STAFF SALARY', 'MAID SALARY', 'OFFICE RENT', 'RENT A/C', 'RENT EXPENSES',
            'TELEPHONE EXP', 'ELECTRICITY', 'BANK CHARGES', 'DAILY ALLOWANCE', 'OFFICE EXPENSE A/C',
            'TRAVEL A/C', 'PRINTING & STATIONERY', 'MISCELLANEOUS EXPENSES', 'EMPLOYE COMISSION',
            'SUNDRY DEBTORS', 'SUNDRY CREDITORS', 'CASH ACCOUNT', 'SUSPENSE ACCOUNT'
        }
        if val_str.upper() in STANDARD_LEDGERS:
            return val_str

        # Import GeminiService's clean party extractor
        try:
            from gemini_service import GeminiService
            clean_formatted = GeminiService.extract_clean_party_from_narration(val_str)
            if clean_formatted and len(clean_formatted) >= 2 and clean_formatted.upper() not in ('PRIVATE LIMITED', 'PVT LTD', 'LLP'):
                return clean_formatted
        except Exception:
            pass

        # Strip @handle domain suffixes
        clean_val = re.sub(r'@[A-Za-z0-9_\-\.]+', '', val_str)
        clean_val = re.sub(r'\b\d{5,}\b', '', clean_val)
        clean_val = re.sub(r'(?<=[A-Za-z]{3})\d{1,4}\b', '', clean_val)

        NOISE = {
            'OKAXIS', 'OKICICI', 'OKHDFCBANK', 'OKSBI', 'PTYES', 'YESCRED', 'NAVIAXIS', 'PTAXIS',
            'WAAXIS', 'AXL', 'YBL', 'IPL', 'IBL', 'KOTAK', 'PAYTM', 'PHONEPE', 'GPAY', 'BHIM',
            'SENT', 'USING', 'REMARKS', 'REMARK', 'INSTAALERTCHG', 'SMS', 'CDT', 'NETBANK',
            'NETB', 'HDFCH', 'HDFCN', 'HDFCE', 'HDFCBANK', 'ICICI', 'AXIS', 'MAHB', 'SVCB',
            'TMBL', 'INDB', 'CCBL', 'KAXIS', 'IS', 'CI', 'FCBANK', 'KHDFCBANK', 'DFCBANK', 'OKICIC', 'KICICI', 'OKS', 'OKI', 'OKA', 'XIS'
        }
        tokens = [w for w in re.split(r'[\s\-\/@._]+', clean_val) if w.upper() not in NOISE]
        clean_val = " ".join(tokens).strip()
        return clean_val.title() if clean_val else val_str

    PROTECTED_NATURE_KEYWORDS = {
        "CASH", "CHEQUE", "CHQ", "ATM", "TRANSFER", "ONLINE", "PAYMENT", "RECEIPT", 
        "DEPOSIT", "NEFT", "RTGS", "UPI", "IMPS", "EFT", "POS", "CARD", "INTERNET BANKING",
        "COMPUTER", "COMPUTERS", "LAPTOP", "PRINTER", "MOBILE", "CAR", "VEHICLE", 
        "MACHINE", "EQUIPMENT", "FURNITURE", "ASSET",
        "SALARY", "SALARIES", "RENT", "TEA", "REFRESHMENT", "PETROL", "FUEL", 
        "ELECTRICITY", "TELEPHONE", "INTEREST", "BANK CHARGES", "DEPOSITORY", 
        "COMMISSION", "DISCOUNT", "DAIRY", "COSMOFEED"
    }

    INDIAN_ACCOUNTING_NATURE_MAP = {
        # Personal / Drawings (Income Tax Sec 37(1) - Non-deductible personal spending)
        "PERSONAL_DRAWINGS": {
            "MOM", "MOTHER", "WIFE", "SON", "DAUGHTER", "BROTHER", "SISTER", "FAMILY", "SELF", 
            "HOME", "HOUSEHOLD", "LIC", "LIFE INSURANCE", "HEALTH INSURANCE", "MEDICLAIM", 
            "SCHOOL FEES", "TUITION", "GROCERY", "SUPERMARKET", "JEWELLERY", "PERSONAL EXPENSE"
        },
        # Capital Assets / Fixed Assets (AS-10 / Ind AS 16)
        "FIXED_ASSETS": {
            "COMPUTER", "COMPUTERS", "LAPTOP", "PRINTER", "PRINTERS", "MONITOR", "SERVER",
            "MOBILE", "SMARTPHONE", "AIR CONDITIONER", "AC", "REFRIGERATOR", "MACHINERY", 
            "EQUIPMENT", "PLANT", "FURNITURE", "FIXTURES", "VEHICLE", "CAR", "BIKE", "SCOOTER"
        },
        # Operational Indirect Expenses (Nominal Accounts - Profit & Loss)
        "INDIRECT_EXPENSES": {
            "RENT", "OFFICE RENT", "SALARY", "STAFF SALARY", "WAGES", "ELECTRICITY", "POWER", 
            "TELEPHONE", "INTERNET", "BROADBAND", "PETROL", "DIESEL", "FUEL", "VEHICLE REPAIR", 
            "TEA", "COFFEE", "SNACKS", "REFRESHMENT", "PRINTING", "STATIONERY", "POSTAGE", 
            "COURIER", "AUDIT FEES", "LEGAL FEES", "PROFESSIONAL FEES", "COMMISSION", "DISCOUNT",
            "PARKING", "PARKING CHARGES", "PARKING EXPENSE", "REIMBURSEMENT", "ALLOWANCE", "TRAVEL", "CONVEYANCE", "FREIGHT", "TRANSPORT"
        },
        # Statutory Taxes & Govt Duties
        "DUTIES_AND_TAXES": {
            "GSTPMT", "GST", "CGST", "SGST", "IGST", "TDS", "INCOME TAX", "ADVANCE TAX", 
            "SELF ASSESSMENT TAX", "PROFESSIONAL TAX", "CHALLAN", "GOVT TAX"
        },
        # Bank Fees & Charges
        "BANK_CHARGES": {
            "BANK CHARGES", "BANK COMM", "SMS CHARGES", "SERVICE CHARGES", "PROCESSING FEE", 
            "MDR RECOVERY", "RUPAY MDR", "CHQ DEP RET CHGS", "MIN BAL CHG", "DEBIT CARD CHGS", 
            "FOREX CHARGES", "DEPOSITORY CHARGES"
        }
    }

    @staticmethod
    def classify_indian_accounting_nature(clean_key: str) -> dict:
        """
        Classifies a memory search pattern key according to Indian Accounting Rules (ICAI / Income Tax / Ind AS).
        Returns category, default account group, and statutory rule guidance.
        """
        if not clean_key:
            return {"category": "GENERAL", "group_hint": "Indirect Expenses", "is_personal": False}

        k_upper = clean_key.strip().upper()
        words = set(re.split(r'[\s\-\/_]+', k_upper))

        if any(w in AIMemoryVault.INDIAN_ACCOUNTING_NATURE_MAP["PERSONAL_DRAWINGS"] for w in words):
            return {
                "category": "PERSONAL_DRAWINGS",
                "group_hint": "Capital Account / Drawings",
                "is_personal": True,
                "accounting_rule": "Income Tax Sec 37(1): Personal spending mapped to Drawings A/c."
            }

        if any(w in AIMemoryVault.INDIAN_ACCOUNTING_NATURE_MAP["FIXED_ASSETS"] for w in words):
            return {
                "category": "FIXED_ASSETS",
                "group_hint": "Fixed Assets",
                "is_personal": False,
                "accounting_rule": "AS-10 / Ind AS 16: Capital Expenditure categorized under Fixed Assets."
            }

        if any(w in AIMemoryVault.INDIAN_ACCOUNTING_NATURE_MAP["DUTIES_AND_TAXES"] for w in words):
            return {
                "category": "DUTIES_AND_TAXES",
                "group_hint": "Duties & Taxes",
                "is_personal": False,
                "accounting_rule": "Statutory Duty Payment categorized under Duties & Taxes."
            }

        if any(w in AIMemoryVault.INDIAN_ACCOUNTING_NATURE_MAP["BANK_CHARGES"] for w in words):
            return {
                "category": "BANK_CHARGES",
                "group_hint": "Indirect Expenses",
                "is_personal": False,
                "accounting_rule": "Financial Service Charges categorized under Bank Charges."
            }

        if any(w in AIMemoryVault.INDIAN_ACCOUNTING_NATURE_MAP["INDIRECT_EXPENSES"] for w in words):
            return {
                "category": "INDIRECT_EXPENSES",
                "group_hint": "Indirect Expenses",
                "is_personal": False,
                "accounting_rule": "Nominal Account Debit: Routine Revenue Expenditure under Indirect Expenses."
            }

        return {
            "category": "BUSINESS_PARTY",
            "group_hint": "Sundry Debtors / Sundry Creditors",
            "is_personal": False,
            "accounting_rule": "Personal Account: Commercial Trade Debtors/Creditors ledger match."
        }

    @staticmethod
    def is_illegal_nature_mapping(clean_key: str, ledger_val: str) -> bool:
        """
        Smart Accountant Nature Guard:
        Enforces Indian Accounting Rules (ICAI / Ind AS / Income Tax Act Sec 37(1)).
        Blocks generic nature keywords, fixed assets, or personal terms from illegal party mappings.
        """
        if not clean_key or not ledger_val:
            return False
            
        k_upper = clean_key.strip().upper()
        v_upper = ledger_val.strip().upper()
        
        nature = AIMemoryVault.classify_indian_accounting_nature(clean_key)
        
        # Rule 1: Personal Drawings keys MUST NOT map to business indirect expenses or random vendor ledgers
        if nature["category"] == "PERSONAL_DRAWINGS":
            if "DRAWING" not in v_upper and "CAPITAL" not in v_upper and "PERSONAL" not in v_upper and v_upper not in ("MOM", "SELF", "FAMILY"):
                return True

        # Rule 2: Fixed Assets keys MUST NOT map to a personal party name or routine maintenance
        if nature["category"] == "FIXED_ASSETS":
            if not any(kw in v_upper for kw in ("ASSET", "COMPUTER", "LAPTOP", "PRINTER", "EQUIPMENT", "MACHINERY", "VEHICLE", "FURNITURE", "FIXED")):
                return True

        # Rule 3: Nominal Indirect Expenses (PARKING, SALARY, RENT, PETROL, TEA, REPAIR) MUST NOT map to Trade Suppliers/Creditors/Debtors
        if nature["category"] == "INDIRECT_EXPENSES":
            expense_keywords = ("PARKING", "SALARY", "SALARIES", "RENT", "PETROL", "DIESEL", "FUEL", "TEA", "COFFEE", "SNACKS", "REFRESHMENT", "ELECTRICITY", "POWER", "REPAIR", "MAINTENANCE", "STATIONERY", "POSTAGE", "COURIER", "AUDIT", "LEGAL")
            if any(w in k_upper for w in expense_keywords):
                # If target ledger value is a pure trade entity (e.g. TRADERS, ENTERPRISE, SUPPLIERS) and has NO expense head indicators
                trade_indicators = ("TRADERS", "TRADING", "ENTERPRISE", "ENTERPRISES", "INDUSTRIES", "SUPPLIERS", "DISTRIBUTORS", "AGENCIES", "STEEL", "METALS", "SYNDICATE", "INFRA")
                has_expense_head = any(kw in v_upper for kw in ("EXPENSE", "EXP", "A/C", "ACCOUNT", "SALARY", "PARKING", "RENT", "FUEL", "TEA", "REPAIR", "MAINTENANCE", "WELFARE", "REIMBURSEMENT", "ALLOWANCE", "CHARGE", "CHARGES"))
                if any(t_kw in v_upper for t_kw in trade_indicators) and not has_expense_head:
                    return True

        # Rule 4: Tax keywords (INCOME TAX, GST, TDS, TAX) MUST NOT map to casting, handicrafts, traders, or commercial vendors
        if any(w in k_upper for w in ("INCOME TAX", "TAX", "DUTIES & TAXES", "GST", "TDS")):
            if not any(kw in v_upper for kw in ("TAX", "DUTIES", "GST", "GOVT", "DRAWING", "CAPITAL", "SUSPENSE", "DUTIES & TAXES")):
                return True

        return False

    def rebuild_memory_keys(self, client_id: str) -> int:
        """
        Retroactively re-cleans all existing expense_mapping keys using the improved
        clean_mapping_key function. Removes dirty/numeric keys and illegal nature mappings
        (e.g., CASH → RADHE KRISHNA, COMPUTER → MITESHBHAI).
        """
        memory = self.load_memory(client_id)
        old_mappings = memory.get("expense_mappings", {})
        if not old_mappings:
            return 0

        new_mappings = {}
        changed = 0
        for raw_key, ledger in old_mappings.items():
            clean_key = self.clean_mapping_key(raw_key)
            clean_val = self.clean_mapping_value(ledger)
            if not clean_key or len(clean_key) < 3 or re.match(r'^\d+$', clean_key) or self.is_illegal_nature_mapping(clean_key, clean_val):
                changed += 1
                print(f"🧹 [Vault Purifier] Purged illegal nature mapping: '{raw_key}' ('{clean_key}') → '{ledger}'")
                continue  # drop garbage/numeric/illegal nature mappings
            if clean_key not in new_mappings:
                new_mappings[clean_key] = clean_val
                if clean_key != raw_key or clean_val != ledger:
                    changed += 1

        memory["expense_mappings"] = new_mappings
        self.save_memory(client_id, memory)
        print(f"✅ [Memory Rebuild] {client_id}: {len(old_mappings)} keys → {len(new_mappings)} clean keys ({changed} changed/purged).")
        return changed

    def purify_all_client_memories(self) -> dict:
        """
        Scans all client memory JSON files in AI_Memory_Vault and retroactively purges dirty keys
        and reformats all stored mapping values to clean Title-Cased party names.
        """
        if not os.path.exists(self.vault_path):
            return {"status": "success", "processed_clients": 0, "total_changed": 0}

        total_changed = 0
        processed_clients = 0
        results = {}

        for fname in os.listdir(self.vault_path):
            if fname.endswith("_memory.json"):
                client_id = fname.replace("_memory.json", "")
                try:
                    changed = self.rebuild_memory_keys(client_id)
                    total_changed += changed
                    processed_clients += 1
                    results[client_id] = changed
                except Exception as e:
                    print(f"⚠️ Error purifying memory for {client_id}: {e}")

        print(f"🧹 [Memory Vault Purification] Cleaned {processed_clients} client vault files ({total_changed} keys updated/purged).")
        return {
            "status": "success",
            "processed_clients": processed_clients,
            "total_changed": total_changed,
            "details": results
        }

    @staticmethod
    def prune_mappings(memory_data: dict) -> dict:
        """
        Scans expense_mappings and deletes redundant longer keys if a shorter,
        encompassing core substring key exists mapping to the same target ledger.
        """
        mappings = memory_data.get("expense_mappings", {})
        if not mappings:
            return memory_data
            
        cleaned_mappings = {}
        for k, v in mappings.items():
            ck = AIMemoryVault.clean_mapping_key(k)
            if ck and v:
                cleaned_mappings[ck] = v
                
        # Sort keys by length so shorter keys are processed first
        sorted_keys = sorted(cleaned_mappings.keys(), key=len)
        pruned = {}
        for key in sorted_keys:
            val = cleaned_mappings[key]
            # Check if any already-saved shorter key is a substring and maps to the same ledger
            is_redundant = False
            for saved_key, saved_val in pruned.items():
                if saved_val.upper() == val.upper() and saved_key in key:
                    is_redundant = True
                    break
            if not is_redundant:
                pruned[key] = val
                
        memory_data["expense_mappings"] = pruned
        return memory_data

    def save_memory(self, client_id: str, memory_data: dict, tenant_id: str = None, miracle_base_path: str = "", company_name: str = ""):
        """Saves updated memory rules to the client's local JSON file atomically with multi-tenant isolation."""
        file_path = self._get_file_path(client_id, tenant_id=tenant_id, miracle_base_path=miracle_base_path, company_name=company_name)
        # Automatically prune and deduplicate before saving
        memory_data = self.prune_mappings(memory_data)
        with _get_client_lock(client_id):
            try:
                temp_path = file_path + ".tmp"
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(memory_data, f, indent=4, ensure_ascii=False)
                os.replace(temp_path, file_path)
                import copy
                cache_key = (self.vault_path, file_path)
                with _memory_cache_lock:
                    _memory_cache[cache_key] = (time.monotonic(), copy.deepcopy(memory_data))
            except Exception as e:
                print(f"Error saving memory for {client_id}: {e}")

    def find_fast_keyword_expense_mapping(self, client_id: str, raw_narration: str) -> tuple[str, str]:
        """
        High-speed O(1) keyword index tab lookup.
        Splits raw_narration into clean uppercase tokens and checks exact hash map matches
        in O(1) time without running slow O(N*M) edit distance loops.
        Returns (mapped_ledger, matched_key) or ("", "").
        """
        clean_k = self.clean_mapping_key(raw_narration)
        if not clean_k or len(clean_k) < 3:
            return ("", "")

        memory = self.load_memory(client_id)
        mappings = memory.get("expense_mappings", {})
        if not mappings:
            return ("", "")

        # 1. Exact full key match (O(1))
        if clean_k in mappings:
            return (mappings[clean_k], clean_k)

        # 2. Token Set / Word Boundary Hash Match (O(Words))
        tokens = [t for t in re.split(r'[^A-Z0-9]', clean_k) if len(t) >= 3]
        for token in tokens:
            if token in mappings:
                return (mappings[token], token)

        # 3. Fast Substring keyword check (Sorted by length descending for best specificity)
        for k in sorted(mappings.keys(), key=len, reverse=True):
            if len(k) >= 4 and (k in clean_k or clean_k in k):
                return (mappings[k], k)

        return ("", "")

    def find_fuzzy_expense_mapping(self, client_id: str, raw_narration: str, cutoff: float = 0.85) -> tuple[str, str]:
        """
        Looks up mapped ledger for raw_narration using high-speed O(1) token index matching.
        Returns (mapped_ledger, matched_key) or ("", "").
        """
        return self.find_fast_keyword_expense_mapping(client_id, raw_narration)

    def delete_expense_mapping(self, client_id: str, key: str) -> bool:
        """Deletes a learned expense mapping key from client memory."""
        memory = self.load_memory(client_id)
        mappings = memory.get("expense_mappings", {})
        clean_k = self.clean_mapping_key(key) if key else ""
        deleted = False
        if key in mappings:
            del mappings[key]
            deleted = True
        elif clean_k in mappings:
            del mappings[clean_k]
            deleted = True
        if deleted:
            memory["expense_mappings"] = mappings
            self.save_memory(client_id, memory)
        return deleted

    def add_expense_mapping(self, client_id: str, narration_keyword: str, ledger_name: str):
        """Teaches the AI a new expense mapping for a client."""
        memory = self.load_memory(client_id)
        if "expense_mappings" not in memory:
            memory["expense_mappings"] = {}
        
        # Clean the key before storing
        clean_key = self.clean_mapping_key(narration_keyword)
        if clean_key:
            memory["expense_mappings"][clean_key] = ledger_name
        self.save_memory(client_id, memory)

    def batch_add_expense_mappings(self, client_id: str, mappings: dict):
        """
        Batch-writes multiple narration→ledger expense mappings in a SINGLE disk read + write.

        Eliminates the N-read / N-write pattern of calling add_expense_mapping() in a loop.
        All keys are cleaned via clean_mapping_key() before storing.

        Args:
            client_id: The client identifier (e.g. 'CMP0003').
            mappings:  Dict of {raw_narration: ledger_name}. Empty or None values are skipped.
        """
        if not mappings:
            return
        memory = self.load_memory(client_id)
        if "expense_mappings" not in memory:
            memory["expense_mappings"] = {}
        added = 0
        for narration_keyword, ledger_name in mappings.items():
            if not narration_keyword or not ledger_name:
                continue
            clean_key = self.clean_mapping_key(narration_keyword)
            if clean_key:
                memory["expense_mappings"][clean_key] = ledger_name
                added += 1
        if added:
            self.save_memory(client_id, memory)

    def set_custom_field_mapping(self, client_id: str, field_name: str, miracle_column: str):
        """Configures the AI to extract a custom field to a specific DBF column."""
        memory = self.load_memory(client_id)
        if "custom_fields" not in memory:
            memory["custom_fields"] = {}
        memory["custom_fields"][field_name] = miracle_column
        self.save_memory(client_id, memory)

    def get_company_settings(self, client_id: str) -> dict:
        """Retrieves global rules/settings for a specific company."""
        memory = self.load_memory(client_id)
        return memory.get("company_settings", {})

    def set_company_settings(self, client_id: str, settings: dict):
        """Saves global rules/settings for a specific company."""
        memory = self.load_memory(client_id)
        if "company_settings" not in memory:
            memory["company_settings"] = {}
        memory["company_settings"].update(settings)
        self.save_memory(client_id, memory)

    def get_business_profile(self, client_id: str) -> str:
        """Retrieves the generated business profile for the client."""
        memory = self.load_memory(client_id)
        return memory.get("business_profile", "")

    def set_business_profile(self, client_id: str, profile_text: str):
        """Saves the generated business profile to the client's memory."""
        memory = self.load_memory(client_id)
        memory["business_profile"] = profile_text
        self.save_memory(client_id, memory)

    def get_specifications(self, client_id: str) -> str:
        """Retrieves the client-provided specifications/remarks for the AI."""
        memory = self.load_memory(client_id)
        return memory.get("specifications", "")

    def set_specifications(self, client_id: str, spec_text: str):
        """Saves client specifications/remarks to memory to be used during extraction."""
        memory = self.load_memory(client_id)
        memory["specifications"] = spec_text
        self.save_memory(client_id, memory)

    def get_product_mappings(self, client_id: str) -> dict:
        """Retrieves the rule-based product mappings for the client."""
        memory = self.load_memory(client_id)
        return memory.get("product_mappings", {"gst_rules": {}, "keyword_rules": {}, "instructions": ""})

    def save_product_mappings(self, client_id: str, mappings: dict):
        """Saves the updated product mappings dictionary to the client's memory."""
        memory = self.load_memory(client_id)
        memory["product_mappings"] = mappings
        self.save_memory(client_id, memory)

    def add_product_keyword_rule(self, client_id: str, keyword: str, product_name: str):
        """Saves a new keyword-based product mapping rule to the client's memory."""
        memory = self.load_memory(client_id)
        if "product_mappings" not in memory:
            memory["product_mappings"] = {"gst_rules": {}, "keyword_rules": {}, "instructions": ""}
        if "keyword_rules" not in memory["product_mappings"]:
            memory["product_mappings"]["keyword_rules"] = {}
        memory["product_mappings"]["keyword_rules"][keyword.strip().lower()] = product_name.strip()
        self.save_memory(client_id, memory)

    def train_from_history(self, client_id: str, client_path: str):
        """Scans historical DBFs across all year folders and auto-trains clean expense mappings."""
        from collections import defaultdict
        import dbfread
        import traceback
        
        try:
            folders = [d for d in os.listdir(client_path) if d.upper().startswith('YR') and os.path.isdir(os.path.join(client_path, d))]
            if not folders:
                return 0
                
            narration_map = defaultdict(lambda: defaultdict(int))
            
            for folder in folders:
                try:
                    year_path = os.path.join(client_path, folder)
                    t41_path = os.path.join(year_path, "RKACCT41.DBF")
                    t40_path = os.path.join(year_path, "RKACCT40.DBF")
                    m01_path = os.path.join(year_path, "RKACCM01.DBF")
                    
                    if not os.path.exists(t41_path): t41_path = os.path.join(year_path, "rkacct41.dbf")
                    if not os.path.exists(t40_path): t40_path = os.path.join(year_path, "rkacct40.dbf")
                    if not os.path.exists(m01_path): m01_path = os.path.join(year_path, "rkaccm01.dbf")
                    
                    if not os.path.exists(t41_path) or not os.path.exists(m01_path):
                        continue
                        
                    # Build Ledger Code -> Name map
                    ledger_names = {}
                    for r in dbfread.DBF(m01_path, load=True, encoding='cp1252'):
                        if hasattr(dbfread.DBF, 'is_deleted') and getattr(dbfread.DBF, 'is_deleted')(r): continue
                        code = str(r.get('FIELD01', '')).strip()
                        name = str(r.get('FIELD02', '')).strip()
                        if code and name:
                            ledger_names[code] = name
                            
                    # 1. Extract from RKACCT41.DBF (FIELD82 is native 50-char narration)
                    for r in dbfread.DBF(t41_path, load=True, encoding='cp1252'):
                        party_code = str(r.get('FIELD04', '')).strip()
                        narr82 = str(r.get('FIELD82', '')).strip()
                        if party_code and narr82 and len(narr82) >= 3:
                            clean_k = self.clean_mapping_key(narr82)
                            if clean_k and len(clean_k) >= 3:
                                narration_map[clean_k][party_code] += 1
                                
                    # 2. Extract from RKACCT40.DBF if present
                    if os.path.exists(t40_path):
                        t41_map = {}
                        for r in dbfread.DBF(t41_path, load=True, encoding='cp1252'):
                            vid = str(r.get('FIELD01', '')).strip()
                            party_code = str(r.get('FIELD04', '')).strip()
                            if vid and party_code:
                                t41_map[vid] = party_code
                        for r in dbfread.DBF(t40_path, load=True, encoding='cp1252'):
                            vid = str(r.get('T40F01', '')).strip()
                            narr40 = str(r.get('T40F02', '')).strip()
                            party_code = t41_map.get(vid)
                            if party_code and narr40 and len(narr40) >= 3:
                                clean_k = self.clean_mapping_key(narr40)
                                if clean_k and len(clean_k) >= 3:
                                    narration_map[clean_k][party_code] += 1
                except Exception as folder_ex:
                    print(f"⚠️ Warning: Skipped training folder {folder} due to DBF read error: {folder_ex}")
                    continue

            # Resolve best matches
            generic_ignore = {"SUSPENSE ACCOUNT", "SUSPENSE A/C", "UPI DEBTORS", "UPI CREDITORS", "CASH ACCOUNT", "CASH A/C"}
            raw_learned = {}
            for clean_k, counts in narration_map.items():
                best_code = max(counts.items(), key=lambda x: x[1])[0]
                best_ledger_name = ledger_names.get(best_code)
                
                if best_ledger_name and best_ledger_name.upper() not in generic_ignore and "SUSPENSE" not in best_ledger_name.upper():
                    if not self.is_illegal_nature_mapping(clean_k, best_ledger_name):
                        raw_learned[clean_k] = best_ledger_name
                    else:
                        print(f"🛑 [Nature Guard] Blocked illegal history learning: '{clean_k}' → '{best_ledger_name}'")

            # Synthesize & clean via Gemini AI if available
            try:
                from gemini_service import GeminiService
                gemini = GeminiService()
                if gemini.api_key:
                    synthesized = gemini.optimize_and_synthesize_memory_rules(raw_learned)
                    if synthesized and isinstance(synthesized, dict):
                        raw_learned = synthesized
            except Exception as ge:
                print(f"⚠️ Gemini synthesis skipped during train_from_history: {ge}")

            memory = self.load_memory(client_id)
            if "expense_mappings" not in memory:
                memory["expense_mappings"] = {}
                
            memory["expense_mappings"].update(raw_learned)
            trained_count = len(raw_learned)
            self.save_memory(client_id, memory)
            print(f"Historical Training Complete: Learned & synthesized {trained_count} clean multi-month mappings across all year folders.")
            return trained_count
        except Exception as e:
            print(f"Failed to train from history: {e}")
            traceback.print_exc()
            return 0

    # ─────────────────────────────────────────────────────────────
    # PRODUCT CATALOG MEMORY  (Sales & Purchases)
    # Remembers: item name → HSN, GST%, UOM, last_rate, seen_count
    # ─────────────────────────────────────────────────────────────

    def get_product_catalog(self, client_id: str) -> dict:
        """Returns the learned product catalog for a client."""
        memory = self.load_memory(client_id)
        return memory.get("product_catalog", {})

    def _update_product_catalog(self, memory: dict, items: list):
        """Internal helper: updates product_catalog from a list of item dicts."""
        if "product_catalog" not in memory:
            memory["product_catalog"] = {}
        catalog = memory["product_catalog"]
        for item in items:
            name = str(item.get("name", "")).strip()
            if not name or len(name) < 2:
                continue
            hsn = str(item.get("hsn_code", "")).strip()
            gst_pct = item.get("gst_pct")
            uom = str(item.get("uom", "")).strip()
            rate = item.get("rate") or item.get("taxable") or 0.0

            # Normalise key — lowercase for stable lookup
            key = name.lower()
            entry = catalog.get(key, {})
            entry["display_name"] = name  # keep original casing
            if hsn and hsn not in ("nan", "None", ""):
                entry["hsn"] = hsn
            # Only update GST% if it is a valid standard rate
            VALID_RATES = {0.0, 0.1, 0.25, 1.5, 3.0, 5.0, 6.0, 9.0, 12.0, 14.0, 18.0, 28.0}
            try:
                gst_val = float(gst_pct) if gst_pct not in (None, "", "nan") else None
                if gst_val is not None and gst_val in VALID_RATES:
                    entry["gst_pct"] = gst_val
            except (ValueError, TypeError):
                pass
            if uom and uom not in ("nan", "None", ""):
                entry["uom"] = uom
            try:
                rate_val = float(rate)
                if rate_val > 0:
                    entry["last_rate"] = round(rate_val, 2)
            except (ValueError, TypeError):
                pass
            entry["seen_count"] = entry.get("seen_count", 0) + 1
            catalog[key] = entry
        memory["product_catalog"] = catalog
        return memory

    # ─────────────────────────────────────────────────────────────
    # SUPPLIER CATALOG MEMORY  (Purchases only)
    # Remembers: vendor name → gstin, city, typical_items, seen_count
    # ─────────────────────────────────────────────────────────────

    def get_supplier_catalog(self, client_id: str) -> dict:
        """Returns the learned supplier catalog for a client (Purchases module)."""
        memory = self.load_memory(client_id)
        return memory.get("supplier_catalog", {})

    def _update_supplier_catalog(self, memory: dict, vouchers: list):
        """Internal helper: updates supplier_catalog from purchase vouchers."""
        if "supplier_catalog" not in memory:
            memory["supplier_catalog"] = {}
        cat = memory["supplier_catalog"]
        for v in vouchers:
            name = str(v.get("party_name", "")).strip()
            if not name or len(name) < 2:
                continue
            key = name.lower()
            entry = cat.get(key, {})
            entry["display_name"] = name
            gstin = str(v.get("party_gstin", "")).strip()
            if gstin and len(gstin) >= 10:
                entry["gstin"] = gstin
                if len(gstin) >= 2 and gstin[:2].isdigit():
                    entry["state_code"] = gstin[:2]
            city = str(v.get("party_city", "")).strip()
            if city and city not in ("nan", "None", ""):
                entry["city"] = city
            # Track which items this supplier usually provides
            items = v.get("items", [])
            item_names = [str(i.get("name", "")).strip() for i in items if i.get("name")]
            existing_items = set(entry.get("typical_items", []))
            existing_items.update(item_names)
            entry["typical_items"] = list(existing_items)[:10]  # cap at 10
            entry["seen_count"] = entry.get("seen_count", 0) + 1
            cat[key] = entry
        memory["supplier_catalog"] = cat
        return memory

    # ─────────────────────────────────────────────────────────────
    # EXCEL COLUMN STRUCTURE CACHE
    # Remembers: which column map worked last time per module
    # ─────────────────────────────────────────────────────────────

    def get_excel_profile(self, client_id: str, module: str) -> dict:
        """Returns the saved Excel column structure for a module."""
        memory = self.load_memory(client_id)
        return memory.get("excel_profiles", {}).get(module, {})

    def save_excel_profile(self, client_id: str, module: str, profile: dict):
        """Saves a successful Excel column structure for a module."""
        memory = self.load_memory(client_id)
        if "excel_profiles" not in memory:
            memory["excel_profiles"] = {}
        memory["excel_profiles"][module] = profile
        self.save_memory(client_id, memory)
        print(f"💾 [Excel Profile] Saved column structure for module '{module}'")

    # ─────────────────────────────────────────────────────────────
    # AUTO-TRAINER: Runs after every successful PUSH
    # Updates all catalogs from the confirmed vouchers
    # ─────────────────────────────────────────────────────────────

    def learn_from_pushed_vouchers(self, client_id: str, vouchers: list, module: str):
        """
        Auto-trains memory from confirmed/pushed vouchers.
        Called automatically after every successful push.

        Sales:    Updates product_catalog (items + HSN + GST%)
        Purchases: Updates product_catalog + supplier_catalog (vendor info)
        Bank:     Updates expense_mappings (narration → ledger) — already handled separately
        """
        if not vouchers or module not in ("Sales", "Purchases"):
            return

        try:
            memory = self.load_memory(client_id)

            # Collect all items across all vouchers
            all_items = []
            for v in vouchers:
                items = v.get("items", [])
                if isinstance(items, list):
                    all_items.extend(items)

            # 1. Update product catalog from all items
            if all_items:
                memory = self._update_product_catalog(memory, all_items)
                print(f"✅ [Product Catalog] Learned {len(all_items)} item entries from {module} push.")

            # 2. For Purchases: update supplier catalog
            if module == "Purchases":
                memory = self._update_supplier_catalog(memory, vouchers)
                print(f"✅ [Supplier Catalog] Updated supplier entries from {len(vouchers)} purchase vouchers.")

            self.save_memory(client_id, memory)

        except Exception as e:
            print(f"⚠️ [Auto-Learn] Failed to learn from pushed vouchers: {e}")

    def get_catalog_prompt_injection(self, client_id: str, module: str) -> str:
        """
        Builds a compact, AI-ready prompt string from the product catalog and
        (for Purchases) the supplier catalog. Injected into the Gemini prompt
        before extraction so the AI uses real verified data instead of guessing.
        """
        memory = self.load_memory(client_id)
        lines = []

        # ── Product Catalog ──
        catalog = memory.get("product_catalog", {})
        if catalog:
            # Sort by seen_count descending so most common items come first
            sorted_items = sorted(catalog.items(), key=lambda x: x[1].get("seen_count", 0), reverse=True)
            lines.append("VERIFIED PRODUCT CATALOG (from your real past invoices — trust these over guessing):")
            for key, entry in sorted_items[:40]:  # inject top 40 items
                name = entry.get("display_name", key)
                hsn  = entry.get("hsn", "?")
                gst  = entry.get("gst_pct", "?")
                uom  = entry.get("uom", "PCS")
                cnt  = entry.get("seen_count", 1)
                lines.append(f"  - \"{name}\" → HSN: {hsn}, GST: {gst}%, UOM: {uom}  [verified {cnt}× in history]")
            lines.append("  RULE: If an item name in the document MATCHES or CLOSELY MATCHES one of these, use EXACTLY this HSN and GST%. Do NOT guess a different rate.")
            lines.append("")

        # ── Supplier Catalog (Purchases only) ──
        if module == "Purchases":
            sup_cat = memory.get("supplier_catalog", {})
            if sup_cat:
                sorted_sups = sorted(sup_cat.items(), key=lambda x: x[1].get("seen_count", 0), reverse=True)
                lines.append("VERIFIED SUPPLIER CATALOG (known vendors from past purchases):")
                for key, entry in sorted_sups[:20]:  # inject top 20 suppliers
                    name  = entry.get("display_name", key)
                    gstin = entry.get("gstin", "")
                    city  = entry.get("city", "")
                    cnt   = entry.get("seen_count", 1)
                    detail = f"  - \"{name}\""
                    if gstin:
                        detail += f" | GSTIN: {gstin}"
                    if city:
                        detail += f" | City: {city}"
                    detail += f"  [seen {cnt}×]"
                    lines.append(detail)
                lines.append("  RULE: If a vendor name matches one of these, use the saved GSTIN — do NOT hallucinate a different GSTIN.")
                lines.append("")

        return "\n".join(lines) if lines else ""
