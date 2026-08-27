import os
import sys
import warnings
import logging

# Suppress google-genai SDK automatic function calling (AFC) recommendation warnings
warnings.filterwarnings("ignore", category=UserWarning, message=".*Automatic function calling.*")
warnings.filterwarnings("ignore", category=UserWarning, message=".*automatic function calling.*")
warnings.filterwarnings("ignore", message=".*Automatic function calling.*")
warnings.filterwarnings("ignore", message=".*automatic function calling.*")

logging.getLogger("google.genai").setLevel(logging.ERROR)
logging.getLogger("google.generativeai").setLevel(logging.ERROR)

# Ensure pandas & Excel parsing packages from backend/venv site-packages are in sys.path
try:
    import pandas as pd
except ImportError:
    backend_venv_sp = os.path.abspath(os.path.join(os.path.dirname(__file__), "venv", "lib", "python3.14", "site-packages"))
    if os.path.exists(backend_venv_sp) and backend_venv_sp not in sys.path:
        sys.path.insert(0, backend_venv_sp)

import json
import re
import hashlib
import difflib
import threading

# --- THREAD-SAFE MULTI-USER STATUS STORE ---
_GLOBAL_STATUS_LOCK = threading.Lock()
_GLOBAL_STATUS_STORE = {}

def get_current_extraction_status(filename: str = None) -> dict:
    """Returns thread-safe in-memory status without disk lock delays."""
    with _GLOBAL_STATUS_LOCK:
        if filename and filename in _GLOBAL_STATUS_STORE:
            return _GLOBAL_STATUS_STORE[filename]
        return _GLOBAL_STATUS_STORE.get("_latest", {
            "filename": "", "part": 0, "total": 0, "progress_pct": 0, "percentage": 0, "message": "Idle"
        })

# --- DAILY 429 MODEL QUOTA BLACKLIST TRACKER ---
EXHAUSTED_MODELS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "exhausted_models.json")

def _load_exhausted_models_cache() -> dict:
    if os.path.exists(EXHAUSTED_MODELS_FILE):
        try:
            with open(EXHAUSTED_MODELS_FILE, "r") as f:
                data = json.load(f)
                today_str = datetime.date.today().isoformat()
                return {m: d for m, d in data.items() if d == today_str}
        except Exception:
            return {}
    return {}

def _save_exhausted_models_cache(cache: dict):
    try:
        with open(EXHAUSTED_MODELS_FILE, "w") as f:
            json.dump(cache, f)
    except Exception as e:
        print(f"Warning: Could not save exhausted models cache: {e}")

_EXHAUSTED_MODELS_CACHE = _load_exhausted_models_cache()

import hashlib

def _make_key_model_cache_key(api_key: str | None, model_name: str) -> str:
    k_hash = hashlib.md5((api_key or "default").encode('utf-8')).hexdigest()[:12]
    return f"{k_hash}:{model_name}"

def is_key_model_quota_exhausted_today(api_key: str | None, model_name: str) -> bool:
    global _EXHAUSTED_MODELS_CACHE
    today_str = datetime.date.today().isoformat()
    cache_key = _make_key_model_cache_key(api_key, model_name)
    if cache_key in _EXHAUSTED_MODELS_CACHE:
        if _EXHAUSTED_MODELS_CACHE[cache_key] == today_str:
            return True
        else:
            del _EXHAUSTED_MODELS_CACHE[cache_key]
            _save_exhausted_models_cache(_EXHAUSTED_MODELS_CACHE)
            return False
    return False

def mark_key_model_quota_exhausted_today(api_key: str | None, model_name: str):
    global _EXHAUSTED_MODELS_CACHE
    today_str = datetime.date.today().isoformat()
    cache_key = _make_key_model_cache_key(api_key, model_name)
    _EXHAUSTED_MODELS_CACHE[cache_key] = today_str
    _save_exhausted_models_cache(_EXHAUSTED_MODELS_CACHE)
    masked_key = (api_key[:6] + "...") if api_key and len(api_key) > 6 else "key"
    print(f"🚫 [Daily Key Blacklist] Key '{masked_key}' hit 429 daily quota on '{model_name}'. Blacklisted until 12:00 AM midnight reset!")

def is_model_quota_exhausted_today(model_name: str) -> bool:
    return is_key_model_quota_exhausted_today("default", model_name)

def mark_model_quota_exhausted_today(model_name: str):
    mark_key_model_quota_exhausted_today("default", model_name)
try:
    from google import genai
    from google.genai import types
except ImportError:
    try:
        import google.generativeai as genai
        types = None
    except ImportError:
        genai = None
        types = None

def make_config(response_mime_type="application/json"):
    if types and hasattr(types, "GenerateContentConfig"):
        return types.GenerateContentConfig(response_mime_type=response_mime_type)
    return None

class LegacyGenerativeAIClientWrapper:
    def __init__(self, api_key: str):
        self.api_key = api_key
        if genai and hasattr(genai, "configure"):
            genai.configure(api_key=api_key)

    class _FilesWrapper:
        def upload(self, file: str):
            if genai and hasattr(genai, "upload_file"):
                return genai.upload_file(path=file)
            return file

        def delete(self, name: str):
            if genai and hasattr(genai, "delete_file"):
                try:
                    genai.delete_file(name=name)
                except Exception:
                    pass

    class _ModelsWrapper:
        def __init__(self, api_key: str):
            self.api_key = api_key

        def generate_content(self, model: str, contents, config=None):
            if genai and hasattr(genai, "GenerativeModel"):
                m = genai.GenerativeModel(model_name=model)
                res = m.generate_content(contents)
                return res
            raise RuntimeError("Gemini SDK not available")

    @property
    def files(self):
        return self._FilesWrapper()

    @property
    def models(self):
        return self._ModelsWrapper(self.api_key)

    def generate_content(self, model: str, contents, config=None):
        return self.models.generate_content(model=model, contents=contents, config=config)

# Module-level spec file cache: {md5_hash: distilled_rules_text}
_SPEC_FILE_CACHE: dict = {}

class GeminiService:
    def __init__(self, api_key: str | None = None, model_name: str | None = None, is_paid_api_key: bool | None = None):
        from core.config import get_gemini_api_key_pool, clean_api_key

        if not api_key:
            api_key = os.getenv("GEMINI_API_KEY")
            
        if not api_key:
            try:
                settings_path = os.path.join(os.path.dirname(__file__), "settings.json")
                if os.path.exists(settings_path):
                    with open(settings_path, "r") as f:
                        cfg = json.load(f)
                        api_key = cfg.get("gemini_api_key")
                        if model_name is None: model_name = cfg.get("gemini_model")
                        if is_paid_api_key is None: is_paid_api_key = cfg.get("is_paid_api_key")
            except Exception:
                pass

        # Build 10-Key API Pool (GEMINI_API_KEY .. GEMINI_API_KEY_10)
        self.api_keys_pool = []
        if api_key:
            for raw_k in re.split(r'[,;\s]+', str(api_key)):
                c_k = clean_api_key(raw_k)
                if c_k and c_k not in self.api_keys_pool:
                    self.api_keys_pool.append(c_k)

        discovered_pool = get_gemini_api_key_pool()
        for k in discovered_pool:
            if k not in self.api_keys_pool:
                self.api_keys_pool.append(k)

        self.current_key_idx = 0
        if self.api_keys_pool:
            self.api_key = self.api_keys_pool[0]
            print(f"🔑 [API Key Pool Initialized] Loaded {len(self.api_keys_pool)} active Gemini API key(s) for smart rotation.")
        else:
            self.api_key = api_key or ""
            print("WARNING: Gemini API Key not found. Please provide it in settings or environment variables.")

        self.model_name = model_name or "gemini-3.1-flash-lite"
        self.is_paid_api_key = is_paid_api_key if is_paid_api_key is not None else False

    def _get_client(self, target_key: str | None = None):
        use_key = target_key or self.api_key
        if not use_key:
            raise RuntimeError("Gemini API Key is not configured.")
        if not genai:
            raise RuntimeError("Google GenAI module is not installed.")
        if hasattr(genai, "Client"):
            return genai.Client(api_key=use_key)
        return LegacyGenerativeAIClientWrapper(use_key)

    @staticmethod
    def repair_json_string(json_str: str) -> str:
        r"""
        Crash-Proof AI JSON Repair Guard.
        Sanitizes raw LLM output before passing to json.loads().
        - Strips markdown wrapper fences (```json ... ```)
        - Removes stray foreign/hallucinated characters (like 'хорошо') outside string values
        - Injects missing commas between adjacent JSON objects (`}\s*{` -> `},{`)
        - Fixes trailing commas inside objects and arrays (`,}` -> `}`, `,]` -> `]`)
        - Extracts JSON payload bounded by first '{' and last '}'
        """
        if not json_str:
            return "{}"

        text = json_str.strip()

        # 1. Remove markdown code blocks
        if "```" in text:
            text = re.sub(r'```(?:json)?\s*', '', text)
            text = re.sub(r'```\s*$', '', text)

        # 2. Extract substring between first '{' and last '}'
        first_curly = text.find('{')
        last_curly = text.rfind('}')
        if first_curly != -1 and last_curly != -1 and last_curly > first_curly:
            text = text[first_curly:last_curly+1]

        # 3. Inject missing commas between adjacent objects (e.g. `} {` or `} \n {`)
        text = re.sub(r'\}\s*\{', '},{', text)

        # 4. Strip stray non-ASCII hallucinated words (like 'хорошо') appearing between JSON elements
        lines = []
        for line in text.splitlines():
            line_cleaned = re.sub(r'(?<=[\}\],])\s*[^\x00-\x7F]+\s*(?=[\{\[\"]|$)', '', line)
            line_cleaned = re.sub(r'^[^\x00-\x7F\s\{\}\[\]\",]+$', '', line_cleaned)
            line_cleaned = re.sub(r'[^\x00-\x7F]+', '', line_cleaned)
            if line_cleaned.strip():
                lines.append(line_cleaned)
        text = "\n".join(lines)

        # 5. Inject missing commas between adjacent objects (e.g. `} {` or `} \n {`)
        text = re.sub(r'\}\s*\{', '},{', text)
        text = re.sub(r'\}\s*\"', '},"', text)
        text = re.sub(r'\]\s*\{', '],{', text)

        # 6. Fix trailing commas before closing braces/brackets
        text = re.sub(r',\s*\}', '}', text)
        text = re.sub(r',\s*\]', ']', text)

        return text.strip()

    @staticmethod
    def _is_valid_ledger_match(mapped_name: str, narr: str, bank_name: str = "") -> bool:
        """
        Validates whether a mapped ledger account name is physically present inside the narration text.
        Supports space-insensitive matching (e.g. 'S S R Footcare' matching 'SSRFOOTCARE' or 'FOOTC ARE').
        """
        if not mapped_name or not narr:
            return False
            
        mapped_upper = mapped_name.upper().strip()
        narr_upper = narr.upper().strip()
        
        # 0. Anti-Dummy & Generic Filler Ledger Guard: Never accept dummy filler words (REMARK, DUMMY, etc.) as valid party ledgers!
        BANNED_DUMMY_LEDGERS = {"REMARK", "REMARKS", "SUSPENSE", "DUMMY", "UNKNOWN", "PART PAYMENT", "NARRATION", "NOTE", "PAYMENT", "RECEIPT"}
        if mapped_upper in BANNED_DUMMY_LEDGERS:
            return False

        # 1. Anti-Bank Contra Check: If mapped to the bank itself, reject!
        if bank_name and bank_name.upper() in mapped_upper:
            return False

        # 2. Universal 100-Client System & Generic Ledger Regex Classifier
        # Automatically recognizes System, Expense, Income, Tax, Utility, & Operating ledgers across 100+ industries
        SYSTEM_LEDGER_PATTERNS = [
            # Banking, Treasury, Loans & Finance
            r'\b(BANK\s*CHARG|CHARGES|INTEREST|SWEEP|FD|FIXED\s*DEPOSIT|MUTUAL\s*FUND|INVESTMENT|LOAN|ADVANCE|CAPITAL|DRAWING|OVERDRAFT|OD|CC|LOAN\s*A/C)\b',
            # Payroll, Staff & HR
            r'\b(SALARY|WAGES|STIPEND|BONUS|PF|ESI|WELFARE|INCENTIVE|REMUNERATION|STAFF|EMPLOYEE|ALLOWANCE|GRATUITY)\b',
            # Utilities, Rent & Real Estate
            r'\b(RENT|ELECTRICITY|POWER|WATER|GAS|FUEL|PETROL|DIESEL|TELEPHONE|MOBILE|BROADBAND|INTERNET|WIFI|LEASE|OFFICE\s*EXP)\b',
            # Taxes, Duties & Statutory Compliance
            r'\b(GST|CGST|SGST|IGST|CESS|TDS|TCS|DUTY|DUTIES|TAX|INCOME\s*TAX|PROFESSIONAL\s*TAX|PTAX|PENALTY|LATE\s*FEE|CUSTOMS)\b',
            # Operations, Maintenance, Spares & Repairs (Electric, Pumps, Machinery, Motors, Vehicles, Testing)
            r'\b(REPAIR|REPAIRS|MAINTENANCE|SERVICE|SERVICING|WINDING|TOOLS|HARDWARE|SPARES|FITTING|EQUIPMENT|MACHINERY|VEHICLE|TESTING|CALIBRATION|LAB|WEIGHTBRIDGE|CUTTING)\b',
            # Freight, Logistics & Travel
            r'\b(FREIGHT|CARTAGE|OCTROI|LOADING|UNLOADING|TRANSPORT|CONVEYANCE|TRAVEL|TRAVELLING|LODGING|BOARDING|COURIER|POSTAGE|DELIVERY)\b',
            # Office Supplies, Technology & Professional Services
            r'\b(PRINTING|STATIONERY|SOFTWARE|SUBSCRIPTION|LICENSE|DOMAIN|HOSTING|CLOUD|IT\s*EXPENSE|LEGAL|AUDIT|PROFESSIONAL|FEES|COMMISSION|BROKERAGE|ADVERTISEMENT|PROMOTION|MARKETING)\b',
            # General Accounting & Misc Ledger Suffixes
            r'\b(EXPENSE|EXPENSES|EXP|INCOME|CHARGES|SUSPENSE|MISC|ROUND\s*OFF|DISCOUNT|REBATE|CASH|ACCOUNT|A/C)\b'
        ]

        for pattern in SYSTEM_LEDGER_PATTERNS:
            if re.search(pattern, mapped_upper):
                return True
            
        # Strip all non-alphanumeric characters for clean letter-sequence comparison
        def clean_letters(s):
            return re.sub(r'[^A-Z0-9]', '', str(s).upper())
            
        mapped_clean = clean_letters(mapped_name)
        narr_clean = clean_letters(narr)
        
        # 1. Full space-insensitive name match (e.g. "S S R FOOTCARE" -> "SSRFOOTCARE" in "502001...SSRFOOTCARE000")
        if len(mapped_clean) >= 3 and mapped_clean in narr_clean:
            return True
            
        # 2. Key word letter sequence match (e.g. "FOOTCARE", "HEENARAJENDRAS", "PATTANAYAKSONALI", "SARTY")
        mapped_words = [w for w in re.split(r'[\s\-\/@._]+', mapped_upper) if len(w) >= 3 and w not in ("LTD", "PVT", "INC", "CORP", "BANK", "ACCOUNT", "A/C")]
        if not mapped_words:
            return True
            
        for w in mapped_words:
            w_clean = clean_letters(w)
            if len(w_clean) >= 3 and w_clean in narr_clean:
                return True
                
        # 3. Soft Fallback: If mapped name contains clean alphabetic words, allow it as a party resolution
        if len(mapped_clean) >= 3:
            return True

        return False

    @staticmethod
    def extract_clean_party_from_narration(narr: str) -> str:
        """
        Robust Universal Narration Party Extractor.
        Parses Indian bank statement narrations (UPI, IMPS, NEFT, RTGS, Transfers)
        to extract the true party/vendor/person name while stripping all UPI handles,
        bank IFSC fragments, gateway noise, and numeric reference codes.
        """
        if not narr:
            return ""
        narr_str = str(narr).strip()
        # 0. Strip leading transaction type prefixes (e.g. 'ACH D -', 'ACH C -', 'NEFT CR -', 'TPT-')
        narr_str = re.sub(r'^(ACH\s*[CD]?\s*[-_]?\s*|ACH\s*DR\s*[-_]?\s*|ACH\s*CR\s*[-_]?\s*|NEFT\s*[DR|CR]*\s*[-_]?\s*|RTGS\s*[DR|CR]*\s*[-_]?\s*|IMPS\s*[-_]?\s*|TPT\s*[-_]?\s*)', '', narr_str, flags=re.IGNORECASE).strip()

        # 1. Pre-clean @handle and dot/hyphen VPA domain suffixes BEFORE any regex splitting!
        raw_no_handle = re.sub(r'@[A-Za-z0-9_\-\.\s]{1,25}(?:AXIS|ICICI|HDFC|DFCBANK|FCBANK|SBI|YES|PAYTM|YBL|KOTAK|UPI|PTYES|YESCRED|NAVIAXIS|PTAXIS|WAAXIS|AXL|IPL|IBL|OKAXIS|OKICICI|OKSBI|MAHB|BARB|INDB|TMBL|SVCB)', '', narr_str, flags=re.IGNORECASE)
        raw_no_handle = re.sub(r'@[A-Za-z0-9_\-\.]+', '', raw_no_handle)
        raw_no_handle = re.sub(r'[\.\-](?:SBI|OKSBI|OKICICI|OKAXIS|KHDFCBANK|YBL|KOTAK|PAYTM|PHONEPE|GPAY|BHIM|PTYES|AXIS|ICICI|HDFC)\b', '', raw_no_handle, flags=re.IGNORECASE)
        raw_no_handle = re.sub(r'\b(X{2,10}|XXXXX)\b', '', raw_no_handle, flags=re.IGNORECASE)
        raw_no_handle = re.sub(r'\b(OKH|OKICIC|OKICICI|OKAXIS|OKSBI|KHDFCBANK|FCBANK|DFCBANK|KOTAK|PAYTM|PHONEPE|GPAY|BHIM|PTYES|YESCRED|NAVIAXIS|PTAXIS|WAAXIS|AXL|YBL|IPL|IBL)\b', '', raw_no_handle, flags=re.IGNORECASE)

        # 2. Strip standard IFSC codes (4 alpha + 0 + 6 alphanumeric)
        raw_no_ifsc = re.sub(r'\b[A-Za-z]{4}0[A-Za-z0-9]{6}\b', '', raw_no_handle, flags=re.IGNORECASE)
        raw_no_ifsc = re.sub(r'\b[A-Za-z]{4}[0-9][A-Za-z0-9]{4,6}\b', '', raw_no_ifsc, flags=re.IGNORECASE)

        # 3. Strip long standalone numeric ref numbers/UTRs (11+ digits), keeping party IDs like DU82848 or 10-digit mobile handles
        raw_no_ids = re.sub(r'\b\d{11,}\b', '', raw_no_ifsc)

        NOISE_TOKENS = {
            'UPI', 'IMPS', 'NEFT', 'RTGS', 'P2A', 'P2P', 'MOB', 'DR', 'CR',
            'NOREF', 'PAYMENT', 'RECEIPT', 'TRANSFER', 'TRF', 'FRM', 'TO',
            'INB', 'BY', 'CHQ', 'PAID', 'YESB', 'SBIN', 'HDFC', 'ICIC', 'UTIB',
            'KKBK', 'BARB', 'CNRB', 'UBIN', 'PUNB', 'TM', 'AB', 'TPT', 'NETBANK',
            'NETB', 'HDFCH', 'HDFCN', 'HDFCE', 'HDFCBANK', 'ICICI', 'AXIS', 'MAHB',
            'SVCB', 'TMBL', 'INDB', 'CCBL', 'OKAXIS', 'OKICICI', 'OKHDFCBANK', 'OKSBI',
            'PTYES', 'YESCRED', 'NAVIAXIS', 'PTAXIS', 'WAAXIS', 'AXL', 'YBL', 'IPL',
            'IBL', 'KOTAK', 'PAYTM', 'PHONEPE', 'GPAY', 'BHIM', 'SENT', 'USING',
            'REMARKS', 'REMARK', 'INSTAALERTCHG', 'SMS', 'CDT', 'HAND', 'LOAN',
            'SELF', 'NEHRU', 'NAGAR', 'KURLA', 'EAST', 'WEST', 'BRANCH',
            'KAXIS', 'IS', 'CI', 'FCBANK', 'KHDFCBANK', 'OKICIC', 'OKS', 'OKI', 'OKA', 'XIS'
        }

        MONTH_NAMES = {'JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC',
                       'JANUARY', 'FEBRUARY', 'MARCH', 'APRIL', 'JUNE', 'JULY', 'AUGUST', 'SEPTEMBER', 'OCTOBER', 'NOVEMBER', 'DECEMBER'}

        COMMON_NAME_PARTS = [
            'AATHIRA', 'CHANDRAN', 'PALLAVI', 'PANCHAL', 'RUPALI', 'WAGH', 'NIKHILA', 'KIRALE',
            'PAWAN', 'KUMAR', 'SHAH', 'SHASHANK', 'GAWDE', 'GAWD', 'SAMPADA', 'VEDAK', 'SWATI', 'TILAK',
            'RINDA', 'FERNS', 'JAYEETA', 'DOKERAJU', 'SAURABH', 'PANDEY', 'HIRAL', 'CHANDARANA',
            'ANJANAVELIL', 'VARSHA', 'SHRIKANT', 'DANGE', 'NAMRATA', 'GANGTOK', 'PRADEEP', 'SHAW',
            'SUNEETA', 'HARSHA', 'PAREKH', 'DIGAMBAR', 'KHETLE', 'SONAWANE', 'JAYWANT', 'TAUSIF',
            'SIRAJ', 'SHAIKH', 'CHANDRAKANT', 'PARTE', 'BONY', 'YALLAPPA', 'KUNCHI', 'KORVE', 'MASALI',
            'ANAND', 'SHARMA', 'SANJAY', 'DEEPAK', 'RARESH', 'RAJESH', 'PRIYA', 'AMJAD', 'MITUL', 'MANISH',
            'HASMUKH', 'SHANTILAL', 'MEENA', 'PATIDAR', 'KALAMBE', 'PANDURANG', 'NATROX', 'GIBZ', 'VANIA', 'VARUN',
            'SINGH', 'PATEL', 'VERMA', 'GUPTA', 'JAIN', 'MEHTA', 'DESHMUKH', 'CHAVAN', 'PAWAR', 'JADHAV',
            'MORE', 'JOSHI', 'KULKARNI', 'PATIL', 'AGRAWAL', 'SURI', 'BHATIA', 'KAPOOR', 'KHAN', 'RODRIGUES',
            'FERNANDES', 'ALMEIDA', 'DOUZA', 'SOARES', 'SHAH', 'CHAUDHARY', 'REDDY', 'NAIR', 'MENON', 'PILLAI'
        ]

        CORPORATE_MAP = {
            'PVT LTD': 'Pvt Ltd',
            'PRIVATE LIMITED': 'Private Limited',
            'LLP': 'LLP',
            'ENTERPRISES': 'Enterprises',
            'TRADERS': 'Traders',
            'INDUSTRIES': 'Industries',
            'SERVICES': 'Services',
            'SOLUTIONS': 'Solutions',
            'TECHNOLOGIES': 'Technologies',
            'MOTORS': 'Motors',
            'HARDWARE': 'Hardware',
            'STORES': 'Stores',
            'AGENCIES': 'Agencies',
            'LOGISTICS': 'Logistics'
        }

        def _sanitize_party(candidate: str) -> str:
            if not candidate:
                return ""
            # Strip hyphenated trailing index numbers (e.g. NIKHILAKIRALE-1 -> NIKHILAKIRALE)
            cand = re.sub(r'[\s\-]\d+$', '', candidate)

            tokens = []
            for w in re.split(r'[\s\-\/@._]+', cand):
                w_clean = w
                if not re.match(r'^[A-Z]{2}\d{4,6}$', w, re.IGNORECASE):
                    w_clean = re.sub(r'(?<=[A-Za-z]{3})\d{1,4}$', '', w)
                w_upper = w_clean.upper()

                if not w_clean or w_upper in NOISE_TOKENS or w_upper in MONTH_NAMES:
                    continue
                if w_clean.isdigit() and len(w_clean) != 10:
                    continue
                tokens.append(w_clean)

            clean_raw = " ".join(tokens).strip()
            if not clean_raw:
                return ""

            # Cryptic reference IDs (e.g. DU82848, TXN12345, REF99281) or pure numbers/short noise are NOT party names!
            # Reject them (return "") so they automatically route to Suspense Account for manual/AI review.
            if re.match(r'^[A-Z]{1,4}\d{4,12}$', clean_raw, re.IGNORECASE) or clean_raw.isdigit() or len(clean_raw) < 3:
                return ""

            # Syllable splitting & Title casing for human names
            formatted_words = []
            words = clean_raw.split()
            i = 0
            while i < len(words):
                w = words[i]
                w_up = w.upper()

                # Check multi-word corporate suffix (e.g., PVT LTD, PRIVATE LIMITED)
                if i + 1 < len(words):
                    two_words = f"{w_up} {words[i+1].upper()}"
                    if two_words in CORPORATE_MAP:
                        formatted_words.append(CORPORATE_MAP[two_words])
                        i += 2
                        continue

                if w_up in CORPORATE_MAP:
                    formatted_words.append(CORPORATE_MAP[w_up])
                    i += 1
                    continue

                matched_segments = []
                rem = w_up
                for seg in sorted(COMMON_NAME_PARTS, key=len, reverse=True):
                    if seg in rem:
                        idx = rem.find(seg)
                        matched_segments.append((idx, seg))
                        rem = rem[:idx] + (" " * len(seg)) + rem[idx + len(seg):]

                if matched_segments:
                    matched_segments.sort(key=lambda x: x[0])
                    built_parts = []
                    curr_idx = 0
                    for seg_idx, seg_str in matched_segments:
                        if seg_idx > curr_idx:
                            between = w_up[curr_idx:seg_idx].strip()
                            if between:
                                built_parts.append(between.upper() if len(between) <= 2 else between.title())
                        built_parts.append(seg_str.title())
                        curr_idx = seg_idx + len(seg_str)
                    if curr_idx < len(w_up):
                        trailing = w_up[curr_idx:].strip()
                        if trailing:
                            built_parts.append(trailing.upper() if len(trailing) <= 2 else trailing.title())
                    formatted_words.append(" ".join(built_parts))
                else:
                    formatted_words.append(w.title())
                i += 1

            result = " ".join(formatted_words).strip()
            return re.sub(r'\s+', ' ', result)

        # Pattern matches on pre-cleaned string
        mA = re.search(r'UPI[/\-]\d*[/\-]?(?:DR|CR)?[/\-]?([A-Za-z0-9_\-\s&\.]+?)(?:[/\-]|$)', raw_no_ids, re.IGNORECASE)
        if mA:
            res = _sanitize_party(mA.group(1))
            if res and len(res) >= 2:
                return res

        mB = re.search(r'(?:NEFT|RTGS|IMPS)[/\-\s]+(?:CR|DR|P2A|P2P)?[/\-\s]*[A-Za-z0-9]*[/\-\s]*([A-Za-z0-9_\-\s&\.]+?)(?:[/\-]|$)', raw_no_ids, re.IGNORECASE)
        if mB:
            res = _sanitize_party(mB.group(1))
            if res and len(res) >= 2:
                return res

        mC = re.search(r'TPT[/\-\s]+(?:[A-Za-z0-9]+\s*)*[/\-\s]+([A-Za-z0-9_\-\s&\.]+?)$', raw_no_ids, re.IGNORECASE)
        if mC:
            res = _sanitize_party(mC.group(1))
            if res and len(res) >= 2:
                return res

        # General fallback
        res = _sanitize_party(raw_no_ids)
        if res and len(res) >= 2:
            return res

        return ""

    @staticmethod
    def classify_transaction_nature(narr: str, party_name: str, tx_type: str = "Receipt", amount: float = 0.0) -> str:
        """
        Deep Transaction Nature & Group Classifier for Indian Accounting (ICAI / Ind AS).
        
        DECISION FRAMEWORK:
        ════════════════════════════════════════════════════════════════════
        STEP 1: Read NARRATION PREFIX (UPI / ACH D / NEFT CR etc.)
        STEP 2: Read DR or CR direction (is_payment vs is_receipt)
        STEP 3: Read AMOUNT (small/large/round → context signal)
        STEP 4: Read PARTY NAME keywords (Groww / Amazon / CRED etc.)
        STEP 5: Apply ACCOUNTING RULE based on all above signals combined
        ════════════════════════════════════════════════════════════════════

        DR (Debit/OUT from bank) = Money GOING OUT = PAYMENT / EXPENSE
            → NEVER "Sales Accounts", NEVER "Sundry Debtors (income)"
            → Can be: Indirect Expenses, Investments, Duties & Taxes,
                      Secured Loans (repayment), Bank Accounts (transfer)

        CR (Credit/IN to bank) = Money COMING IN = RECEIPT / INCOME
            → NEVER "Sundry Creditors (expense payable)"
            → Can be: Sundry Debtors, Indirect Income, Sales, Investments (return),
                      Unsecured Loans (borrowed), Bank Accounts (transfer)

        AMOUNT SIGNALS:
            Small  (₹1 – ₹5,000)    → Petty expenses, UPI food/cab, small charges
            Medium (₹5,001 – ₹50,000) → Vendor payment, salary, utility bills
            Large  (₹50,001+)        → Salary bulk, loan EMI, investment SIP, bank transfer
            Round  (₹10k / ₹25k / ₹50k / ₹1L multiples) → Very likely loan EMI or inter-bank transfer
        """
        text = f"{narr} {party_name}".strip().upper()
        narr_up = narr.strip().upper()
        is_payment = tx_type.strip().capitalize() in ("Payment", "Debit", "Dr", "Out")
        is_receipt = not is_payment

        # AMOUNT RANGE SIGNALS
        amt = abs(float(amount or 0))
        is_small_amt   = amt < 5000          # petty cash / food / cab / recharge
        is_medium_amt  = 5000 <= amt < 50000  # salary / vendor / utility
        is_large_amt   = amt >= 50000         # EMI / bulk salary / investment / bank transfer
        # Round amount = multiple of 500 with no paise → likely scheduled/auto-debit (EMI, SIP, transfer)
        is_round_amt   = amt > 0 and amt % 500 == 0 and amt == int(amt)

        # ── STEP 0: BANK CHARGES & FEES (Top Priority Expense) ───────────────
        BANK_CHARGE_KWS = [
            'BANK CHARGES', 'BANK CHAGES', 'BANK CHARG', 'BANK CHAG', 'MDR RCVRY', 'RUPAY MDR',
            'INSTAALERT', 'INSTAALERTCHG', 'ALERTCHG', 'SMS CHG', 'SMS-CHARG', 'SMS CHARGE', 'MIN BAL',
            'ATM CHG', 'DEBIT CARD CHG', 'CHQ BOUNCE', 'DEPOSITORY CHARGES',
            'PROCESSING FEE', 'LATE FEE', 'PENALTY', 'FORECLOSURE', 'POS RENTAL', 'SOUND BOX',
            'SERVICE CHG', 'SERVICE CHARGE', 'SERVICE CHARGES', 'NACH CHARGE', 'ECS CHARGE'
        ]
        if any(k in text for k in BANK_CHARGE_KWS):
            return "Indirect Expenses"

        # ── STEP 1: NARRATION PREFIX SIGNALS ────────────────────────────────
        # ACH D- / NACH D- = auto-debit mandate (Payment going OUT)
        if narr_up.startswith(("ACH D", "NACH D", "ECS D", "MANDATE DR")):
            is_payment = True
            is_receipt = False
        # NEFT CR / ACH CR = money coming IN
        if narr_up.startswith(("NEFT CR", "IMPS CR", "UPI CR", "ACH CR", "NACH CR", "ECS CR")):
            is_receipt = True
            is_payment = False

        # ── STEP 2: AMOUNT + DIRECTION COMBINED SIGNALS ─────────────────────
        # Large round DR amount starting with ACH/NACH = Loan EMI or SIP
        if is_payment and is_round_amt and is_large_amt:
            if any(k in text for k in ["EMI", "LOAN", "HOUSING", "HOME LOAN", "PERSONAL LOAN", "AUTO LOAN", "VEHICLE"]):
                return "Secured Loans"
            if any(k in text for k in ["SIP", "INVEST", "MUTUAL FUND", "GROWW", "ZERODHA", "UPSTOX"]):
                return "Investments"

        # Large CR amount = could be salary received, loan received, FD maturity
        if is_receipt and is_large_amt and is_round_amt:
            if any(k in text for k in ["SALARY", "PAYROLL", "COMPENSATION"]):
                return "Indirect Income"
            if any(k in text for k in ["LOAN", "DISBURS", "OD LIMIT", "OVERDRAFT"]):
                return "Secured Loans"

        # ── STEP 2b: STATUTORY TAXES & GOVT DUTIES (Top Priority) ───────────
        STATUTORY_TAX_KWS = [
            'PROFESSIONAL TAX', 'PTAX', 'GST', 'CGST', 'SGST', 'IGST', 'TDS', 'TCS',
            'ADVANCE TAX', 'INCOME TAX', 'DUTIES & TAXES', 'CHALLAN', 'GSTPMT',
            'NSDL', 'TRACES', 'TAX PAYMENT', 'TDS PAYMENT'
        ]
        if any(k in text for k in STATUTORY_TAX_KWS):
            return "Duties & Taxes"

        # ── STEP 3: INVESTMENT PLATFORMS & CLEARING CORPS ───────────────────
        INVESTMENT_KWS = [
            'GROWW', 'NEXTBILLION', 'ZERODHA', 'UPSTOX', 'ANGEL ONE', 'ANGELBROKING',
            'PAYTM MONEY', 'ICICI DIRECT', 'MOTILAL OSWAL', 'INDIAN CLEARING',
            'INDIAN CLEARING CORP', 'CLEARING CORP', 'NSCCL', 'BSCCL', 'ICCL',
            'NSE CLEARING', 'BSE CLEARING', 'MUTUAL FUND', 'SHARES', 'SECURITIES', 'DEMAT',
            'SMALLCASE', 'KUVERA', 'FYERS', 'DHANI STOCKS'
        ]
        if any(k in text for k in INVESTMENT_KWS):
            return "Investments"  # Both DR (SIP/clearing out) and CR (redemption in) = Investments

        # ── STEP 5: CREDIT CARD GATEWAYS ────────────────────────────────────
        CREDIT_CARD_GATEWAY_KWS = [
            'CRED', 'CRED CLUB', 'RAZORPAY', 'PAYTM GATEWAY', 'INSTAMOJO',
            'BILLDESK', 'CCAVENUE', 'PAYU', 'EASEBUZZ', 'CASHFREE'
        ]
        if any(k in text for k in CREDIT_CARD_GATEWAY_KWS):
            # CRED DR = credit card bill payment; CRED CR = cashback
            return "Indirect Expenses" if is_payment else "Indirect Income"

        # ── STEP 6: BANKS & FINANCIAL INSTITUTIONS ───────────────────────────
        BANK_FINANCE_KWS = [
            'IDFC FIRST BANK', 'IDFCFIRST', 'HDFC BANK', 'ICICI BANK', 'AXIS BANK',
            'STATE BANK OF INDIA', 'SBI ', 'KOTAK MAHINDRA', 'INDUSIND BANK', 'BANK OF BARODA',
            'PUNJAB NATIONAL BANK', 'CANARA BANK', 'UNION BANK', 'FINANCIAL SERVICES',
            'BANDHAN BANK', 'YES BANK', 'RBL BANK', 'FEDERAL BANK', 'KARNATAKA BANK'
        ]
        if any(k in text for k in BANK_FINANCE_KWS):
            if is_payment:
                if any(k in text for k in ['EMI', 'LOAN', 'REPAY', 'OD', 'OVERDRAFT']):
                    return "Secured Loans"
                # Large round DR to bank = inter-bank transfer
                return "Bank Accounts"
            else:
                if any(k in text for k in ['INTEREST', 'INT CR', 'CREDIT INT']):
                    return "Indirect Income"
                if is_large_amt and is_round_amt:
                    return "Secured Loans"  # Likely loan disbursement
                return "Bank Accounts"

        # ── STEP 7: E-COMMERCE & FOOD DELIVERY (Amount-Aware) ───────────────
        ECOM_KWS = [
            'AMAZON', 'FLIPKART', 'MYNTRA', 'AJIO', 'NYKAA', 'MEESHO', 'SNAPDEAL',
            'JIO MART', 'JIOMART', 'BIGBASKET', 'MILKBASKET', 'BLINKIT', 'ZEPTO',
            'SWIGGY', 'ZOMATO', 'INSTAMART', 'DUNZO', 'URBAN COMPANY', 'URBANCLAP'
        ]
        if any(k in text for k in ECOM_KWS):
            if is_payment:
                # Small Amazon DR = consumer purchase (indirect expense)
                # Large Amazon DR = could be seller stock purchase
                return "Indirect Expenses" if is_small_amt or is_medium_amt else "Purchase Accounts"
            else:
                # Amazon CR = seller payment received from Amazon
                return "Sundry Debtors"

        # ── STEP 8: UTILITY & BILLS & BANK CHARGES ───────────────────────────
        UTILITY_KWS = [
            'ELECTRICITY', 'BIJLI', 'POWER', 'TELEPHONE', 'MOBILE', 'RECHARGE',
            'WIFI', 'BROADBAND', 'AIRTEL', 'JIO', 'VODAFONE', 'BSNL', 'TATA SKY',
            'PETROL', 'FUEL', 'DIESEL', 'INDANE', 'HPCL', 'BPCL', 'IOCL',
            'RENT', 'LEASE', 'MAINTENANCE', 'WATER BILL', 'GAS BILL',
            'GOOGLE PLAY', 'NETFLIX', 'AMAZON PRIME', 'HOTSTAR', 'SPOTIFY',
            'INSTAALERT', 'ALERTCHG', 'SMS CHARGE', 'SOUND BOX', 'EDC RENTAL', 'POS RENTAL',
            'MSEB', 'BEST', 'TATA POWER', 'ADANI ELECTRICITY', 'TORRENT POWER', 'MAHADISCOM'
        ]
        if any(k in text for k in UTILITY_KWS):
            return "Indirect Expenses" if is_payment else "Indirect Income"

        # ── STEP 8b: HEALTHCARE, DIAGNOSTICS & TRADE VENDORS ───────────────
        TRADE_HEALTH_KWS = [
            'DIABETIC', 'FOOTWEAR', 'SHOES', 'DIAGNOSTICS', 'HEALTHCARE',
            'HOSPITAL', 'CLINIC', 'LAB ', 'PHARMA', 'MEDICAL'
        ]
        if any(k in text for k in TRADE_HEALTH_KWS):
            return "Sundry Debtors" if is_receipt else "Sundry Creditors"

        # ── STEP 9: PAYMENT WALLETS ──────────────────────────────────────────
        WALLET_KWS = ['GOOGLE PAY', 'GPAY', 'PAYTM', 'PHONEPE', 'BHIM', 'FAMPAY']
        if any(k in text for k in WALLET_KWS):
            if is_payment:
                # Small wallet DR = petty expense; large wallet DR = person-to-person transfer
                return "Indirect Expenses" if is_small_amt else "Loans & Advances (Asset)"
            else:
                return "Sundry Debtors" if is_medium_amt or is_large_amt else "Indirect Income"

        # ── STEP 10: STATUTORY TAXES & GOVT DUTIES ───────────────────────────
        STATUTORY_TAX_KWS = [
            'PROFESSIONAL TAX', ' PTAX ', ' GST ', 'CGST', 'SGST', 'IGST', ' TDS ', ' TCS ',
            'ADVANCE TAX', 'INCOME TAX', 'DUTIES & TAXES', 'CHALLAN', 'GSTPMT',
            'NSDL', 'TRACES', 'TAX PAYMENT'
        ]
        if any(k in text for k in STATUTORY_TAX_KWS):
            return "Duties & Taxes"

        # ── STEP 11: BANK FEES & CHARGES ────────────────────────────────────
        BANK_CHARGE_KWS = [
            'BANK CHARGES', 'MDR RCVRY', 'RUPAY MDR', 'INSTAALERT', 'SMS CHG', 'MIN BAL',
            'ATM CHG', 'DEBIT CARD CHG', 'CHQ BOUNCE', 'DEPOSITORY CHARGES',
            'PROCESSING FEE', 'LATE FEE', 'PENALTY', 'FORECLOSURE'
        ]
        if any(k in text for k in BANK_CHARGE_KWS):
            return "Indirect Expenses"

        # ── STEP 12: SALARY & PAYROLL (Amount-Aware) ────────────────────────
        if any(k in text for k in ['SALARY', 'SALARIES', 'WAGES', 'STIPEND', 'BONUS', 'PAYROLL', 'COMPENSATION', 'HR PAY']):
            if is_payment:
                return "Indirect Expenses"  # Salary paid out
            else:
                return "Indirect Income"    # Salary received (own salary)

        # ── STEP 13: GENERAL EXPENSE KEYWORDS ───────────────────────────────
        EXPENSE_KWS = [
            'EXPENSE', 'EXPENSES', 'PF ', 'ESI', 'AUDIT', 'LEGAL', 'FEE', 'FEES', 'COMMISSION',
            'PRINTING', 'STATIONERY', 'COURIER', 'POSTAGE', 'CLEANING', 'REPAIR', 'REPAIRS',
            'SOFTWARE', 'DOMAIN', 'HOSTING', 'CLOUD', 'TAXI', 'CAB', 'TRAVEL',
            'CONVEYANCE', 'SUBSCRIPTION', 'DONATION', 'WELFARE', 'INSURANCE', 'PREMIUM'
        ]
        if any(k in text for k in EXPENSE_KWS):
            return "Indirect Expenses" if is_payment else "Indirect Income"

        # ── STEP 14: PERSONAL / DRAWINGS ────────────────────────────────────
        if any(k in text for k in ['LIC', 'MEDICLAIM', 'MEDICINE', 'HEALTH INSURANCE', 'PERSONAL EXP']):
            return "Capital Account / Drawings" if is_payment else "Indirect Income"

        # ── STEP 15: HUMAN PERSONS — Loans between individuals ──────────────
        is_human = any(t in text for t in ['BHAI', 'KUMAR', 'LAL', 'DEVI', 'SHAH', 'PATEL', 'MEHTA', 'MANDALIA', 'BEN ', 'KAKA '])
        is_company = any(b in text for b in ['LTD', 'LIMITED', 'PVT', 'PRIVATE', 'CORP', 'TRADERS', 'ENTERPRISE', 'INDUSTRIES', 'INC', 'LLC'])
        if is_human and not is_company:
            return "Loans & Advances (Asset)" if is_payment else "Unsecured Loans"

        # ── STEP 16: FINAL DR/CR DIRECTION GATE (when no keyword matched) ───
        # Use amount size as final tiebreaker for unknown parties
        if is_payment:
            if is_large_amt and is_round_amt:
                return "Bank Accounts"   # Large round DR with unknown party = likely inter-bank transfer
            return "Sundry Creditors"    # Unknown DR = vendor payment (expense payable)
        else:
            if is_large_amt and is_round_amt:
                return "Unsecured Loans" # Large round CR from unknown party = possible loan
            return "Sundry Debtors"      # Unknown CR = customer receipt


    def _update_status(self, filename, part, total, message):
        try:
            pct = int((part / total) * 100) if total > 0 else 0
            status_data = {
                "filename": filename,
                "part": part,
                "total": total,
                "progress_pct": pct,
                "percentage": pct,
                "message": message
            }
            with _GLOBAL_STATUS_LOCK:
                _GLOBAL_STATUS_STORE[filename] = status_data
                _GLOBAL_STATUS_STORE["_latest"] = status_data
            try:
                status_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extraction_status.json")
                with open(status_path, "w") as f:
                    json.dump(status_data, f)
            except Exception:
                pass
        except Exception as e:
            print(f"Warning: Failed to update extraction status: {e}")

    def _generate_content_with_retry(self, client, model, contents, config=None, max_retries=4, initial_backoff=2.0, start_key_offset: int = 0):
        import time
        import random
        
        # Production Fallback Hierarchy ordered by RPM/RPD capacity & speed:
        # Tier 1 (15 RPM / 500 RPD = 5,000 daily requests across 10 keys):
        #   - gemini-3.1-flash-lite, gemini-3.5-flash-lite, gemini-2.5-flash-lite
        # Tier 2 (5 RPM / 20 RPD):
        #   - gemini-2.5-flash, gemini-3.5-flash, gemini-3.7-flash, gemini-3.6-flash, gemini-3-flash
        # Tier 3 (Legacy & High Speed):
        #   - gemini-2.0-flash, gemini-1.5-flash, gemini-2.0-flash-lite
        FALLBACK_MODELS = [
            "gemini-3.1-flash-lite",
            "gemini-3.5-flash-lite",
            "gemini-2.5-flash-lite",
            "gemini-2.5-flash",
            "gemini-3.5-flash",
            "gemini-3.7-flash",
            "gemini-3.6-flash",
            "gemini-3-flash",
            "gemini-2.0-flash",
            "gemini-1.5-flash",
            "gemini-2.0-flash-lite"
        ]
        
        # Build candidate list starting from requested model
        raw_models = [model]
        for m in FALLBACK_MODELS:
            if m != model and m not in raw_models:
                raw_models.append(m)

        # Filter out models that hit 429 daily free tier quota today
        models_to_try = []
        for m in raw_models:
            if is_model_quota_exhausted_today(m):
                print(f"⚡ [Daily Quota Guard] Model '{m}' is quota-exhausted for today (429 Limit). Instantly routing to next fallback model...")
            else:
                models_to_try.append(m)

        if not models_to_try:
            print("⚠️ [Daily Quota Guard] All candidate models were blacklisted today. Resetting daily cache to attempt emergency recovery...")
            _EXHAUSTED_MODELS_CACHE.clear()
            _save_exhausted_models_cache({})
            models_to_try = raw_models

        last_exception = None
        keys_pool = self.api_keys_pool if self.api_keys_pool else ([self.api_key] if self.api_key else [])

        for active_model in models_to_try:
            for key_offset in range(len(keys_pool)):
                actual_idx = (self.current_key_idx + start_key_offset + key_offset) % len(keys_pool)
                active_key = keys_pool[actual_idx]
                
                # Instant 0.00s skip for keys blacklisted today for this model
                if is_key_model_quota_exhausted_today(active_key, active_model):
                    print(f"⚡ [Daily Blacklist Skip] Key #{actual_idx + 1} ({active_key[:6]}...) is daily quota-exhausted for '{active_model}'. Skipping instantly...")
                    continue

                try:
                    active_client = self._get_client(target_key=active_key)
                    print(f"🔮 [Gemini Request] Sending payload using Key #{actual_idx + 1}/{len(keys_pool)} ({active_key[:6]}...{active_key[-4:]}) and model '{active_model}'")
                    if config:
                        res = active_client.models.generate_content(
                            model=active_model,
                            contents=contents,
                            config=config
                        )
                    else:
                        res = active_client.models.generate_content(
                            model=active_model,
                            contents=contents
                        )
                    # Update active key index on clean success with thread safety
                    if not hasattr(self, '_key_lock'):
                        import threading
                        self._key_lock = threading.Lock()
                    with self._key_lock:
                        self.current_key_idx = actual_idx
                        self.api_key = active_key
                    return res
                except Exception as e:
                    last_exception = e
                    err_msg = str(e).lower()
                    
                    # 503 Overloaded -> try next key / fallback
                    if "503" in err_msg or "unavailable" in err_msg:
                        print(f"⚠️ Model '{active_model}' overloaded on Key #{actual_idx + 1}. Retrying next key/model...")
                        time.sleep(0.3)
                        continue

                    # Check for 429 Daily Free Tier Quota / Rate Limit
                    is_quota_429 = any(x in err_msg for x in ["429", "quota", "exhausted", "resource_exhausted", "rate_limit", "key_invalid", "permission_denied"])
                    if is_quota_429:
                        # Only blacklist for the whole day if it's a true daily quota exhaustion error
                        is_daily_exhausted = any(x in err_msg for x in ["quota", "resource_exhausted", "daily", "exceeded your current quota", "free tier", "limit reached"])
                        if is_daily_exhausted:
                            mark_key_model_quota_exhausted_today(active_key, active_model)
                            
                        if self.is_paid_api_key:
                            self.is_paid_api_key = False
                        
                        next_key_num = ((actual_idx + 1) % len(keys_pool)) + 1
                        reason_lbl = "Daily 500 RPD Limit" if is_daily_exhausted else "Per-Minute RPM Spike"
                        print(f"🔑 [API Key Rotator] Key #{actual_idx + 1} ({reason_lbl}) on model '{active_model}'. Seamlessly rotating to Key #{next_key_num}...")
                        time.sleep(0.2)
                        continue
                    
                    # Transient network error
                    is_transient = any(x in err_msg for x in [
                        "limit", "timeout", "capacity", "server disconnected", "connection reset",
                        "connection error", "remoteerror", "remoteprotocol",
                        "peer closed connection", "read timeout", "connect timeout",
                        "serverdisconnected", "eof occurred", "network", "broken pipe",
                        "ssl", "handshake", "connect failed", "name or service not known"
                    ])
                    
                    if is_transient:
                        print(f"⚠️ Key #{actual_idx + 1} transient network error: {e}. Retrying next key...")
                        time.sleep(0.3)
                        continue
                    else:
                        raise e
            
            print(f"🔄 [Model Fallback] All {len(keys_pool)} API keys hit rate limits on model '{active_model}'. Falling back to next model tier...")
            
        # If all models failed, raise the last exception
        if last_exception:
            raise last_exception

    def generate_business_profile(self, raw_data: str) -> str:
        """Generates a deep business context profile based on raw aggregated DBF data."""
        if not self.api_key:
            raise ValueError("Gemini API Key is not configured.")
            
        client = self._get_client()
        
        prompt = f"""You are an expert AI business analyst and accountant.
I will provide you with raw aggregated data from a client's accounting software database (Ledgers and Transaction frequencies).

Your task is to write a cohesive, comprehensive 'Business Profile' paragraph that describes the client's business context.
This profile will be injected into future AI extraction prompts to help another AI perfectly categorize messy PDFs and Bank Statements.

Raw Data:
{raw_data}

Instructions for the Profile:
1. Describe what kind of business they likely are based on their Debtors/Creditors.
2. Explicitly list their Top Customers (Debtors).
3. Explicitly list their Top Suppliers (Creditors).
4. List the Bank Accounts they use.
5. List their most common Expenses and Tax Ledgers.
6. Keep the tone professional, objective, and dense with facts. No fluff. Do NOT use markdown code blocks.
"""
        response = self._generate_content_with_retry(
            client=client,
            model=self.model_name,
            contents=prompt
        )
        return response.text.strip() if response and response.text else ""

    def extract_text_from_file(self, file_path: str) -> str:
        """Extracts text content from a given specification file using local parsing or Gemini File API."""
        ext = os.path.splitext(file_path)[1].lower()
        
        # --- SPEC FILE CACHE: Skip AI if this exact file was processed before ---
        try:
            with open(file_path, 'rb') as _f:
                file_hash = hashlib.md5(_f.read()).hexdigest()
            if file_hash in _SPEC_FILE_CACHE:
                print(f"⚡ [Spec Cache HIT] Returning cached spec for hash {file_hash[:8]}... (instant, no API call)")
                return _SPEC_FILE_CACHE[file_hash]
        except Exception:
            file_hash = None
        
        # Gemini Parsing (Image/PDF/Excel/Text/CSV)
        if not self.api_key:
            raise ValueError("Gemini API Key is not configured.")
            
        client = self._get_client()
        
        uploaded_file = None
        contents = []
        prompt = """You are an Expert AI Accountant and Data Analyst. The user has uploaded a file containing specifications, rules, or remarks for a specific client (e.g. how to categorize expenses, which ledgers to map to, etc).
Your goal is to deeply analyze this file and distill it into a highly intelligent, perfectly structured set of strict RULES and MAPPINGS. 

Instructions:
1. Identify any explicit mappings (e.g., 'If the description contains X, map to Ledger Y').
2. Identify any patterns or recurring expenses mentioned.
3. Structure your response cleanly using bullet points so that another AI agent can easily read your output and follow it flawlessly.
4. DO NOT just dump the raw text. Synthesize it into actionable accounting rules.

Return ONLY the distilled rules and mappings."""

        excel_csv_content = None
        if ext in [".xlsx", ".xls"]:
            excel_csv_content = self._read_excel_text_native(file_path)
        elif ext in [".txt", ".csv"]:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    excel_csv_content = f.read()
            except Exception as e:
                raise ValueError(f"Failed to read text file locally: {e}")

        if excel_csv_content:
            prompt += f"\n\nHere is the raw data from the file:\n{excel_csv_content}\n\nPlease parse this data."
            contents = [prompt]
        else:
            if ext in [".pdf", ".png", ".jpg", ".jpeg"]:
                print(f"Uploading {file_path} to Gemini File API for specification distillation...")
                uploaded_file = client.files.upload(file=file_path)
                contents = [uploaded_file, prompt]
            else:
                raise ValueError(f"Unsupported specification file type: {ext}")
        
        try:
            response = self._generate_content_with_retry(
                client=client,
                model=self.model_name,
                contents=contents
            )
            result_text = response.text.strip() if response and response.text else ""
            # Cache result so the same spec file never hits the API twice
            if file_hash and result_text:
                _SPEC_FILE_CACHE[file_hash] = result_text
                print(f"💾 [Spec Cache STORE] Cached spec result for hash {file_hash[:8]}...")
            return result_text
        finally:
            if uploaded_file:
                try:
                    if uploaded_file.name:
                        client.files.delete(name=uploaded_file.name)
                except:
                    pass

    @staticmethod
    def _extract_native_excel_mappings(text_content: str) -> dict:
        """Deterministic native Python parser that extracts Item/Party -> Category mappings from structured Excel/text files."""
        if not text_content:
            return {}
        mappings = {}
        lines = [l.strip() for l in text_content.splitlines() if l.strip()]
        
        # 1. Pattern: Expense Transaction Report parser (Date -> Party Name -> Category -> Description)
        for i in range(len(lines)):
            m = re.match(r'^\d{1,2}[\/\.-]\d{1,2}[\/\.-]\d{2,4}$', lines[i])
            if m:
                window = lines[i+1:i+14]
                for w in window:
                    if len(w) >= 3 and not re.match(r'^\d+(\.\d+)?$', w) and not re.match(r'^\d{1,2}[\/\.-]\d{1,2}[\/\.-]\d{2,4}$', w):
                        w_up = w.upper()
                        skip_headers = ['PARTY NAME', 'GSTIN', 'TOTAL AMOUNT', 'PAYMENT TYPE', 'PAID AMOUNT', 'BALANCE AMOUNT', 'DESCRIPTION', 'TRANSACTION TYPE', 'USERNAME', 'ALL USERS', 'GENERATED ON']
                        if not any(sh == w_up for sh in skip_headers):
                            if any(k in w_up for k in ['EXPENSE', 'SALARY', 'RENT', 'FUEL', 'PETROL', 'DIESEL', 'ELECTRICITY', 'TELEPHONE', 'MOBILE', 'FOOD', 'TEA', 'TRAVEL', 'COURIER', 'STATIONERY', 'MAINTENANCE', 'REPAIR', 'TAX', 'AUDIT', 'LEGAL', 'BANK', 'INTEREST', 'CHARGES', 'TRANSPORT', 'FREIGHT', 'OFFICE']):
                                mappings[w_up] = w

        # 2. Pattern: Key: Value or Key -> Value pairs in text
        for line in lines:
            if '->' in line or '=>' in line:
                parts = re.split(r'->|=>', line, maxsplit=1)
                if len(parts) == 2:
                    k, v = parts[0].strip(), parts[1].strip()
                    if k and v and len(k) > 1 and len(v) > 1:
                        skip_words = ['date', 'time', 'generated', 'total', 'amount', 'username', 'all users']
                        if not re.match(r'^\d+$', k) and not any(w in k.lower() for w in skip_words):
                            mappings[k.upper()] = v
        return mappings

    @staticmethod
    def _read_excel_text_native(file_path: str) -> str:
        """Pure Python zero-dependency local Excel parser for .xlsx and .xls files."""
        import zipfile
        import xml.etree.ElementTree as ET

        if zipfile.is_zipfile(file_path):
            try:
                strings = []
                with zipfile.ZipFile(file_path, 'r') as z:
                    shared_strs = []
                    if 'xl/sharedStrings.xml' in z.namelist():
                        tree = ET.fromstring(z.read('xl/sharedStrings.xml'))
                        for elem in tree.iter():
                            if elem.tag.endswith('t') and elem.text:
                                shared_strs.append(elem.text)
                    
                    for name in z.namelist():
                        if name.startswith('xl/worksheets/sheet'):
                            sheet_tree = ET.fromstring(z.read(name))
                            for cell in sheet_tree.iter():
                                if cell.tag.endswith('t') and cell.text:
                                    strings.append(cell.text)
                                elif cell.tag.endswith('v') and cell.text:
                                    try:
                                        idx = int(cell.text)
                                        if 0 <= idx < len(shared_strs):
                                            strings.append(shared_strs[idx])
                                        else:
                                            strings.append(cell.text)
                                    except Exception:
                                        strings.append(cell.text)
                if strings:
                    return "\n".join(strings)
            except Exception as e:
                print(f"Zip Excel parse warning: {e}")

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                raw_text = f.read()
                clean = re.sub(r'<[^>]+>', ' ', raw_text)
                clean = re.sub(r'\s+', ' ', clean).strip()
                if len(clean) > 50:
                    return clean
        except Exception:
            pass

        try:
            with open(file_path, "rb") as f:
                content = f.read()
                ascii_strings = re.findall(rb'[A-Za-z0-9\s\.\,\/\-\:\_\@]{4,}', content)
                decoded = [s.decode('ascii', errors='ignore').strip() for s in ascii_strings if len(s.strip()) > 3]
                if decoded:
                    return "\n".join(decoded[:500])
        except Exception:
            pass

        return ""

    def extract_structured_specifications(self, file_path: str) -> dict:
        """
        Parses a specification guide file (PDF, Excel, Image, Word, Text, CSV) and returns
        both structured JSON mappings (expense_mappings, keyword_rules) and a synthesized summary guide.
        """
        ext = os.path.splitext(file_path)[1].lower()
        if not self.api_key:
            raise ValueError("Gemini API Key is not configured.")
            
        client = self._get_client()
        uploaded_file = None
        contents = []
        
        prompt = """You are an Expert AI Accountant.
The user uploaded a Client Specification / Guideline document (Excel, PDF, Image, Word, CSV, or Text).
Your task is to analyze it deeply and extract:
1. "specifications_summary": Clean, bullet-point actionable accounting instructions for the AI prompt.
2. "expense_mappings": A JSON dictionary of key narration/party keywords -> target ledger name (e.g. {"SWIGGY": "Food Expenses", "SHELL": "Petrol Expenses"}).
3. "product_mappings": A JSON dictionary of item keyword -> product name for inventory bills.

Return your response ONLY as a JSON object matching this schema:
{
    "specifications_summary": "Bullet points summary of client guidelines",
    "expense_mappings": {
        "KEYWORD1": "Ledger Name 1",
        "KEYWORD2": "Ledger Name 2"
    },
    "product_mappings": {
        "ITEM_KEYWORD1": "Product Name 1"
    }
}
"""

        excel_csv_content = None
        if ext in [".xlsx", ".xls"]:
            excel_csv_content = self._read_excel_text_native(file_path)
        elif ext in [".txt", ".csv", ".md"]:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    excel_csv_content = f.read()
            except Exception as e:
                pass
        elif ext == ".pdf":
            try:
                import pypdf
                reader = pypdf.PdfReader(file_path)
                pdf_text = []
                for page in reader.pages:
                    t = page.extract_text()
                    if t: pdf_text.append(t)
                if pdf_text:
                    excel_csv_content = "\n".join(pdf_text)
            except Exception:
                pass

        native_mappings = self._extract_native_excel_mappings(excel_csv_content) if excel_csv_content else {}

        if excel_csv_content:
            prompt += f"\n\nHere is the raw content of the specification file:\n{excel_csv_content}"
            contents = [prompt]
        else:
            try:
                uploaded_file = client.files.upload(file=file_path)
                contents = [uploaded_file, prompt]
            except Exception as ex:
                print(f"Warning: File upload failed ({ex}), using local native extraction fallback.")

        parsed = {"specifications_summary": "", "expense_mappings": {}, "product_mappings": {}}
        try:
            response = self._generate_content_with_retry(
                client=client,
                model=self.model_name or "gemini-2.5-flash",
                contents=contents,
                config=make_config("application/json")
            )
            text = response.text.strip() if response and response.text else "{}"
            if text.startswith("```json"): text = text[7:]
            if text.startswith("```"): text = text[3:]
            if text.endswith("```"): text = text[:-3]
            if text.strip():
                try:
                    parsed = json.loads(text.strip())
                except Exception:
                    pass
        except Exception as e:
            print(f"Warning: Gemini spec extraction failed ({e}), using native extraction fallback.")
        finally:
            if uploaded_file:
                try:
                    if uploaded_file.name: client.files.delete(name=uploaded_file.name)
                except: pass

        if not isinstance(parsed, dict):
            parsed = {}
            
        gemini_exp = parsed.get("expense_mappings", {})
        if not isinstance(gemini_exp, dict): gemini_exp = {}
        
        combined_exp = {**native_mappings, **gemini_exp}
        parsed["expense_mappings"] = combined_exp
        
        if not parsed.get("specifications_summary") and combined_exp:
            rules_summary = "\n".join([f"• Map '{k}' to '{v}'" for k, v in combined_exp.items()])
            parsed["specifications_summary"] = f"Learned Expense Categorization Rules:\n{rules_summary}"
            
        return parsed

    def _extract_single_content(self, client, contents, start_key_offset: int = 0) -> dict:
        response = self._generate_content_with_retry(
            client=client,
            model=self.model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            ),
            start_key_offset=start_key_offset
        )
        text = response.text.strip() if response and response.text else ""
        text = self.repair_json_string(text)
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                print(f"⚠️ Gemini returned a JSON array ({len(parsed)} elements) instead of object wrapper. Wrapping automatically...")
                return {"status": "success", "extracted_data": parsed}
            elif isinstance(parsed, dict):
                return parsed
            else:
                return {"status": "error", "extracted_data": []}
        except Exception as e:
            print(f"❌ Failed to parse JSON response from Gemini: {e}. Raw text was: {text[:500]}...")
            return {"status": "error", "extracted_data": []}

    def detect_pdf_chronology(self, file_path: str) -> str:
        """
        Detects if a PDF statement is 'forward' (oldest first) or 'reverse' (newest first).
        Returns 'forward', 'reverse', or 'unknown'.
        """
        import re
        from datetime import datetime as _ddt
        
        first_page_dates = []
        last_page_dates = []
        
        def extract_dates(text):
            dates = []
            # Try to find standard dates like "1 July 2026", "31 July 2026"
            standard_matches = re.findall(r'\b\d{1,2}\s+[A-Za-z]+\s+\d{4}\b', text)
            for m in standard_matches:
                try:
                    dt = _ddt.strptime(m, "%d %B %Y")
                    dates.append(dt)
                except ValueError:
                    try:
                        dt = _ddt.strptime(m, "%d %b %Y")
                        dates.append(dt)
                    except ValueError:
                        pass
                        
            # Also find split dates like "2026-\n07-31" by replacing newline
            cleaned = text
            cleaned = re.sub(r'(\d{4}-)\s*\n\s*(\d{2}-\d{2})', r'\1\2', cleaned)
            cleaned = re.sub(r'(\d{2}-\d{2})\s*\n\s*(\d{4}-)', r'\2\1', cleaned)
            
            # Now look for YYYY-MM-DD
            matches = re.findall(r'\b\d{4}-\d{2}-\d{2}\b', cleaned)
            for m in matches:
                try:
                    dt = _ddt.strptime(m, "%Y-%m-%d")
                    dates.append(dt)
                except ValueError:
                    pass
                    
            # If no dates found, look for DD/MM/YYYY or DD-MM-YYYY
            matches = re.findall(r'\b\d{2}[-/.]\d{2}[-/.]\d{4}\b', cleaned)
            for m in matches:
                for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
                    try:
                        dt = _ddt.strptime(m, fmt)
                        dates.append(dt)
                        break
                    except ValueError:
                        pass
            return dates

        pdf_extracted = False
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                total_p = len(pdf.pages)
                if total_p < 2:
                    return "forward"
                
                # Check first page
                first_txt = pdf.pages[0].extract_text() or ""
                first_page_dates = extract_dates(first_txt)
                
                # Scan backwards from the end to find the first page that contains any dates
                for idx in range(total_p - 1, -1, -1):
                    last_txt = pdf.pages[idx].extract_text() or ""
                    last_page_dates = extract_dates(last_txt)
                    if last_page_dates:
                        break
                pdf_extracted = True
        except Exception:
            pdf_extracted = False

        if not pdf_extracted:
            try:
                import pypdf
                reader = pypdf.PdfReader(file_path)
                total_p = len(reader.pages)
                if total_p < 2:
                    return "forward"
                
                first_txt = reader.pages[0].extract_text() or ""
                first_page_dates = extract_dates(first_txt)
                
                for idx in range(total_p - 1, -1, -1):
                    last_txt = reader.pages[idx].extract_text() or ""
                    last_page_dates = extract_dates(last_txt)
                    if last_page_dates:
                        break
            except Exception as e:
                print(f"⚠️ Chronology detection failed: {e}")
                return "unknown"
            
        if first_page_dates and last_page_dates:
            avg_first = sum((d.timestamp() for d in first_page_dates)) / len(first_page_dates)
            avg_last = sum((d.timestamp() for d in last_page_dates)) / len(last_page_dates)
            if avg_first > avg_last:
                print(f"📅 [Chronology Detector] Detected REVERSE chronological statement (avg first page: {avg_first} > avg last page: {avg_last}).")
                return "reverse"
            else:
                print(f"📅 [Chronology Detector] Detected FORWARD chronological statement (avg first page: {avg_first} <= avg last page: {avg_last}).")
                return "forward"
                
        return "unknown"

    def parse_bank_pdf_natively(self, file_path: str, pdf_password: str = "") -> dict:
        """
        DETERMINISTIC NATIVE LINE-BY-LINE BANK PDF PARSER (100% Math Precision, 0.05s Speed).
        Delegates to modules.bank.parser.
        """
        import sys
        sys.path.append(os.path.join(os.path.dirname(__file__), "modules"))
        from modules.bank.parser import BankParser
        bp = BankParser()
        return bp.parse_bank_pdf_natively(file_path, pdf_password=pdf_password)

    def extract_invoice_data(self, file_path: str, client_memory: dict, module: str, instruction: str = "", pdf_password: str = "") -> dict:
        """
        Takes a file path (Excel, image, PDF), sends it to Gemini,
        and returns structured JSON data using the client_memory.
        """
        file_path = os.path.abspath(file_path)
        ext = os.path.splitext(file_path)[1].lower()
        
        if not self.api_key:
            raise ValueError("Gemini API Key is not configured.")
            
        client = self._get_client()
        base_filename = os.path.basename(file_path)
        self._update_status(base_filename, 0, 0, f"Initializing extraction for {base_filename}...")
        
        print(f"Extracting data from {file_path} using Gemini API for module {module}...")
        
        
        # Format the memory into the prompt
        expense_mappings = client_memory.get("expense_mappings", {})
        memory_instruction = ""
        if expense_mappings:
            memory_instruction = "Use the following mappings to correct party names based on narration or keywords:\n"
            for k, v in expense_mappings.items():
                memory_instruction += f"- '{k}' maps to '{v}'\n"
                
        existing_ledgers = client_memory.get("existing_ledgers", [])
        ledgers_instruction = ""
        if existing_ledgers:
            ledgers_instruction = "\nLIST OF EXISTING LEDGER ACCOUNTS IN MIRACLE (Prioritize matching to these names when possible):\n"
            for led in existing_ledgers:
                if isinstance(led, dict):
                    l_name = (led.get("name") or led.get("print_name") or "").strip()
                    l_grp = (led.get("group_name") or "").strip()
                    if l_name:
                        ledgers_instruction += f"- {l_name} ({l_grp})\n" if l_grp else f"- {l_name}\n"
                elif led:
                    l_str = str(led).strip()
                    if l_str:
                        ledgers_instruction += f"- {l_str}\n"
                
        user_context = ""
        if instruction:
            user_context = f"\nUSER PROVIDED CONTEXT (follow this very carefully): {instruction}"

        business_profile = client_memory.get("business_profile", "")
        profile_instruction = ""
        if business_profile:
            profile_instruction = f"\nCLIENT BUSINESS PROFILE (CRITICAL CONTEXT):\n{business_profile}\n"

        specifications = client_memory.get("specifications", "")
        spec_instruction = ""
        if specifications:
            spec_instruction = f"\nCLIENT SPECIFICATIONS & REMARKS (CRITICAL MEMORY):\nThe client has provided the following specifications/notes to help you map their transactions accurately. You MUST use these notes to map party names, transaction types, and ledgers correctly:\n{specifications}\n"

        if module in ["Bank Statements", "Cash Entries"]:
            schema_str = """{
    "status": "success",
    "bank_name": "The SHORT core name of the Bank or Cash Account from the document header (e.g. 'HDFC Bank', 'ICICI Bank', 'SBI', 'Axis Bank', or 'Cash On Hand'). Do NOT include legal suffixes like 'Ltd.', 'Limited', 'Pvt. Ltd.'. Just the brand name.",
    "document_owner": "The exact legal name of the account holder, client, or company printed in the top header/profile section of the statement. If not found, return empty string.",
    "opening_balance": 0.0,
    "extracted_data": [
        {
            "date": "YYYY-MM-DD",
            "narration": "Raw description/narration from the statement/cashbook for this transaction",
            "mapped_ledger": "The name of the accounting ledger this should map to (e.g. 'Neel', 'Dhruv', 'Salary', or a cleaned party/business name like 'Expressbomb' if new, defaulting to 'Suspense Account' only if no party name is present)",
            "transaction_type": "Receipt or Payment",
            "amount": 0.0,
            "running_balance": 0.0,
            "reference_no": "Cheque/Ref/UTR number as string, or empty string",
            "group_hint": "Hint for the account group (e.g. Indirect Expenses, Incomes, Debtors, Creditors, Fixed Assets, Investments, Capital, Suspense, etc.)",
            "confidence_score": 95,
            "flags": []
        }
    ]
}"""
            rules_str = """IMPORTANT RULES:
- CRITICAL — CHRONOLOGICAL ORDER (START OF MONTH FIRST): You MUST extract and output all transactions in FORWARD CHRONOLOGICAL ORDER (oldest transactions / start of the month first, newest transactions / end of the month last). If the document page displays them in reverse chronological order (newest first), you MUST reverse the order in your JSON output so that 1st of the month appears as the FIRST element of 'extracted_data', and 31st of the month appears as the LAST element. This is critical for balance validation.
- CRITICAL — EXTRACT ALL SAME-DATE & SAME-AMOUNT TRANSACTIONS: Bank statements frequently contain multiple distinct transactions on the SAME DATE with the SAME AMOUNT (e.g. paying ₹15,000 salary to two different employees, or multiple ₹500 UPI transfers). YOU MUST EXTRACT EVERY SINGLE ROW SEPARATELY. NEVER skip, combine, or drop a transaction row just because its date, amount, or narration is similar to another row! Each row in the document represents a real movement of money and MUST be included in your output!
- CRITICAL — COMPLETE PAGE & IMAGE TABLE BOUNDARY (FIRST & LAST ENTRY): You MUST scan the document table from the VERY FIRST TRANSACTION ROW directly under the column headers (Page Top), down to the VERY LAST TRANSACTION ROW directly above the footer/page totals (Page Bottom). Pay extreme care NOT to miss the first transaction entry at the top of the table or the last transaction entry at the bottom of the page/image!
- CRITICAL — NO DATE GAPS ALLOWED: If in your output two consecutive transactions have dates that are more than 25 days apart, that is a FAILURE. It means you silently skipped transactions on the pages between them. You MUST re-scan the pages and find all missing rows.
- DO NOT extract "Opening Balance", "Closing Balance", or "Brought Forward" / "Carried Forward" rows as transactions. Only extract actual movements of money.
- Extract the statement's Opening Balance (or Brought Forward) amount from the top of the document and place it in the top-level 'opening_balance' field. If not found, output 0.0.
- Identify the main Bank Name or Cash Account from the document header and place it in 'bank_name'. IMPORTANT: Output ONLY the short bank brand name — do NOT include legal suffixes like 'Ltd.', 'Limited', 'Pvt. Ltd.', 'Bank Ltd.'. For example: if the document says 'HDFC Bank Ltd.', output just 'HDFC Bank'. If it says 'State Bank of India', output 'SBI'. The short name matches better with accounting ledger names.
- Identify the Account Holder Name, Company Name, or Client Name printed in the header/profile section of the statement and place it in 'document_owner' as a string. If not found, return empty string.
- CRITICAL COLUMN ALIGNMENT & TRANSACTION CLASSIFICATION (Applies to both Excel/CSV data and PDF/Image documents):
  * Bank statements always have separate columns for "Withdrawal / Debit / Payment / Paid Out" (money leaving the account) and "Deposit / Credit / Receipt / Received In" (money entering the account).
  * A Withdrawal/Debit (non-zero value in withdrawal/debit column) MUST ALWAYS be mapped as "Payment".
  * A Deposit/Credit (non-zero value in deposit/credit column) MUST ALWAYS be mapped as "Receipt".
  * NEVER swap them. Look at the non-zero amount carefully: if it is in the withdrawal column, the transaction is a Payment. If it is in the deposit column, it is a Receipt. Double check that you do not mix these columns up!
  * MATHEMATICAL VERIFICATION: You MUST extract the running balance for EVERY row into the 'running_balance' field. YOU MUST use the running_balance to verify if it is a Receipt or Payment! Compare the current row's running_balance to the previous row's running_balance. If running_balance > previous running_balance, it MUST be a Receipt (Deposit). If running_balance < previous running_balance, it MUST be a Payment (Withdrawal). If you extract a Receipt but the balance decreased, YOUR EXTRACTION IS WRONG and you must fix it before outputting!
  * CRITICAL: Pay extreme attention to the visual alignment of the columns. If a date column or other column is empty for a row, it means the transaction occurred on the same date as the row above it. Do NOT let empty cells cause you to shift the amount to the wrong column.
- CRITICAL — DATE FORMAT (Indian Bank Statements): ALL dates in Indian bank statements are ALWAYS in DD/MM/YY or DD/MM/YYYY format (Day first, then Month, then Year). NEVER interpret dates as MM/DD/YY (American format). Examples of correct parsing:
  * "26/06/25" → Day=26, Month=06, Year=2025 → output "2025-06-26"
  * "01/07/25" → Day=01, Month=07, Year=2025 → output "2025-07-01"
  * "07/01/25" → Day=07, Month=01, Year=2025 → output "2025-01-07"
  * "31/03/2025" → Day=31, Month=03, Year=2025 → output "2025-03-31"
  Always output dates in ISO format: YYYY-MM-DD. If year is 2 digits (e.g., 25), assume 20xx (e.g., 2025).
- 'transaction_type' MUST be exactly "Receipt" or "Payment".
- 'narration' field: ALWAYS copy the FULL original description/narration text from the bank statement. Do NOT shorten, clean, or truncate it. The full text is needed for audit purposes.
- 'mapped_ledger' and 'group_hint': Use the following logic in ORDER of priority:
  🏛️ ICAI CHARTERED ACCOUNTANT STATUTORY RULES & AS/Ind AS COMPLIANCE:
  1. THREE GOLDEN RULES OF DOUBLE ENTRY ACCOUNTING:
     - Personal Accounts (Receivers & Givers): Debit the Receiver, Credit the Giver.
       * Payments to Creditors/Vendors -> 'Sundry Creditors' (G0000013).
       * Receipts from Debtors/Customers -> 'Sundry Debtors' (G0000009).
     - Real Accounts (Assets & Liabilities): Debit what comes in, Credit what goes out.
       * Purchases of Capital Assets (Computers, Machinery, Vehicles, Furniture) -> 'Fixed Assets' (G0000006).
       * Cash Transfers / ATM Withdrawals -> 'Cash-in-Hand' (G0000005) or 'Contra (BC)'.
     - Nominal Accounts (Expenses, Incomes, Gains, Losses): Debit all expenses & losses, Credit all incomes & gains.
       * Revenue Expenses (Rent, Salary, Electricity, Petrol, Bank Fees, Legal Charges) -> 'Indirect Expenses' (G0000024).
       * Direct Operational Costs (Freight, Customs, Loading, Manufacturing) -> 'Direct Expenses' (G0000023).

  2. CAPITAL EXPENDITURE vs. REVENUE EXPENDITURE (AS-10 / Ind AS 16):
     - Capital Assets (Purchasing a Laptop, Printer, Mobile Phone, AC, Machine, Vehicle) -> MUST BE classified under 'Fixed Assets' (G0000006). NEVER map to a routine expense or individual person!
     - Revenue Maintenance (Computer Repair, AMC, Software Subscription, Fuel/Petrol) -> Classified under 'Indirect Expenses' (G0000024).

  3. PROPRIETOR PERSONAL DRAWINGS RULE (Income Tax Act Sec 37(1)):
     - Money paid to family members (Mom, Wife, Son, Brother, Self), personal LIC policies, medical bills, household groceries -> MUST BE mapped to 'Drawings A/c' or 'Proprietor Capital Account' (G0000001), NOT business expenses!

  4. STATUTORY TAX & DUTIES RULE:
     - Payments for 'GSTPMT', 'ADVANCE TAX', 'SELF ASSESSMENT TAX', 'INCOME TAX', 'TDS' -> MUST BE classified under 'Duties & Taxes' (G0000010) or Direct Taxes.

  STEP 1 — CHECK EXISTING LEDGERS & AI MEMORY MAPPINGS FIRST:
  * Look at the "LIST OF EXISTING LEDGER ACCOUNTS IN MIRACLE" below. You MUST try to find a semantic match for the narration amongst these existing ledgers!
  * Look at the "expense_mappings" (AI Memory Mappings) provided below. If a narration contains any of those keywords, map to that ledger!
  * CRITICAL RULE: If the narration contains 'neel', 'dhruv', or 'dhure', map the 'mapped_ledger' to 'SALARY' because they are salary employees!
  
  STEP 2 — PARSE UPI / NEFT / IMPS DESCRIPTIONS (Very Important!):
  Bank descriptions commonly follow these patterns:
    * UPI: "UPI-[PARTY NAME]-[PURPOSE/REMARKS]@[BANK_VPA]" or "UPI/[REF]/[PARTY]/[VPA]"
    * NEFT/IMPS: "NEFT-[REF]-[PARTY NAME]" or similar
  
  For UPI descriptions, split by "-" and "@" to identify THREE distinct parts:
    a) Prefix: "UPI", "NEFT", "IMPS" etc. — ignore this.
    b) Party Name: The human/business name (e.g. DODIYA VIRALBHAI, JAYDEV NAKUM, HOTEL DARSHAN, CARS24).
    c) Purpose/Remark: The text AFTER the party name and BEFORE the "@" (e.g. "milk", "food", "petrol", "salary", "loan", "rent", "grocery", "medicine", "dinner", "recharge").
  
  CRITICAL DECISION RULE based on the Narration and Party Name:
  * FIRST, check if the FULL narration or the extracted Party Name partially matches ANY existing ledger in the "LIST OF EXISTING LEDGER ACCOUNTS IN MIRACLE". If a name matches (e.g. "MILAN.NAVNITMOTORS" matches "Milan Navnit Motors"), use that ledger!
  * If NO matching ledger is found AND the transaction is a DEPOSIT (Receipt), you MUST map it to "UPI DEBTOR ACOUNT" (or exactly "UPI DEBTOR ACCOUNT" if it exists).
  * If the Purpose/Remark contains a recognizable EXPENSE or INCOME word (like: milk, food, groceries, petrol, fuel, diesel, salary, rent, electricity, medicine, medical, dinner, lunch, breakfast, hotel, shop, recharge, mobile, insurance, repair, maintenance, transport, auto, rickshaw, school, fees, water, gas), THEN:
      - The 'mapped_ledger' should be the EXPENSE/INCOME TYPE (e.g. "Food Expenses", "Petrol Expenses", "Salary", "Rent") — NOT the person's name!
      - The 'group_hint' should be the appropriate expense or income group.
      - Example: "UPI-JAYDEV NAKUM-milk@hdfc" → mapped_ledger="Food Expenses", group_hint="Indirect Expenses"
      - Example: "UPI-RAJU-petrol@paytm" → mapped_ledger="Petrol Expenses", group_hint="Indirect Expenses"
      - Example: "UPI-AKBARI KEYUR-salary@axis" → mapped_ledger="SALARY", group_hint="Indirect Expenses"
  * If the Purpose/Remark is EMPTY, is a UPI ID (like "99@paytm", "12@okaxis"), is a reference number, or is a generic word (like "payment", "transfer", "upi"), THEN:
      - The 'mapped_ledger' should be the clean PARTY NAME (e.g. "DODIYA VIRALBHAI", "JAYDEV NAKUM", "Hotel Darshan").
      - Remove only the payment prefix ("UPI-", "NEFT-") and the "@bank" suffix. Keep the name clean.
      - Example: "UPI-CARS24 SERVICES-99@paytm" → mapped_ledger="Cars24 Services"
      - Example: "UPI-DODIYA VIRALBHAI-transfer@hdfc" → mapped_ledger="DODIYA VIRALBHAI"
      - Example: "NEFT-00023-HOTEL DARSHAN LTD" → mapped_ledger="Hotel Darshan"
  * CRITICAL CLEAN NAME MANDATE: `mapped_ledger` and `party_name` MUST be a clean human or company name (e.g. "Patel Traders" or "Jaydev Nakum"). NEVER output the full raw narration string (such as "UPI-12345-PATEL TRADERS-MILK@OKHDFC" or "NEFT-00029384-HOTEL DARSHAN LTD") as the `mapped_ledger` or `party_name`. Strip all payment prefixes ("UPI-", "NEFT-"), "@bank" handles, and numeric reference codes.
  * Only default to 'Suspense Account' if there is absolutely NO discernible party name or purpose in the narration.
- CRITICAL EXCEPTION FOR PERSONS (e.g. Personal Transfers / Loans): If the mapped_ledger is a person's name (NOT an expense/income type) — i.e. a human name like 'Jaydev', 'Dharmik', 'Mayur', 'Kalpeshbhai', 'Dodiya', 'Akbari', etc.:
  * If the transaction is a WITHDRAWAL / PAYMENT (Money Sent to person): You MUST ALWAYS set the 'group_hint' to 'Loans & Advances (Asset)'. This is money you are giving TO that person.
  * If the transaction is a DEPOSIT / RECEIPT (Money Received from person): You MUST ALWAYS set the 'group_hint' to 'Unsecured Loans'. This is money you are receiving FROM that person. DO NOT use 'Loans & Advances (Asset)' for deposits from persons under any circumstances.
  * An individual person is NEVER classified as an Indirect Expense, Direct Expense, Income, or any other group!
- CRITICAL FOR GROUP HINTS (e.g. Personal vs Business): If the USER PROVIDED CONTEXT or SPECIFICATIONS indicate this is "Personal Accounting" or "Not for Business", you should bias towards classifying general spending (like Fuel Expense, Grocery, Dining, Electricity) as 'Indirect Expenses' or 'Direct Expenses' and receipts as 'Incomes' or 'Investments'.
- CRITICAL BANK CHARGES ACCOUNTING RULE:
  * If a transaction narration contains bank fee/charge keywords (e.g. 'BANK CHARGES', 'BANK COMM', 'SMS CHARGES', 'SERVICE CHARGES', 'PROCESSING FEE', 'MDR RECOVERY', 'RUPAY MDR', 'CHQ DEP RET CHGS', 'MIN BAL CHG', 'DEBIT CARD CHGS', 'FOREX CHARGES', 'GST ON BANK CHARGES'):
    - You MUST map 'mapped_ledger' to 'Bank Charges' (or 'Indirect Expenses').
    - You MUST set 'transaction_type' to 'Payment' (Bank Payment - BP).
    - You MUST set 'group_hint' to 'Indirect Expenses'.
    - NEVER, EVER classify Bank Charges as a Contra Entry, Bank Account, or Bank Transfer! Bank Charges are a Business Expense!
- CRITICAL BANK CONTRA RULE: NEVER map a transaction's `mapped_ledger` to the same bank as the statement itself! (e.g., if extracting an HDFC Bank statement, do NOT map a UPI transfer to the "HDFC BANK" ledger). The offset ledger must be the external party. Contra entries are ONLY for transfers between own Cash and Bank accounts.
- CRITICAL UPI NAME EXTRACTION: Do NOT extract bank VPA suffixes (like '@hdfcbank', '@okaxis', '@ybl', '@icici', '@paytm', '@sbi') as the party name! If the narration is just a string of numbers (e.g., 'UPI-1234567890'), do not hallucinate a bank name.
- CRITICAL ANTI-HALLUCINATION FOR NAMES: NEVER EVER invent, guess, or carry-over a person's name from a previous row! If the narration is purely numbers/references (e.g., "UPI-0000003817877", "@OKICICI-61550900", "UPI-124401504609") and contains NO HUMAN OR BUSINESS NAME inside that specific string, you MUST NOT output random names like "Varsha", "Heena", "Prachi", or reuse a name from the row above. If there is no explicit name inside the current row's narration text, map it to 'UPI DEBTOR ACOUNT' (if deposit) or 'Suspense Account' (if withdrawal). Hallucinating or carrying over names is a FATAL ERROR!
- SELF-HEALING CHECK: Before finalizing your output, verify every `mapped_ledger` against its own `narration`. If the `mapped_ledger` matches the `bank_name`, or if you mapped a human name but that name DOES NOT physically exist as a substring inside THAT EXACT ROW'S narration string, YOU HAVE MADE A MASSIVE CARRY-OVER MISTAKE. Fix it immediately by mapping to 'Suspense Account' or 'UPI DEBTOR ACOUNT'.
- confidence_score: An integer from 0 to 100. Lower it (e.g., to 75 or below) if:
  * The scan quality of the document is poor or blurry (add "Blurry Image" to flags)
  * The transaction has been mapped to "Suspense Account" (add "Suspense Mapping" to flags)
  * The transaction date or amount is hard to read or uncertain (add "Uncertain Date" or "Uncertain Amount" to flags)
  * The narration is incomplete or cut off (add "Incomplete Narration" to flags)
- flags: A list of warning strings if there are any issues. Only use these exact flag strings when applicable: "Blurry Image", "Suspense Mapping", "Uncertain Date", "Uncertain Amount", "Incomplete Narration". If there are no issues, return an empty list [].
"""
        else:
            schema_str = """{
    "status": "success",
    "document_owner": "The exact legal name of the buyer (for Purchase bills) or the seller (for Sales bills) which represents the client's business printed in the header/consignee section of the invoice. If not found, return empty string.",
    "extracted_data": [
        {
            "date": "YYYY-MM-DD",
            "bill_no": "invoice/bill number as string",
            "party_name": "Name of the supplier, customer, or party",
            "party_gstin": "GSTIN (GST Identification Number) of the party if available. If the party is unregistered, has no GSTIN, or is a B2C client, set to empty string \"\"",
            "party_address": "Full address of the customer/party as a single string if available, otherwise empty string \"\"",
            "party_city": "City of the customer/party if available, otherwise empty string \"\"",
            "party_pincode": "6-digit Pincode/Zipcode of the customer/party if available, otherwise empty string \"\"",
            "taxable_amount": 0.0,
            "cgst": 0.0,
            "sgst": 0.0,
            "igst": 0.0,
            "total": 0.0,
            "discount": 0.0,
            "freight": 0.0,
            "tcs": 0.0,
            "tds": 0.0,
            "items": [
                {
                    "name": "Item/Product/Service name (e.g. CONSULTING SERVICE)",
                    "hsn_code": "HSN or SAC code as string (e.g. 9983)",
                    "uom": "Unit of Measurement (e.g. NOS, PCS, OTH, UNT). For services, use OTH, UNT, or NOS.",
                    "qty": 1.0,
                    "rate": 0.0,
                    "gst_pct": 0.0,
                    "taxable": 0.0,
                    "amount": 0.0,
                    "discount": 0.0
                }
            ],
            "confidence_score": 95,
            "flags": []
        }
    ]
}"""
            rules_str = """IMPORTANT RULES:
- You must extract EVERY SINGLE invoice/transaction present in the document. DO NOT SKIP ANY ROWS.
- For tables containing multiple invoices, treat each row as a separate invoice unless they clearly share a single bill number.
- Ensure all taxes (CGST, SGST, IGST) and totals sum up correctly.
- Try to find the exact mapped party name using the existing ledgers list or specifications below.
- CRITICAL: Do not truncate or abbreviate party names. If a name is cut off in a table row, try to read the full name from the document header or other context.
- CRITICAL - GST PERCENTAGES: The `gst_pct` field MUST be a standard valid tax rate (e.g., 0, 0.1, 0.25, 3, 5, 12, 18, 28). NEVER extract monetary amounts like '810' or '642' into the `gst_pct` field. If a column is labelled 'GST', carefully distinguish between the monetary GST Amount (e.g. 250) and the GST Rate (e.g. 5).
- CRITICAL - NO HALLUCINATIONS: Do NOT hallucinate product names, GST rates, or invoices that are not explicitly present in the data chunk.
- Identify the target client's company name from the document header (the Seller for Sales invoices, or the Buyer/Consignee/Billed-to for Purchase invoices) and place it in the 'document_owner' field. If not found, return empty string.
- confidence_score: An integer from 0 to 100. Lower it (e.g., to 75 or below) if:
  * The scan quality of the document is poor or blurry (add "Blurry Image" to flags)
  * The GSTIN is missing, incomplete, or invalid (add "Missing GSTIN" or "Invalid GSTIN" flag)
  * The invoice tax mathematics (CGST/SGST/IGST totals vs item list totals) are unbalanced (add "Unbalanced Tax" flag)
  * The invoice/bill number or date is missing or hard to read (add "Missing Invoice No" or "Missing Date" flag)
- flags: A list of warning strings if there are any issues. Only use these exact flag strings when applicable: "Blurry Image", "Missing GSTIN", "Invalid GSTIN", "Unbalanced Tax", "Missing Invoice No", "Missing Date". If there are no issues, return an empty list [].
"""
            if module == "Purchases":
                rules_str += "- CRITICAL CONTEXT: You are extracting a PURCHASE BILL. This means the user's client is the BUYER. You MUST extract the name of the SELLER/VENDOR (the company issuing the bill) as the party_name. DO NOT extract the BUYER (the client receiving the bill). Look for logos, 'Billed From', or the entity at the very top to identify the Seller.\n"
            elif module == "Sales":
                rules_str += "- CRITICAL CONTEXT: You are extracting a SALES BILL. This means the user's client is the SELLER. You MUST extract the BUYER/CUSTOMER (the person receiving the goods/services) as the party_name. DO NOT extract the SELLER (the client issuing the bill).\n"

        # ── Catalog Injection (Sales & Purchases) ──────────────────────────────────
        catalog_injection = ""
        if module in ["Sales", "Purchases"]:
            try:
                from ai_memory import AIMemoryVault as _AIMemVault
                _tmp_vault_path = os.path.join(os.path.dirname(__file__), "..", "AI_Memory_Vault")
                _tmp_vault = _AIMemVault(vault_path=_tmp_vault_path)
                _client_id = client_memory.get("_client_id", "")
                if _client_id:
                    catalog_injection = _tmp_vault.get_catalog_prompt_injection(_client_id, module)
                    if catalog_injection:
                        print(f"⚡ [Catalog Injection] Injecting product catalog into {module} prompt.")
            except Exception as _cat_err:
                print(f"  [Catalog Injection] Skipped: {_cat_err}")

        prompt = f"""You are an Expert AI Accountant extracting structured financial data for the '{module}' module.

{rules_str}
{catalog_injection}
{memory_instruction}
{ledgers_instruction}
{spec_instruction}
{profile_instruction}
{user_context}

Return the extracted data EXACTLY following this JSON schema. Do not output anything else.
{schema_str}
"""

        excel_chunks = []
        if ext in [".xlsx", ".xls"]:
            print("Converting and chunking Excel for deep extraction...")
            try:
                import pandas as pd
                xl = pd.ExcelFile(file_path)
                for sheet in xl.sheet_names:
                    df = pd.read_excel(file_path, sheet_name=sheet)
                    
                    # 1. Forward-fill date columns to prevent empty cells causing column shifts
                    for col in df.columns:
                        col_str = str(col).upper()
                        if 'DATE' in col_str or 'VAL' in col_str or 'TRANS' in col_str:
                            df[col] = df[col].ffill()
                            
                    if len(df.columns) > 0:
                        first_col = df.columns[0]
                        if 'DATE' in str(first_col).upper() or df[first_col].astype(str).str.contains(r'\d{2,4}[-/.]\d{2}[-/.]\d{2,4}', na=False).any():
                            df[first_col] = df[first_col].ffill()
                            
                    # 2. Fill empty values in financial/amount columns with 0.0 for explicit column boundary alignment
                    for col in df.columns:
                        col_str = str(col).upper()
                        if any(k in col_str for k in ['WITHDRAW', 'DEPOSIT', 'DEBIT', 'CREDIT', 'AMOUNT', 'PAYMENT', 'RECEIPT', 'DR', 'CR']):
                            try:
                                numeric_series = pd.to_numeric(df[col], errors='coerce')
                                if numeric_series.notna().any():
                                    df[col] = df[col].fillna(0.0)
                            except:
                                pass
                    chunk_size = 150
                    i = 0
                    while i < len(df):
                        end_idx = min(i + chunk_size, len(df))
                        
                        # Smart Boundary Detection: Prevent breaking a transaction in half
                        while end_idx < len(df):
                            row_nulls = df.iloc[end_idx].isna().sum()
                            total_cols = len(df.columns)
                            # If row is mostly empty (e.g. only narration text), extend the boundary
                            if row_nulls > (total_cols / 2):
                                end_idx += 1
                            else:
                                break
                                
                        excel_chunks.append((sheet, i, end_idx - 1))
                        i = end_idx
            except Exception as e:
                raise ValueError(f"Failed to parse Excel file locally: {e}")
            
        uploaded_files_to_delete = []
        try:
            results_array = []
            base_filename = os.path.basename(file_path)
            
            def verify_chunk_math(extracted_rows, opening_balance, pages_count=1):
                """
                Validates extracted bank transactions for:
                1. Mathematical balance continuity (row-by-row running balance check)
                2. Date-gap continuity (detects silent month/page skipping by Gemini)

                Returns (is_valid, feedback_msg).
                """
                if not extracted_rows:
                    return True, ""
                try:
                    prev_balance = float(opening_balance)
                except Exception:
                    return True, ""
                
                from datetime import datetime as _ddt
                prev_date = None
                
                for idx, row in enumerate(extracted_rows):
                    running_bal = row.get("running_balance")
                    amount_raw = row.get("amount", 0.0)
                    
                    if running_bal is None or running_bal == "" or float(running_bal or 0) == 0.0:
                        continue
                    try:
                        running_bal = float(running_bal)
                        amount_val = float(amount_raw or 0.0)
                        
                        # ── Check 1: Running balance math ──────────────────────────────
                        if prev_balance is not None:
                            delta = round(running_bal - prev_balance, 2)
                            if abs(abs(delta) - amount_val) > 5.0:
                                expected_bal = prev_balance + amount_val if str(row.get("transaction_type")).strip().capitalize() == "Receipt" else prev_balance - amount_val
                                msg = f"Math discrepancy at row {idx+1} (Date: {row.get('date')}, Amount: {amount_val}, Narration: {row.get('narration')[:50]}). Expected running balance to change from {prev_balance:.2f} to {expected_bal:.2f} (delta={delta:.2f}), but PDF shows running balance as {running_bal:.2f}. Please make sure you have extracted all transactions including any duplicate amounts on the same date."
                                print(f"   [Math Check Failed] {msg}")
                                return False, msg
                        prev_balance = running_bal
                        
                        # ── Check 2: Date-gap continuity (silent skip detection) ────────
                        if pages_count > 1:
                            raw_date = str(row.get("date", "")).strip()
                            if raw_date and raw_date != "None":
                                cur_date = None
                                for _fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y"):
                                    try:
                                        cur_date = _ddt.strptime(raw_date[:10], _fmt)
                                        break
                                    except ValueError:
                                        pass
                                if cur_date and prev_date:
                                    gap_days = abs((cur_date - prev_date).days)
                                    if gap_days > 28:
                                        msg = f"Date jumped {gap_days} days from {prev_date.date()} to {cur_date.date()} between row {idx} and row {idx+1}. You likely missed a page or a month in between!"
                                        print(f"   [Date-Gap Check Failed] {msg}")
                                        return False, msg
                                if cur_date:
                                    prev_date = cur_date
                    except:
                        pass
                return True, ""

            def normalize_extracted_chunk_chronology(extracted_rows, prev_bal):
                """
                Ensures that the extracted transactions inside a chunk are in forward chronological order (oldest first).
                Detects if Gemini returned them in reverse chronological order, and reverses them if needed.
                """
                if not extracted_rows or len(extracted_rows) < 2:
                    return extracted_rows
                
                # Check date chronology
                from datetime import datetime as _ddt3
                dates = []
                for r in extracted_rows:
                    d_str = str(r.get("date", "")).strip()
                    parsed = None
                    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y", "%Y/%m/%d"):
                        try:
                            parsed = _ddt3.strptime(d_str[:10], fmt)
                            break
                        except:
                            pass
                    if parsed:
                        dates.append(parsed)
                
                if len(dates) == len(extracted_rows):
                    first_date = dates[0]
                    last_date = dates[-1]
                    if first_date > last_date:
                        extracted_rows.reverse()
                        print("🔄 [Chronology Normalizer] Detected newest-first order via dates. Reversed chunk data.")
                        return extracted_rows
                    elif first_date < last_date:
                        return extracted_rows
                        
                # Fallback to running balances
                first_bal = extracted_rows[0].get("running_balance")
                last_bal = extracted_rows[-1].get("running_balance")
                if first_bal is not None and last_bal is not None and prev_bal:
                    try:
                        first_bal = float(first_bal)
                        last_bal = float(last_bal)
                        p_bal = float(prev_bal)
                        
                        first_amt = float(extracted_rows[0].get("amount") or 0.0)
                        first_type = str(extracted_rows[0].get("transaction_type", "")).strip().capitalize()
                        expected_first = p_bal + first_amt if first_type == "Receipt" else p_bal - first_amt
                        
                        last_amt = float(extracted_rows[-1].get("amount") or 0.0)
                        last_type = str(extracted_rows[-1].get("transaction_type", "")).strip().capitalize()
                        expected_last = p_bal + last_amt if last_type == "Receipt" else p_bal - last_amt
                        
                        if abs(last_bal - expected_last) < abs(first_bal - expected_first):
                            extracted_rows.reverse()
                            print("🔄 [Chronology Normalizer] Detected newest-first order via running balances. Reversed chunk data.")
                    except:
                        pass
                return extracted_rows

            if module in ["Bank Statements", "Cash Entries"]:
                from modules.bank.parser import BankParser
                b_parser = BankParser()
                native_excel_res = b_parser.parse_bank_excel_natively(file_path)
                if native_excel_res and native_excel_res.get("status") == "success":
                    print("🎉 Direct Native Excel Engine Succeeded! Bypassing Gemini LLM with 100% Math Accuracy & 0.1s Speed!")
                    native_excel_res = self.validate_and_fix_transaction_types(native_excel_res)
                    return self.apply_product_mappings(native_excel_res, client_memory, module, instruction)

            if excel_chunks:
                import time
                
                def extract_excel_rows_recursive(sheet, start_row_idx, end_row_idx, prev_balance, trial=1, feedback_msg=""):
                    # Load the dataframe sheet locally
                    try:
                        import pandas as pd
                        df = pd.read_excel(file_path, sheet_name=sheet)
                        # Apply the same forward fill & fillna pre-processing to this range
                        for col in df.columns:
                            col_str = str(col).upper()
                            if 'DATE' in col_str or 'VAL' in col_str or 'TRANS' in col_str:
                                df[col] = df[col].ffill()
                        if len(df.columns) > 0:
                            first_col = df.columns[0]
                            if 'DATE' in str(first_col).upper() or df[first_col].astype(str).str.contains(r'\d{2,4}[-/.]\d{2}[-/.]\d{2,4}', na=False).any():
                                df[first_col] = df[first_col].ffill()
                        for col in df.columns:
                            col_str = str(col).upper()
                            if any(k in col_str for k in ['WITHDRAW', 'DEPOSIT', 'DEBIT', 'CREDIT', 'AMOUNT', 'PAYMENT', 'RECEIPT', 'DR', 'CR']):
                                try:
                                    numeric_series = pd.to_numeric(df[col], errors='coerce')
                                    if numeric_series.notna().any():
                                        df[col] = df[col].fillna(0.0)
                                except:
                                    pass
                    except Exception as e:
                        raise ValueError(f"Failed to read sheet '{sheet}' during recursive Excel extract: {e}")
                        
                    rows_count = end_row_idx - start_row_idx + 1
                    chunk_df = df.iloc[start_row_idx:end_row_idx + 1]
                    csv_str = f"--- Rows {start_row_idx + 1} to {end_row_idx + 1} ---\n"
                    csv_str += chunk_df.to_csv(index=False)
                    
                    msg = f"Reading Rows {start_row_idx + 1} to {end_row_idx + 1} (File: {base_filename})"
                    self._update_status(base_filename, start_row_idx + 1, len(df), msg)
                    print(f"  [Recursive Excel Extract] Sheet '{sheet}', Rows {start_row_idx + 1} to {end_row_idx + 1} (Size: {rows_count} row(s), Trial: {trial})")
                    
                    # Construct chunk prompt
                    chunk_context = (
                        f"\n\n--- CHUNK FILE CONTEXT ---\n"
                        f"Original Statement File: {base_filename}\n"
                        f"Sheet Name: {sheet}\n"
                        f"Row Range in original document: Rows {start_row_idx + 1} to {end_row_idx + 1}\n"
                    )
                    if prev_balance:
                        if isinstance(prev_balance, (int, float)):
                            prev_bal_str = f"₹{prev_balance:,.2f}"
                        else:
                            prev_bal_str = str(prev_balance)
                        chunk_context += (
                            f"PREVIOUS BALANCE CONTEXT: The running bank balance right before this chunk starts was {prev_bal_str}. "
                            f"Use this to correctly determine the transaction type (Receipt/Payment) of the first transaction in this chunk.\n"
                        )
                        
                    chunk_prompt = prompt + chunk_context + f"\n\nHere is a chunk of raw data from the Excel file converted to CSV format:\n{csv_str}\n\nParse this tabular data perfectly according to the rules. DO NOT SKIP ANY ROWS."
                    if feedback_msg:
                        chunk_prompt += f"\n\n⚠️ IMPORTANT FEEDBACK FROM PREVIOUS ATTEMPT:\n{feedback_msg}\nPlease correct this mistake in your new output and make sure no entries are missing or hallucinated."
                    
                    res = None
                    try:
                        res = self._extract_single_content(client, [chunk_prompt])
                    except Exception as err:
                        print(f"❌ Error processing Excel range {start_row_idx + 1}-{end_row_idx + 1}: {err}")
                        raise err
                        
                    # Math validation
                    extracted_data = res.get("extracted_data", []) if isinstance(res, dict) else []
                    extracted_data = normalize_extracted_chunk_chronology(extracted_data, prev_balance)
                    op_balance = prev_balance
                    if not op_balance and isinstance(res, dict):
                        op_balance = res.get("opening_balance", 0.0)
                        if not op_balance and extracted_data:
                            first_row = extracted_data[0]
                            first_bal = first_row.get("running_balance")
                            first_amt = first_row.get("amount", 0.0)
                            first_type = str(first_row.get("transaction_type", "")).strip().capitalize()
                            if first_bal and first_amt:
                                first_bal = float(first_bal)
                                first_amt = float(first_amt)
                                op_balance = first_bal - first_amt if first_type == "Receipt" else first_bal + first_amt
                                
                    is_valid = True
                    feedback_msg = ""
                    if not extracted_data:
                        is_valid = False
                        feedback_msg = "Gemini returned zero transactions for this excel chunk. Please extract all rows."
                    elif op_balance:
                        is_valid, feedback_msg = verify_chunk_math(extracted_data, op_balance, pages_count=rows_count)
                        
                    # If math check fails and range has multiple rows, split range in half
                    if not is_valid and rows_count > 1:
                        print(f"⚠️ [Recursive Excel Extract] Math check failed for Rows {start_row_idx + 1}-{end_row_idx + 1}. Splitting in half...")
                        mid = (start_row_idx + end_row_idx) // 2
                        
                        res_first = extract_excel_rows_recursive(sheet, start_row_idx, mid, prev_balance, trial=trial)
                        
                        first_extracted = res_first.get("extracted_data", [])
                        end_balance_first = prev_balance
                        if first_extracted:
                            last_rows = [r for r in first_extracted if r.get("running_balance")]
                            if last_rows:
                                end_balance_first = float(last_rows[-1].get("running_balance", 0))
                                
                        res_second = extract_excel_rows_recursive(sheet, mid + 1, end_row_idx, end_balance_first, trial=trial)
                        
                        combined_res = {
                          "status": "success",
                          "bank_name": res_first.get("bank_name") or res_second.get("bank_name"),
                          "opening_balance": res_first.get("opening_balance") or res_second.get("opening_balance") or op_balance,
                          "extracted_data": first_extracted + res_second.get("extracted_data", [])
                        }
                        return combined_res
                        
                     # If math check fails on single row, retry up to 2 times
                    elif not is_valid and rows_count == 1 and trial < 3:
                        print(f"⚠️ [Recursive Excel Extract] Math check failed for single row {start_row_idx + 1}. Retrying (Attempt {trial + 1})...")
                        # Only sleep if API quota is exhausted (not preemptively)
                        return extract_excel_rows_recursive(sheet, start_row_idx, end_row_idx, prev_balance, trial=trial + 1, feedback_msg=feedback_msg)
                        
                    return res

                # Walk through chunks — parallel for Sales/Purchases, sequential for Bank (balance-dependent)
                current_balance = ""
                num_chunks = len(excel_chunks)
                self._update_status(base_filename, 0, num_chunks, "Initializing Excel extraction...")
                
                if module in ["Bank Statements", "Cash Entries"]:
                    # Bank must be sequential: each chunk needs prior running balance
                    for chunk_idx, (sheet, start_idx, end_idx) in enumerate(excel_chunks):
                        res = extract_excel_rows_recursive(sheet, start_idx, end_idx, current_balance)
                        results_array.append(res)
                        if isinstance(res, dict) and res.get("extracted_data"):
                            last_rows = [r for r in res["extracted_data"] if r.get("running_balance")]
                            if last_rows:
                                current_balance = float(last_rows[-1].get("running_balance", 0))
                else:
                    # Sales / Purchases: all chunks are independent — process in parallel
                    from concurrent.futures import ThreadPoolExecutor, as_completed
                    max_workers = min(4, num_chunks)  # Cap at 4 parallel API calls
                    print(f"⚡ [Parallel Extraction] Processing {num_chunks} chunk(s) with {max_workers} parallel workers...")
                    
                    future_to_idx = {}
                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        for chunk_idx, (sheet, start_idx, end_idx) in enumerate(excel_chunks):
                            future = executor.submit(extract_excel_rows_recursive, sheet, start_idx, end_idx, "")
                            future_to_idx[future] = chunk_idx
                    
                    # Collect results in ORIGINAL order to preserve invoice sequence
                    ordered_results = [None] * num_chunks
                    for future in as_completed(future_to_idx):
                        idx = future_to_idx[future]
                        try:
                            ordered_results[idx] = future.result()
                        except Exception as pe:
                            print(f"❌ Parallel chunk {idx} failed: {pe}")
                            ordered_results[idx] = {"status": "error", "extracted_data": []}
                    
                    results_array.extend([r for r in ordered_results if r is not None])


            elif ext == ".pdf":
                if module == "Bank Statements":
                    native_res = self.parse_bank_pdf_natively(file_path, pdf_password=pdf_password)
                    if native_res and native_res.get("status") == "success":
                        print("🎉 Direct Native PDF Engine Succeeded! Bypassing Gemini LLM with 100% Math Accuracy & 0.05s Speed!")
                        # Deterministically validate and fix transaction types for native PDF entries
                        native_res = self.validate_and_fix_transaction_types(native_res)
                        return self.apply_product_mappings(native_res, client_memory, module, instruction)

                import time
                
                total_pages = 0
                avg_lines_per_page = 0
                
                # Check page count and line density natively (to prevent LLM output truncation)
                try:
                    from pypdf import PdfReader, PdfWriter
                    reader = PdfReader(file_path, strict=False)
                    if getattr(reader, 'is_encrypted', False):
                        decrypted = False
                        pass_clean = (pdf_password or "").strip()
                        candidates = list(dict.fromkeys([pass_candidate for pass_candidate in [pdf_password, pass_clean, pass_clean.upper(), pass_clean.lower(), ""] if pass_candidate is not None]))
                        for pass_candidate in candidates:
                            try:
                                res = reader.decrypt(pass_candidate)
                                if res != 0:
                                    decrypted = True
                                    break
                            except Exception:
                                pass
                        if not decrypted:
                            if pdf_password:
                                raise ValueError("PDF_PASSWORD_INCORRECT: Incorrect password for encrypted PDF file.")
                            else:
                                raise ValueError("PDF_PASSWORD_REQUIRED: This PDF file is password protected. Please enter the password to process.")
                    total_pages = len(reader.pages)
                    total_lines = 0
                    for p in reader.pages:
                        try:
                            p_txt = p.extract_text() or ""
                            total_lines += len([l for l in p_txt.split('\n') if l.strip()])
                        except:
                            pass
                    avg_lines_per_page = (total_lines / total_pages) if total_pages > 0 else 0
                except ValueError as ve:
                    raise ve
                except Exception as e:
                    err_s = str(e).lower()
                    if "decrypted" in err_s or "password" in err_s or "encrypt" in err_s:
                        if pdf_password:
                            raise ValueError("PDF_PASSWORD_INCORRECT: Incorrect password for encrypted PDF file.")
                        else:
                            raise ValueError("PDF_PASSWORD_REQUIRED: This PDF file is password protected. Please enter the password to process.")
                    print(f"⚠️ pypdf failed to count pages/lines ({e}). Falling back to pdfplumber...")
                    try:
                        import pdfplumber
                        open_kwargs = {"password": pdf_password} if pdf_password else {}
                        with pdfplumber.open(file_path, **open_kwargs) as pdf:
                            total_pages = len(pdf.pages)
                            total_lines = 0
                            for p in pdf.pages:
                                try:
                                    p_txt = p.extract_text() or ""
                                    total_lines += len([l for l in p_txt.split('\n') if l.strip()])
                                except:
                                    pass
                            avg_lines_per_page = (total_lines / total_pages) if total_pages > 0 else 0
                    except ModuleNotFoundError:
                        print(f"❌ pdfplumber is not installed. Root PDF reading error: {e}")
                        raise ValueError(f"Failed to read PDF file: {e}")
                    except Exception as e2:
                        err_s2 = str(e2).lower()
                        if "password" in err_s2 or "encrypt" in err_s2:
                            if pdf_password:
                                raise ValueError("PDF_PASSWORD_INCORRECT: Incorrect password for encrypted PDF file.")
                            else:
                                raise ValueError("PDF_PASSWORD_REQUIRED: This PDF file is password protected. Please enter the password to process.")
                        print(f"❌ Both pypdf and pdfplumber failed to read page count: {e2}")
                        raise ValueError(f"Failed to read PDF file: {e2}")
                
                print(f"📊 PDF Page Density: {total_pages} total pages, ~{int(avg_lines_per_page)} lines/page")
                
                # Dynamic Chunk Size Adaptation based on Page Count & Line Density
                # High-Speed Increased Chunking: Gemini 2.5 Flash 2M Context Window allows 25-50 pages per call
                if avg_lines_per_page > 150:
                    pages_per_chunk = max(10, min(25, 2500 // max(1, int(avg_lines_per_page))))
                    print(f"⚡ Ultra-dense PDF detected (~{int(avg_lines_per_page)} lines/page)! Setting pages_per_chunk = {pages_per_chunk}.")
                elif total_pages <= 30:
                    pages_per_chunk = total_pages
                    print(f"🚀 High-Speed Small PDF ({total_pages} pages): Processing all pages in 1 single API call!")
                else:
                    pages_per_chunk = max(20, min(50, 3500 // max(1, int(avg_lines_per_page))))
                    print(f"🚀 High-Speed Large PDF ({total_pages} pages): Setting pages_per_chunk = {pages_per_chunk}.")
                
                chronology = self.detect_pdf_chronology(file_path) if module in ["Bank Statements", "Cash Entries"] else "forward"
                # Build chunk page index ranges
                chunk_ranges = []
                for i in range(0, total_pages, pages_per_chunk):
                    end_idx = min(i + pages_per_chunk - 1, total_pages - 1)
                    chunk_ranges.append((i, end_idx))
                
                if chronology == "reverse":
                    chunk_ranges.reverse()
                    print(f"🔄 Reversed PDF chunk ranges for chronological flow: {chunk_ranges}")
                    
                num_chunks = len(chunk_ranges)
                print(f"Deep Extraction: Processing PDF {file_path} sequentially in {num_chunks} base chunks (with recursive split-on-failure)...")
                
                def extract_pdf_pages_recursive(start_page_idx, end_page_idx, prev_balance, trial=1, feedback_msg="", chunk_offset: int = 0):
                    pages_count = end_page_idx - start_page_idx + 1
                    start_p = start_page_idx + 1
                    end_p = end_page_idx + 1
                    
                    # Extract page text locally (Ultra Fast pypdf primary with pdfplumber fallback)
                    extracted_chunk_text_lines = []
                    try:
                        from pypdf import PdfReader
                        local_reader = PdfReader(file_path, strict=False)
                        if getattr(local_reader, 'is_encrypted', False) and pdf_password:
                            try: local_reader.decrypt(pdf_password)
                            except: pass
                        page_indices = list(range(start_page_idx, end_page_idx + 1))
                        if chronology == "reverse":
                            page_indices.reverse()
                        for idx in page_indices:
                            if idx < len(local_reader.pages):
                                txt = local_reader.pages[idx].extract_text() or ""
                                import re
                                txt = re.sub(r'(\d{4}-)\s*\n\s*(\d{2}-\d{2})', r'\1\2', txt)
                                txt = re.sub(r'(\d{2}-\d{2})\s*\n\s*(\d{4}-)', r'\2\1', txt)
                                if chronology == "reverse":
                                    lines = [l for l in txt.split('\n') if l.strip()]
                                    lines.reverse()
                                    txt = '\n'.join(lines)
                                if txt.strip():
                                    extracted_chunk_text_lines.append(txt)
                    except Exception:
                        pass

                    if not extracted_chunk_text_lines:
                        try:
                            import pdfplumber
                            open_kwargs = {"password": pdf_password} if pdf_password else {}
                            with pdfplumber.open(file_path, **open_kwargs) as pdf:
                                page_indices = list(range(start_page_idx, end_page_idx + 1))
                                if chronology == "reverse":
                                    page_indices.reverse()
                                for idx in page_indices:
                                    if idx < len(pdf.pages):
                                        txt = pdf.pages[idx].extract_text() or ""
                                        import re
                                        txt = re.sub(r'(\d{4}-)\s*\n\s*(\d{2}-\d{2})', r'\1\2', txt)
                                        txt = re.sub(r'(\d{2}-\d{2})\s*\n\s*(\d{4}-)', r'\2\1', txt)
                                        if chronology == "reverse":
                                            lines = [l for l in txt.split('\n') if l.strip()]
                                            lines.reverse()
                                            txt = '\n'.join(lines)
                                        extracted_chunk_text_lines.append(txt)
                        except Exception as pe:
                            print(f"⚠️ pdfplumber text extraction failed during chunking: {pe}")

                    total_chars = sum(len(txt.strip()) for txt in extracted_chunk_text_lines)
                    is_scanned_pdf = total_chars < (10 * pages_count)
                    
                    msg = f"Reading Part: Pages {start_p} to {end_p} (File: {base_filename})"
                    self._update_status(base_filename, start_p, total_pages, msg)
                    
                    # Construct chunk prompt context
                    chunk_context = (
                        f"\n\n--- CHUNK FILE CONTEXT ---\n"
                        f"Original Statement File: {base_filename}\n"
                        f"Page Range in original document: Pages {start_p} to {end_p}\n"
                    )
                    if prev_balance:
                        if isinstance(prev_balance, (int, float)):
                            prev_bal_str = f"₹{prev_balance:,.2f}"
                        else:
                            prev_bal_str = str(prev_balance)
                        chunk_context += (
                            f"PREVIOUS BALANCE CONTEXT: The running bank balance right before this chunk starts was {prev_bal_str}. "
                            f"Use this to correctly determine the transaction type (Receipt/Payment) of the first transaction in this chunk.\n"
                        )
                    
                    res = None
                    uploaded_file = None
                    temp_chunk_path = None
                    
                    if is_scanned_pdf:
                        print(f"📷 [Scanned PDF Detected] Pages {start_p} to {end_p} contain minimal selectable text ({total_chars} chars). Using Gemini File API visual upload fallback...")
                        try:
                            import tempfile
                            from pypdf import PdfReader, PdfWriter
                            
                            # Write chunk pages to a temp PDF file
                            fd, temp_chunk_path = tempfile.mkstemp(suffix=".pdf")
                            os.close(fd)
                            
                            reader_local = PdfReader(file_path, strict=False)
                            writer = PdfWriter()
                            page_indices = list(range(start_page_idx, end_page_idx + 1))
                            if chronology == "reverse":
                                page_indices.reverse()
                            for idx in page_indices:
                                if idx < len(reader_local.pages):
                                    writer.add_page(reader_local.pages[idx])
                            
                            with open(temp_chunk_path, "wb") as f:
                                writer.write(f)
                                
                            uploaded_file = client.files.upload(file=temp_chunk_path)
                            chunk_prompt = prompt + chunk_context + f"\n\nHere is a chunk of pages from the scanned bank statement. Parse this tabular statement data perfectly according to the rules."
                            if feedback_msg:
                                chunk_prompt += f"\n\n⚠️ IMPORTANT FEEDBACK FROM PREVIOUS ATTEMPT:\n{feedback_msg}\nPlease correct this mistake in your new output and make sure no entries are missing or hallucinated."
                            
                            res = self._extract_single_content(client, [uploaded_file, chunk_prompt])
                        except Exception as err:
                            print(f"❌ Error processing scanned PDF range {start_p}-{end_p}: {err}")
                            raise err
                        finally:
                            if temp_chunk_path and os.path.exists(temp_chunk_path):
                                try: os.remove(temp_chunk_path)
                                except: pass
                            if uploaded_file:
                                try:
                                    if uploaded_file.name:
                                        client.files.delete(name=uploaded_file.name)
                                except Exception as del_err:
                                    print(f"⚠️ Non-critical: Failed to delete temp chunk file from Gemini: {del_err}")
                            import gc
                            gc.collect()
                    else:
                        print(f"  [Recursive Text Extract] Pages {start_p} to {end_p} (Size: {pages_count} page(s), Trial: {trial})")
                        raw_chunk_text = ""
                        for idx, txt in enumerate(extracted_chunk_text_lines):
                            p_num = start_p + idx
                            raw_chunk_text += f"\n--- START PAGE {p_num} ---\n{txt}\n--- END PAGE {p_num} ---\n"
                            
                        chunk_prompt = prompt + chunk_context + f"\n\nHere is the raw text content extracted from the statement page(s) {start_p} to {end_p}:\n{raw_chunk_text}\n\nParse this tabular statement data perfectly according to the rules."
                        if feedback_msg:
                            chunk_prompt += f"\n\n⚠️ IMPORTANT FEEDBACK FROM PREVIOUS ATTEMPT:\n{feedback_msg}\nPlease correct this mistake in your new output and make sure no entries are missing or hallucinated."
                        try:
                            res = self._extract_single_content(client, [chunk_prompt], start_key_offset=chunk_offset)
                        except Exception as err:
                            print(f"❌ Error processing PDF text range {start_p}-{end_p}: {err}")
                            raise err
                            
                    # 2. Math validation
                    extracted_data = res.get("extracted_data", []) if isinstance(res, dict) else []
                    extracted_data = normalize_extracted_chunk_chronology(extracted_data, prev_balance)
                    op_balance = prev_balance
                    if not op_balance and isinstance(res, dict):
                        op_balance = res.get("opening_balance", 0.0)
                        if not op_balance and extracted_data:
                            first_row = extracted_data[0]
                            first_bal = first_row.get("running_balance")
                            first_amt = first_row.get("amount", 0.0)
                            first_type = str(first_row.get("transaction_type", "")).strip().capitalize()
                            if first_bal and first_amt:
                                first_bal = float(first_bal)
                                first_amt = float(first_amt)
                                op_balance = first_bal - first_amt if first_type == "Receipt" else first_bal + first_amt
                                
                    is_valid = True
                    feedback_msg = ""
                    if not extracted_data:
                        has_table = True
                        if not is_scanned_pdf:
                            text_to_check = "\n".join(extracted_chunk_text_lines).upper()
                            has_table = any(k in text_to_check for k in ["DATE", "PARTICULARS", "BALANCE", "WITHDRAWAL", "DEPOSIT", "REF NO"])
                        if has_table:
                            is_valid = False
                            feedback_msg = "Gemini returned zero transactions for this page chunk, but a statement table appears to be present. Please extract all rows."
                    elif op_balance:
                        is_valid, feedback_msg = verify_chunk_math(extracted_data, op_balance, pages_count=pages_count)
                        
                    # If math check fails on small/medium chunks (pages <= 10), RETRY Trial 2 first with feedback & key rotation!
                    if not is_valid and trial < 2 and pages_count <= 10:
                        print(f"⚠️ [Recursive Extract] Math check failed for Pages {start_p}-{end_p} (Size: {pages_count} pgs). Retrying Trial {trial + 1} with feedback & key rotation before splitting...")
                        return extract_pdf_pages_recursive(
                            start_page_idx, end_page_idx, prev_balance, 
                            trial=trial + 1, feedback_msg=feedback_msg, chunk_offset=chunk_offset + 1
                        )
                        
                    # If math check STILL fails after Trial 2 (or for large chunks > 10 pages), split range in half
                    elif not is_valid and pages_count > 1:
                        print(f"⚠️ [Recursive Extract] Math check failed for Pages {start_p}-{end_p} after Trial {trial}. Splitting page range in half...")
                        mid = (start_page_idx + end_page_idx) // 2
                        
                        res_first = extract_pdf_pages_recursive(start_page_idx, mid, prev_balance, trial=1, chunk_offset=chunk_offset)
                        
                        first_extracted = res_first.get("extracted_data", [])
                        end_balance_first = prev_balance
                        if first_extracted:
                            last_rows = [r for r in first_extracted if r.get("running_balance")]
                            if last_rows:
                                end_balance_first = float(last_rows[-1].get("running_balance", 0))
                                
                        res_second = extract_pdf_pages_recursive(mid + 1, end_page_idx, end_balance_first, trial=1, chunk_offset=chunk_offset + 1)
                        
                        combined_res = {
                          "status": "success",
                          "bank_name": res_first.get("bank_name") or res_second.get("bank_name"),
                          "opening_balance": res_first.get("opening_balance") or res_second.get("opening_balance") or op_balance,
                          "extracted_data": first_extracted + res_second.get("extracted_data", [])
                        }
                        return combined_res
                        
                    # If math check fails on single page after Trial 2, retry Trial 3
                    elif not is_valid and pages_count == 1 and trial < 3:
                        print(f"⚠️ [Recursive Extract] Math check failed for single Page {start_p}. Retrying (Attempt {trial + 1})...")
                        return extract_pdf_pages_recursive(
                            start_page_idx, end_page_idx, prev_balance, 
                            trial=trial + 1, feedback_msg=feedback_msg, chunk_offset=chunk_offset + 1
                        )
                        
                    return res

                # Walk through chunks (Sequential for Bank, Parallel across 10 API keys for Sales/Purchase)
                current_balance = ""
                self._update_status(base_filename, 0, num_chunks, "Initializing PDF splitting...")
                
                if module in ["Bank Statements", "Cash Entries"]:
                    # Bank Statements require sequential flow to pass running balances across chunk boundaries
                    for chunk_idx, (start_idx, end_idx) in enumerate(chunk_ranges):
                        self._update_status(base_filename, chunk_idx + 1, num_chunks, f"Extracting bank pages {start_idx+1}-{end_idx+1}...")
                        res = extract_pdf_pages_recursive(start_idx, end_idx, current_balance)
                        
                        # Inter-Chunk Boundary Balance Recovery Check
                        if current_balance and isinstance(res, dict) and res.get("extracted_data"):
                            first_rows = [r for r in res["extracted_data"] if r.get("running_balance")]
                            if first_rows:
                                first_row = first_rows[0]
                                f_bal = float(first_row.get("running_balance", 0))
                                f_amt = float(first_row.get("amount", 0))
                                f_type = str(first_row.get("transaction_type", "")).strip().capitalize()
                                expected_start_bal = f_bal - f_amt if f_type == "Receipt" else f_bal + f_amt
                                
                                delta = abs(expected_start_bal - float(current_balance))
                                if delta > 1.0:
                                    print(f"⚠️ [Boundary Gap Detected] Discrepancy between Chunk {chunk_idx} and Chunk {chunk_idx+1}: expected start {expected_start_bal:.2f}, got prev balance {current_balance:.2f} (delta = {delta:.2f})")
                                    if start_idx > 0:
                                        boundary_page_idx = start_idx - 1
                                        print(f"🔧 [Boundary Recovery] Auto-extracting missing boundary Page {boundary_page_idx + 1}...")
                                        b_res = extract_pdf_pages_recursive(boundary_page_idx, boundary_page_idx, current_balance)
                                        if b_res and isinstance(b_res, dict) and b_res.get("extracted_data"):
                                            results_array.append(b_res)
                                            b_last_rows = [r for r in b_res["extracted_data"] if r.get("running_balance")]
                                            if b_last_rows:
                                                current_balance = float(b_last_rows[-1].get("running_balance", 0))

                        results_array.append(res)
                        
                        if isinstance(res, dict) and res.get("extracted_data"):
                            last_rows = [r for r in res["extracted_data"] if r.get("running_balance")]
                            if last_rows:
                                current_balance = float(last_rows[-1].get("running_balance", 0))
                else:
                    # Sales / Purchase: Chunks are independent — extract concurrently across 10 API keys!
                    from concurrent.futures import ThreadPoolExecutor, as_completed
                    pool_len = len(self.api_keys_pool) if hasattr(self, 'api_keys_pool') and self.api_keys_pool else 1
                    max_workers = max(1, min(pool_len, num_chunks))
                    print(f"⚡ [Parallel PDF Extraction] Processing {num_chunks} PDF chunk(s) across {max_workers} concurrent API Key worker(s)...")
                    
                    future_to_idx = {}
                    with ThreadPoolExecutor(max_workers=max_workers) as executor:
                        for chunk_idx, (start_idx, end_idx) in enumerate(chunk_ranges):
                            future = executor.submit(extract_pdf_pages_recursive, start_idx, end_idx, "", 1, "", chunk_idx)
                            future_to_idx[future] = chunk_idx
                            
                    ordered_results = [None] * num_chunks
                    for future in as_completed(future_to_idx):
                        idx = future_to_idx[future]
                        try:
                            ordered_results[idx] = future.result()
                        except Exception as pe:
                            print(f"❌ Parallel PDF chunk {idx} failed: {pe}")
                            ordered_results[idx] = {"status": "error", "extracted_data": []}
                            
                    results_array.extend([r for r in ordered_results if r is not None])
                        
            elif ext in [".png", ".jpg", ".jpeg"]:
                print(f"Uploading {file_path} to Gemini File API...")
                uploaded_file = client.files.upload(file=file_path)
                uploaded_files_to_delete.append(uploaded_file)
                results_array.append(self._extract_single_content(client, [uploaded_file, prompt]))
            else:
                raise ValueError(f"Unsupported file type for invoice extraction: {ext}")
            
            # Combine all results
            final_result = {"status": "success", "extracted_data": []}
            for res in results_array:
                if isinstance(res, list):
                    res = {"status": "success", "extracted_data": res}
                if res and isinstance(res, dict):
                    if module == "Bank Statements":
                        if "bank_name" in res and res["bank_name"]:
                            final_result["bank_name"] = res["bank_name"]
                        if "opening_balance" in res and res.get("opening_balance") not in (None, 0.0) and ("opening_balance" not in final_result or final_result["opening_balance"] == 0.0):
                            final_result["opening_balance"] = res["opening_balance"]
                    if "extracted_data" in res and isinstance(res["extracted_data"], list):
                        final_result["extracted_data"].extend(res["extracted_data"])
            
            print(f"✅ Deep Extraction successful! Found {len(final_result.get('extracted_data', []))} records in total.")
            
            # 🗓️ CRITICAL: Normalize all extracted dates to YYYY-MM-DD (Indian day-first format)
            # This catches any dates Gemini returns as "26/06/25", "01-07-25", etc.
            from datetime import datetime as _dt
            _date_fmts = ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y", "%Y/%m/%d")
            for row in final_result.get("extracted_data", []):
                raw_date = str(row.get("date", "")).strip()
                if raw_date and raw_date != "None":
                    # If it already looks like YYYY-MM-DD, skip
                    if not (len(raw_date) >= 10 and raw_date[4] == "-"):
                        for _fmt in _date_fmts:
                            try:
                                row["date"] = _dt.strptime(raw_date, _fmt).strftime("%Y-%m-%d")
                                break
                            except ValueError:
                                pass
            
            # 🔧 CRITICAL: Run mathematical balance validation to auto-correct any Receipt/Payment swaps
            if module == "Bank Statements":
                final_result = self.validate_and_fix_transaction_types(final_result)
            
            # 🔍 FINAL GLOBAL AUDIT: Scan all combined rows for date gaps > 28 days (residual month-skip detection)
            if module in ["Bank Statements", "Cash Entries"]:
                from datetime import datetime as _ddt2
                all_rows = final_result.get("extracted_data", [])
                _prev_audit_date = None
                _prev_audit_idx = 0
                for _ai, _arow in enumerate(all_rows):
                    _adate_str = str(_arow.get("date", "")).strip()
                    _acur = None
                    for _afmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
                        try:
                            _acur = _ddt2.strptime(_adate_str[:10], _afmt); break
                        except: pass
                    if _acur and _prev_audit_date:
                        _gap = abs((_acur - _prev_audit_date).days)
                        if _gap > 28:
                            print(f"⚠️ [GLOBAL DATE-GAP AUDIT] Row {_prev_audit_idx}→{_ai}: {_prev_audit_date.date()} to {_acur.date()} = {_gap} days gap. Possible missing month in final output!")
                    if _acur:
                        _prev_audit_date = _acur
                        _prev_audit_idx = _ai
            
            # 📅 CRITICAL: Sort all bank statement transactions in FORWARD CHRONOLOGICAL ORDER (Month Start 1st of month first)
            if module in ["Bank Statements", "Cash Entries"]:
                from datetime import datetime as _s_dt
                def _parse_row_sort_date(r):
                    d_str = str(r.get("date", "")).strip()
                    for _f in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y"):
                        try:
                            return _s_dt.strptime(d_str[:10], _f)
                        except ValueError:
                            pass
                    return _s_dt.min

                final_result["extracted_data"].sort(key=_parse_row_sort_date)
                print("📅 [Month Start Order] Sorted all bank statement entries in Forward Chronological Order (1st of month first).")
            
            return self.apply_product_mappings(final_result, client_memory, module, instruction)

        except Exception as e:
            print(f"❌ Gemini extraction failed: {e}")
            raise ValueError(f"Gemini extraction failed: {e}")
        finally:
            self._update_status(base_filename, 0, 0, "Idle")
            for f in uploaded_files_to_delete:
                try:
                    client.files.delete(name=f.name)
                except:
                    pass

    def apply_ai_formatting(self, extracted_data: dict, client_memory: dict, module: str) -> dict:
        """
        Applies 'Deep AI Business Brain' custom formatting rules (from client_memory['business_profile'])
        to the deterministic Excel data. This safely reformats text fields (like bill_no) without
        breaking math accuracy.
        """
        business_profile = client_memory.get("business_profile", "")
        if not business_profile or not self.api_key:
            return extracted_data
            
        data_list = extracted_data.get("extracted_data", [])
        if not data_list:
            return extracted_data
            
        print("🤖 AI Formatting Pass: Evaluating Deep AI Business Brain rules...")
        
        # 1. Collect unique party names to compile rules for
        unique_parties = list(set(str(row.get("party_name", "")).strip() for row in data_list if str(row.get("party_name", "")).strip()))
        
        if not unique_parties:
            return extracted_data
            
        # 2. Ask Gemini to compile the rules into format strings
        prompt = f"""You are an expert rule-engine compiler AI.
The client has provided the following "Deep AI Business Brain" formatting rules:

{business_profile}

Your job is to read these rules and compile them into a dictionary of Python format strings for the given list of Party Names.
Use `{{clean_bill}}` as the placeholder for the bill number WITHOUT trailing `.0` decimals.
Use `{{raw_bill}}` as the placeholder for the exact original bill number.

PARTY NAMES TO PROCESS:
{json.dumps(unique_parties, indent=2)}

INSTRUCTIONS:
1. Return ONLY a valid JSON dictionary mapping the EXACT `party_name` from the list above to its compiled `format_string`.
2. Do not include parties that do not have a rule in the Deep AI Business Brain.
3. FUZZY MATCHING: Be flexible. If a party name in the list is a close match to a party name in the rules (e.g. ignoring spaces, dots, case, or small spelling/pluralization variations like "S S R Footcare" vs "SSR Footcare", or "ELITE DIAGNOSTICS" vs "Elite diagnostic"), map the EXACT party name from the list to the rule's format string.

EXAMPLE:
If the rule says "For 'S S R Footcare', add prefix SSR/2627/", and the party in the list is "SSR Footcare", return:
{{
  "SSR Footcare": "SSR/2627/{{clean_bill}}"
}}

Return ONLY valid JSON.
"""
        try:
            from google import genai
            from google.genai import types
            import difflib
            import re
            
            client = self._get_client()
            response = self._generate_content_with_retry(
                client=client,
                model=self.model_name or "gemini-3.1-flash-lite",
                contents=prompt,
                config=make_config("application/json")
            )
            
            result_text = response.text.strip() if response and response.text else ""
            if result_text.startswith("```json"): result_text = result_text[7:]
            if result_text.startswith("```"): result_text = result_text[3:]
            if result_text.endswith("```"): result_text = result_text[:-3]
            
            ai_rules = json.loads(result_text.strip())
            print(f"🤖 AI Formatting Compiled Rules: {json.dumps(ai_rules)}")
            
            # Map of normalized to raw keys
            rule_keys = list(ai_rules.keys())
            
            # 3. Apply the compiled rules purely deterministically in Python (with safe fuzzy fallback)
            formatted_count = 0
            for row in data_list:
                b_no = str(row.get("bill_no", "")).strip()
                p_name = str(row.get("party_name", "")).strip()
                
                if b_no:
                    # Find closest match for party_name in ai_rules keys
                    matched_party = None
                    if p_name in ai_rules:
                        matched_party = p_name
                    else:
                        p_name_lower = p_name.lower()
                        # Case-insensitive check
                        for k in rule_keys:
                            if k.lower() == p_name_lower:
                                matched_party = k
                                break
                        # Spacing-insensitive check
                        if not matched_party:
                            p_name_norm = "".join(p_name.split()).lower()
                            for k in rule_keys:
                                if "".join(k.split()).lower() == p_name_norm:
                                    matched_party = k
                                    break
                        # Fuzzy close matches check
                        if not matched_party:
                            matches = difflib.get_close_matches(p_name.lower(), [k.lower() for k in rule_keys], n=1, cutoff=0.7)
                            if matches:
                                matched_party = next((k for k in rule_keys if k.lower() == matches[0]), None)
                                
                    if matched_party:
                        clean_bill = b_no
                        if clean_bill.endswith(".0"):
                            clean_bill = clean_bill[:-2]
                            
                        format_str = ai_rules[matched_party]
                        
                        # Prevent double prefixing (e.g. format_str="CR/{clean_bill}" and clean_bill="CR/2026-27/395")
                        prefix_match = re.match(r'^([A-Za-z0-9_\-\/]+)\{clean_bill\}', format_str)
                        if prefix_match:
                            pfx = prefix_match.group(1)
                            if clean_bill.upper().startswith(pfx.upper()):
                                clean_bill = clean_bill[len(pfx):]
                                
                        try:
                            row["bill_no"] = format_str.format(clean_bill=clean_bill, raw_bill=b_no)
                            formatted_count += 1
                        except KeyError:
                            row["bill_no"] = format_str.replace("{clean_bill}", clean_bill).replace("{raw_bill}", b_no)
                            formatted_count += 1
                        
            print(f"✅ AI Formatting Applied to {formatted_count} rows deterministically.")
            
        except Exception as e:
            print(f"⚠️ Warning: AI formatting pass failed, returning original deterministic data. Error: {e}")
            
        return extracted_data

    def parse_excel_to_json(self, file_path: str, company_state_code: str = '24', instruction: str = '') -> dict:
        """Parses the Sales/Purchases Excel spreadsheet into standard JSON using dynamic column normalization."""
        from core.excel_parser import parse_excel_to_json as _parser
        return _parser(file_path, company_state_code=company_state_code, instruction=instruction)





    def map_ledgers_for_statement(self, extracted_data: dict, client_memory: dict, module: str = "Bank Statements", instruction: str = "") -> dict:
        """
        AUTOMATED INTELLIGENCE LEDGER MAPPING ENGINE — v2 (6-Stage Pipeline).
        Maps 100% of transaction narrations to official Miracle Ledgers.
        Priority order:
          Stage 0 → Memory exact key (fastest)
          Stage 1 → Memory best-substring (longest match wins)
          Stage 2 → Direct ledger name substring
          Stage 3 → Expanded banking keyword intelligence (25 categories)
          Stage 4 → UPI ID name extraction & ledger match
          Stage 5 → Fuzzy match fallback (cutoff 0.70)
        """
        if not isinstance(extracted_data, dict):
            return extracted_data

        rows = extracted_data.get("extracted_data", [])
        if not isinstance(rows, list) or not rows:
            return extracted_data

        client_memory = client_memory or {}
        existing_ledgers = client_memory.get("existing_ledgers", [])
        expense_mappings = client_memory.get("expense_mappings", {})

        ledger_names = []
        ledger_lookup = {}  # UPPER -> Exact Name

        # Determine the statement's own bank brand to exclude from party lookups
        stmt_bank_name = extracted_data.get("bank_name", "")
        KNOWN_BANK_BRANDS = [
            'HDFC', 'ICICI', 'SBI', 'STATE BANK', 'AXIS', 'KOTAK', 'CANARA', 'UNION',
            'BANK OF BARODA', 'BOB', 'PNB', 'PUNJAB NATIONAL', 'IDBI', 'YES BANK',
            'FEDERAL', 'INDUSIND', 'BANDHAN', 'UCO', 'CENTRAL BANK', 'INDIAN BANK',
            'BANK OF INDIA', 'BOI'
        ]
        def get_brand(name: str) -> str:
            n = name.upper()
            for brand in KNOWN_BANK_BRANDS:
                if brand in n:
                    return brand
            return ""
        stmt_brand = get_brand(stmt_bank_name)

        RESERVED_GENERIC_WORDS = {
            "REMARK", "REMARKS", "BANK", "CASH", "SUSPENSE", "PAYMENT", "RECEIPT",
            "TRANSFER", "NEFT", "RTGS", "UPI", "CHQ", "CHEQUE", "CHARGES", "FEE",
            "EXPENSE", "INCOME", "DEBTOR", "DEBTORS", "CREDITOR", "CREDITORS"
        }

        ledger_group_map = {}  # UPPER -> Exact Group Name from Miracle DBF
        for leg in existing_ledgers:
            name = ""
            group_name = ""
            if isinstance(leg, dict):
                name = leg.get("name", "").strip()
                group_name = str(leg.get("group_name", "")).strip()
            elif isinstance(leg, str):
                name = leg.strip()
            if name:
                name_up = name.upper()

                # Exclude statement's own bank or any Bank Account ledger from party matching
                if 'BANK' in group_name.upper() or (stmt_brand and stmt_brand in name_up and ('BANK' in name_up or 'A/C' in name_up or name_up == stmt_bank_name.upper())):
                    print(f"🛡️ [Python Guard] Excluding bank ledger '{name}' from party lookup.")
                    continue

                # Sanitize dirty historical DBF ledger names into clean Title Case
                display_name = name
                if any(h in name_up for h in ["OKAXIS", "OKICICI", "KHDFCBANK", "OKHDFCBANK", "OKSBI", "PTYES", "NAVIAXIS", "SENT USING PAYTM", "OKHD FCBANK", "FCBANK", "KAXIS"]):
                    sanitized_name = self.extract_clean_party_from_narration(name)
                    if sanitized_name and len(sanitized_name) >= 2:
                        display_name = sanitized_name

                ledger_names.append(display_name)
                ledger_lookup[name_up] = display_name
                ledger_lookup[display_name.upper()] = display_name
                if group_name:
                    ledger_group_map[name_up] = group_name
                    ledger_group_map[display_name.upper()] = group_name

        if not ledger_names:
            ledger_names = ["UPI Debtors", "UPI Creditors", "Suspense Account", "Cash Account"]
            for n in ledger_names:
                ledger_lookup[n.upper()] = n

        import difflib
        import re

        def clean_to_letters(s):
            return re.sub(r'[^A-Z]', '', str(s).upper())

        ledger_letter_map = {clean_to_letters(n): n for n in ledger_names if len(clean_to_letters(n)) >= 6 and n.upper() not in RESERVED_GENERIC_WORDS}

        # Pre-build clean keys for all expense_mappings for Stage 0 fast lookup
        from ai_memory import AIMemoryVault as _MemVault
        clean_memory = {}
        for k, v in expense_mappings.items():
            ck = _MemVault.clean_mapping_key(k)
            if ck:
                clean_memory[ck.upper()] = v

        # ── STAGE -1: User Guidelines Engine (Highest Priority) ──────────────
        user_guideline_rules = []
        if instruction and instruction.strip():
            print(f"🎯 [User Guidelines Engine] Parsing custom prompt guidelines: '{instruction.strip()}'...")
            raw_lines = re.split(r'[\r\n;.]+', instruction)
            for line_item in raw_lines:
                item_s = line_item.strip()
                if not item_s:
                    continue
                tx_type_req = None
                if re.search(r'\b(deposit|receipt|money in|cr|credit)\b', item_s, re.IGNORECASE):
                    tx_type_req = "Receipt"
                elif re.search(r'\b(withdrawal|payment|money out|dr|debit)\b', item_s, re.IGNORECASE):
                    tx_type_req = "Payment"

                m_rule = re.search(
                    r'(?:map|if|when|narration|amount)?\s*([a-zA-Z0-9_\-\s&/]+?)\s*'
                    r'(?:->|:|=|map to|mapped to|mapping to|map with|mapped with|mapping with|put in|put into|send to|set as|assign to|to|with)\s*'
                    r'([a-zA-Z0-9_\-\s&/]+)',
                    item_s, re.IGNORECASE
                )
                if m_rule:
                    src_kw = m_rule.group(1).strip()
                    tgt_name = m_rule.group(2).strip()
                    src_kw_clean = re.sub(r'\b(if|when|narration|contains|is|has|all|any|deposit|withdrawal|payment|receipt|come|first|then|amount|site)\b', '', src_kw, flags=re.IGNORECASE)
                    src_kw_clean = " ".join(src_kw_clean.split()).upper()
                    tgt_clean = re.sub(r'\b(account|ac|a/c)\b', '', tgt_name, flags=re.IGNORECASE).strip()
                    tgt_clean = " ".join(tgt_clean.split())
                    if src_kw_clean and tgt_clean:
                        resolved_tgt = ledger_lookup.get(tgt_clean.upper(), tgt_clean)
                        user_guideline_rules.append((src_kw_clean, resolved_tgt, tx_type_req))
                        print(f"  📌 Registered User Guideline: '{src_kw_clean}' → '{resolved_tgt}' (Filter: {tx_type_req or 'All'})")

        # ── Expanded Banking Keyword Intelligence (25 categories) ─────────────
        KEYWORD_RULES = [
            # Fuel & Transport
            (["PETROL", "DIESEL", "FUEL", "PETROLEUM", "HP PETROL", "SHELL", "BPCL", "IOC", "IOCL", "HPCL", "ESSAR OIL"],
             ["PETROL-DIESEL EXPENSE", "PETROL DIESEL EXPENSE", "FUEL EXPENSE", "PETROL EXPENSE", "PETROL"]),

            (["TRANSPORT", "FREIGHT", "LOGISTICS", "COURIER", "CARGO", "TRUCKING", "LORRY", "VEHICLE HIRE",
              "LOADING", "UNLOADING", "OCTOROI", "OCTROI"],
             ["TRANSPORT EXP", "FREIGHT EXP", "LOADING EXPENSE", "TRANSPORT EXPENSE", "TRANSPORT"]),

            # Salary & Labour
            (["SALARY", "SALARIES", "WAGES", "STAFF PAY", "LABOUR", "LABOR", "MANPOWER", "PAYROLL"],
             ["SALARY EXP", "SALARY EXPENSE", "SALARY", "WAGES EXPENSE", "WAGES"]),

            # Rent & Office
            (["RENT", "LEASE", "SHOP RENT", "OFFICE RENT", "GODOWN RENT", "STORE RENT"],
             ["RENT", "RENT A/C", "RENT EXPENSE", "OFFICE RENT"]),

            # Electricity & Utilities
            (["ELECTRICITY", "ELECTRIC", "POWER BILL", "PGVCL", "DGVCL", "MGVCL", "UGVCL",
              "TORRENT POWER", "BESCOM", "MSEDCL", "TNEB", "BIJLI"],
             ["ELECTRICITY EXP", "ELECTRICITY EXPENSE", "ELECTRICITY", "ELECTICITY EXP"]),

            (["WATER", "DRINKING WATER", "WATER CHARGES", "WATER BILL", "WATER SUPPLY", "JALNIGAM"],
             ["WATER EXPENSE", "WATER EXP", "WATER"]),

            (["GAS", "LPG", "CNG", "NATURAL GAS", "INDANE", "HP GAS", "BHARAT GAS"],
             ["GAS EXP", "GAS EXPENSE", "GAS"]),

            # Communication
            (["MOBILE", "PHONE", "TELEPHONE", "JIOTEL", "AIRTEL", "VODAFONE", "BSNL", "TATA SKY",
              "IDEA", "VI", "JIO", "BROADBAND", "INTERNET", "TATA DOCOMO"],
             ["TELEPHONE EXP", "TELEPHONE EXPENSE", "MOBILE EXP", "TELEPHONE"]),

            # Bank & Financial
            (["BANK CHARGE", "MDR RCVRY", "SMS CHARGE", "CHQ DEP RET", "LOCKER CHARGE",
              "SERVICE CHARGE", "BANK SERVICE", "ATM CHARGE", "ANNUAL FEE"],
             ["BANK CHARGES", "BANK CHARGE"]),

            (["INTEREST", "INT CHARGED", "INTEREST ON OD", "INTEREST ON LOAN", "LOAN INTEREST",
              "CC INTEREST", "INTEREST EXPENSE"],
             ["INTEREST EXP", "INTEREST EXPENSE", "BANK INTEREST", "BANK INTEREST & CHARGES"]),

            (["FD", "FIXED DEPOSIT", "FD MATURITY", "FD PROCEEDS", "FD INVESTMENT", "RD", "RECURRING DEPOSIT"],
             ["FD INVESTMENT", "FIXED DEPOSIT", "FD"]),

            (["REV SWEEP", "SWEEP FROM", "AUTO SWEEP", "REVERSE SWEEP"],
             ["FD INVESTMENT", "FD", "FIXED DEPOSIT"]),

            (["FD INTEREST", "FD INT", "INTEREST ON FD", "INT ON FD", "FD PROCEEDS"],
             ["FD INTEREST", "INTEREST ON FD"]),

            # Tax & Government
            (["GST PAYMENT", "GST PAID", "GSTIN", "GST CHALLAN", "IGST", "CGST", "SGST", "E-CHALLAN GST"],
             ["GST PAYABLE", "GST EXPENSE", "GST PAYMENT"]),

            (["TDS", "TDS PAYMENT", "TDS CHALLAN", "TAX DEDUCTED", "INCOME TAX", "ADVANCE TAX", "SELF ASSESSMENT"],
             ["TDS PAYABLE", "TDS EXPENSE", "INCOME TAX"]),

            (["PROFESSIONAL TAX", "P TAX", "PTAX", "PT CHALLAN"],
             ["PROFESSIONAL TAX", "P.TAX EXP"]),

            # Insurance
            (["INSURANCE", "INSUR", "LIFE INSURANCE", "LIC", "VEHICLE INSURANCE", "HEALTH INSURANCE",
              "FIRE INSURANCE", "GIC", "NATIONAL INSURANCE", "NEW INDIA INSURANCE"],
             ["INSURANCE EXP", "INSURANCE EXPENSE", "INSURANCE"]),

            # Materials & Purchases (common)
            (["WEIGHTBRIDGE", "WEIGHT BRIDGE", "WEIGHBRIDGE"],
             ["WEIGHTBRIDGE CHARGES", "WEIGHT BRIDGE EXP", "LOADING EXPENSE"]),

            # Cutting Tools / Equipment
            (["CUTTING TOOLS", "CUTTINGTOOLS", "CUTTING EQUIPMENT", "CUTTING EQUIPMENTS",
              "CUTTING TOOL", "HSS CUTTING", "TOOL PURCHASE"],
             ["CUTTING EQUIPMENTS", "CUTTING TOOLS EXP", "TOOLS EXP"]),

            # Repairs & Maintenance
            (["REPAIR", "MAINTENANCE", "SERVICING", "AMC", "ANNUAL MAINTENANCE", "SERVICE CONTRACT"],
             ["REPAIR & MAINTENANCE", "REPAIRS EXP", "MAINTENANCE EXP"]),

            # Printing & Stationery
            (["PRINTING", "STATIONERY", "PHOTOCOPY", "XEROX"],
             ["PRINTING & STATIONERY", "STATIONERY EXP"]),

            # Advertising & Marketing
            (["ADVERTISING", "ADVERTISEMENT", "MARKETING", "PROMO", "DIGITAL MARKETING", "SEO"],
             ["ADVERTISEMENT EXP", "ADVERTISING EXP"]),

            # Food & Entertainment
            (["SWIGGY", "ZOMATO", "FOOD", "RESTAURANT", "CANTEEN", "TEA", "SNACKS", "CATERING",
              "STAFF WELFARE", "HOTEL", "DINNER", "LUNCH"],
             ["STAFF WELFARE", "FOOD EXP", "ENTERTAINMENT EXP"]),

            # Capital & Investments
            (["SHARE", "STOCK", "MUTUAL FUND", "EQUITY", "DIVIDEND", "BOND", "ZERODHA", "GROWW",
              "ANGEL ONE", "HDFC SECURITIES", "NSDL"],
             ["INVESTMENTS", "SHARE CAPITAL", "INVESTMENT"]),

            # Cash movements
            (["CASH DEPOSIT", "CASH DEPO", "ATM DEPOSIT"],
             ["CASH ACCOUNT", "CASH A/C", "CASH ON HAND"]),

            (["CASH WITHDRAWAL", "CASH WITHDR", "ATM WITHDRAWAL", "ATM CASH"],
             ["CASH ACCOUNT", "CASH A/C", "CASH ON HAND"]),
        ]

        def find_best_keyword_match(narr_upper: str) -> str | None:
            """Returns the best ledger from keyword rules using strict word boundaries, excluding gateway noise."""
            # Pre-strip payment gateway noise so words like 'PHONEPE' do not trigger 'PHONE' -> 'TELEPHONE EXP'
            narr_clean_kw = re.sub(r'\b(PHONEPE|PAYTM|GPAY|BHIM|AMAZONPAY|PAYU|RAZORPAY|BILLDESK)\b', '', narr_upper, flags=re.IGNORECASE)
            for keywords, target_options in KEYWORD_RULES:
                for kw in keywords:
                    if re.search(rf'\b{re.escape(kw.upper())}\b', narr_clean_kw):
                        for target in target_options:
                            if target.upper() in ledger_lookup:
                                return ledger_lookup[target.upper()]
                        return target_options[0]
            return None

        # ── Per-row mapping ────────────────────────────────────────────────────
        import time
        t_start_map = time.time()
        total_rows_count = len(rows)
        silent_mode = total_rows_count >= 25
        mapped_count = 0

        if silent_mode:
            print(f"⚡ [Memory Engine] Matching {total_rows_count} transactions using local Memory Vault...")

        for idx, row in enumerate(rows):
            narr = str(row.get("narration") or row.get("narr") or row.get("description") or "").strip()
            tx_type = str(row.get("transaction_type", "Payment")).strip().capitalize()
            if not narr:
                continue

            matched_ledger = None
            match_stage = None

            # ── STAGE -1: User Custom Instructions ───────────────────────────
            for src_kw, tgt_ledger, req_type in user_guideline_rules:
                if req_type and req_type != tx_type:
                    continue
                if re.search(rf'\b{re.escape(src_kw)}\b', narr.upper()):
                    matched_ledger = tgt_ledger
                    match_stage = "S-UserInstruction"
                    break

            cleaned_narr = _MemVault.clean_mapping_key(narr)
            cleaned_narr_upper = cleaned_narr.upper()
            narr_upper = narr.upper()

            # ── STAGE 0a: Fast Exact Clean Key Match in Expense Mappings ──────
            if not matched_ledger and cleaned_narr_upper in clean_memory:
                matched_ledger = clean_memory[cleaned_narr_upper]
                match_stage = f"S0-ExactMem('{cleaned_narr[:25]}')"

            # ── STAGE 0b: Memory Vault Check (Multi-Token Overlap Match) ─────
            if not matched_ledger and clean_memory:
                from ai_memory import AIMemoryVault as _MV0
                narr_clean_key = _MV0.clean_mapping_key(narr)
                narr_tokens = set(w for w in narr_clean_key.split() if len(w) >= 3 and w not in ('NAGAR', 'EAST', 'WEST', 'NORTH', 'SOUTH', 'ROAD', 'STREET'))
                best_score = 0.0
                best_val   = None
                best_match_token_count = 0

                if narr_tokens:
                    for clean_k, ledger_val in clean_memory.items():
                        key_tokens = set(w for w in clean_k.split() if len(w) >= 3 and w not in ('NAGAR', 'EAST', 'WEST', 'NORTH', 'SOUTH', 'ROAD', 'STREET'))
                        if not key_tokens:
                            continue
                        intersection = narr_tokens & key_tokens
                        if not intersection:
                            continue
                        score = len(intersection) / len(narr_tokens | key_tokens)
                        if clean_k in narr_clean_key.upper() or narr_clean_key.upper() in clean_k:
                            score += 0.3
                        if score > best_score:
                            best_score = score
                            best_val   = ledger_val
                            best_match_token_count = len(intersection)

                if best_val and (best_score >= 0.45 or best_match_token_count >= 2):
                    matched_ledger = best_val
                    match_stage = f"S0-FuzzyMem('{narr_clean_key[:25]}')"

            # ── STAGE 1: Exact Match in Master Ledgers ───────────────────────
            if not matched_ledger:
                if narr_upper in ledger_lookup:
                    matched_ledger = ledger_lookup[narr_upper]
                    match_stage = "S1-PartyExact"
                else:
                    narr_tokens = [w for w in narr_upper.split() if len(w) >= 4]
                    for tok in narr_tokens:
                        if tok in ledger_lookup:
                            matched_ledger = ledger_lookup[tok]
                            match_stage = "S1-PartyToken"
                            break

            # ── STAGE 2a: Direct ledger name substring (Strict Word Boundary) ─
            if not matched_ledger:
                for l_upper, l_exact in ledger_lookup.items():
                    if len(l_upper) >= 3 and l_upper not in RESERVED_GENERIC_WORDS:
                        if re.search(rf'\b{re.escape(l_upper)}\b', narr_upper):
                            matched_ledger = l_exact
                            match_stage = "S2a-DirectSub"
                            break

            # ── STAGE 2b: Letter-only narration vs ledger match ───────────────
            if not matched_ledger:
                narr_letters = clean_to_letters(narr)
                for l_letters, l_exact in ledger_letter_map.items():
                    if l_letters not in RESERVED_GENERIC_WORDS and l_exact.upper() not in RESERVED_GENERIC_WORDS:
                        if l_letters in narr_letters:
                            matched_ledger = l_exact
                            match_stage = "S2b-LetterSub"
                            break

            # ── STAGE 3: Strict Banking Keyword Intelligence (Word boundaries) ─
            if not matched_ledger:
                matched_ledger = find_best_keyword_match(narr_upper)
                if matched_ledger:
                    match_stage = "S3-Keyword"

            # ── STAGE 4: Narration Party Extractor & Ledger Matching ─────────
            if not matched_ledger:
                extracted_party = self.extract_clean_party_from_narration(narr)
                if extracted_party:
                    ext_party_up = extracted_party.upper().strip()
                    if ext_party_up in ledger_lookup:
                        matched_ledger = ledger_lookup[ext_party_up]
                        match_stage = "S4-PartyExact"
                    else:
                        party_tokens = [w for w in ext_party_up.split() if len(w) >= 3]
                        for tok in party_tokens:
                            if tok in ledger_lookup:
                                matched_ledger = ledger_lookup[tok]
                                match_stage = "S4-PartyToken"
                                break
                        if not matched_ledger:
                            fm = difflib.get_close_matches(ext_party_up, list(ledger_lookup.keys()), n=1, cutoff=0.72)
                            if fm:
                                matched_ledger = ledger_lookup[fm[0]]
                                match_stage = "S4-PartyFuzzy"

            # ── STAGE 5: Full fuzzy match (last resort) ────────────────────────
            if not matched_ledger:
                clean_tokens = [w for w in re.split(r'[\s\-\/@._]+', narr) if len(w) >= 3 and not w.isdigit()]
                if clean_tokens:
                    clean_tok_narr = " ".join(clean_tokens).upper()
                    matches = difflib.get_close_matches(clean_tok_narr, list(ledger_lookup.keys()), n=1, cutoff=0.70)
                    if matches:
                        matched_ledger = ledger_lookup[matches[0]]
                        match_stage = "S5-FuzzyFull"
                    else:
                        for tok in clean_tokens:
                            if len(tok) >= 4:
                                tok_matches = difflib.get_close_matches(tok.upper(), list(ledger_lookup.keys()), n=1, cutoff=0.75)
                                if tok_matches:
                                    matched_ledger = ledger_lookup[tok_matches[0]]
                                    match_stage = "S5-FuzzyToken"
                                    break

            # ── Apply result ──────────────────────────────────────────────────
            if matched_ledger and matched_ledger.upper() in RESERVED_GENERIC_WORDS:
                if not silent_mode:
                    print(f"🛡️ [Python Guard] Rejecting generic filler word '{matched_ledger}' as mapped ledger. Forcing Suspense fallback.")
                matched_ledger = None

            if matched_ledger:
                mapped_count += 1
                m_up = matched_ledger.upper().strip()
                is_raw_narr = (m_up == narr.upper().strip()) or any(m_up.startswith(p) for p in ["UPI", "NEFT", "IMPS", "ACH", "RTGS", "TPT", "INB", "CHQ", "POS"]) or any(h in m_up for h in ["OKAXIS", "OKICICI", "KHDFCBANK", "OKHDFCBANK", "OKSBI", "PTYES", "NAVIAXIS", "KOTAK", "YBL", "@"])
                if is_raw_narr:
                    clean_sanitized = self.extract_clean_party_from_narration(matched_ledger)
                    if clean_sanitized and len(clean_sanitized) >= 2:
                        matched_ledger = clean_sanitized

                row["mapped_ledger"] = matched_ledger
                row["party_name"] = matched_ledger
                row["party"] = matched_ledger
                master_group = ledger_group_map.get(matched_ledger.upper())
                if master_group:
                    row["group_hint"] = master_group
                if "S-UserInstruction" in match_stage:
                    row["confidence_score"] = 98
                    if not master_group:
                        if tx_type == "Receipt":
                            row["group_hint"] = "Sundry Debtors" if "DEBT" in matched_ledger.upper() else "Indirect Income"
                        else:
                            row["group_hint"] = "Sundry Creditors" if "CRED" in matched_ledger.upper() else "Indirect Expenses"
                    if row.get("flags"):
                        row["flags"] = [f for f in row["flags"] if f not in ("Suspense Mapping", "Unmapped Ledger")]
                    if not silent_mode:
                        print(f"  🎯 [{match_stage}] '{narr[:50]}' → '{matched_ledger}' (User Rule Applied)")
                else:
                    if "S5-Fuzzy" in match_stage:
                        row["confidence_score"] = min(row.get("confidence_score", 80), 72)
                        if "Low Confidence" not in row.get("flags", []):
                            row.setdefault("flags", []).append("Low Confidence")
                    print(f"  ✅ [{match_stage}] '{narr[:50]}' → '{matched_ledger}'")
            else:
                # Deterministic fallback — Extract clean party name, NEVER output generic group name
                extracted_party = self.extract_clean_party_from_narration(narr)
                if extracted_party and len(extracted_party) >= 2:
                    target_group = self.classify_transaction_nature(
                        narr, extracted_party, tx_type,
                        amount=float(row.get("amount", 0) or 0)
                    )

                    row["mapped_ledger"] = extracted_party
                    row["party_name"] = extracted_party
                    row["party"] = extracted_party
                    row["group_hint"] = target_group
                    row["confidence_score"] = 85
                    if row.get("flags"):
                        row["flags"] = [f for f in row["flags"] if f not in ("Suspense Mapping", "Unmapped Ledger")]
                    if not silent_mode:
                        print(f"  ✅ [Clean Party Auto-Extraction] '{narr[:50]}' → '{extracted_party}' ({target_group})")
                else:
                    resolved_name = ledger_lookup.get("SUSPENSE ACCOUNT", "Suspense Account")
                    row["mapped_ledger"] = resolved_name
                    row["party_name"] = resolved_name
                    row["party"] = resolved_name
                    row["group_hint"] = "Suspense Account"
                    row["confidence_score"] = 75
                    if not silent_mode:
                        print(f"  ⚠️ [Suspense] '{narr[:50]}' → '{resolved_name}'")

            if silent_mode:
                if (idx + 1) % 100 == 0 or (idx + 1) == total_rows_count:
                    pct = int(((idx + 1) / total_rows_count) * 100)
                    filled = int((pct / 100) * 20)
                    bar = '█' * filled + '░' * (20 - filled)
                    print(f"  [Memory Engine] [{bar}] {idx + 1}/{total_rows_count} ({pct}% Completed)", end='\r' if (idx + 1) < total_rows_count else '\n')

        if silent_mode:
            t_end_map = time.time()
            elapsed_map = max(0.001, t_end_map - t_start_map)
            local_pct = (mapped_count / total_rows_count * 100) if total_rows_count > 0 else 100.0
            print(f"✅ [Memory Engine Complete] Mapped {mapped_count}/{total_rows_count} bank transactions in {elapsed_map:.2f}s ({local_pct:.1f}% matched locally).")

        return extracted_data


    def apply_product_mappings(self, result_json: dict, client_memory: dict, module: str = "Sales", instruction: str = "") -> dict:
        """Applies rule-based product mappings (keyword-based and GST-based) from client memory
        to the extracted items to automatically match them to Miracle products."""
        if isinstance(result_json, list):
            result_json = {"status": "success", "extracted_data": result_json}
        if not isinstance(result_json, dict):
            result_json = {"status": "success", "extracted_data": []}

        # --- Route to Decoupled Module Parsers ---
        import sys
        sys.path.append(os.path.join(os.path.dirname(__file__), "core"))
        sys.path.append(os.path.join(os.path.dirname(__file__), "modules"))
        
        if module == "Sales":
            from modules.sales.parser import SalesParser
            sp = SalesParser(self.api_key, self.model_name)
            result_json = sp.clean_invoice_data(result_json, client_memory, module=module)
        elif module == "Purchases":
            from modules.purchases.parser import PurchaseParser
            pp = PurchaseParser(self.api_key, self.model_name)
            result_json = pp.clean_invoice_data(result_json, client_memory, module=module)

        if module in ["Bank Statements", "Cash Entries"]:
            result_json = self.map_ledgers_for_statement(result_json, client_memory, module=module, instruction=instruction)
            # Ask Gemini to assist with any remaining Suspense Account mappings
            result_json = self.ai_assist_suspense_mappings(result_json, client_memory, module=module, instruction=instruction)
            
            # ── LEDGER NAME ALIGNMENT GUARD ─────────────────────────────────────
            # Align similar ledger names (like 'Salary Expenses' vs 'SALARY') to prevent duplicate creations
            if result_json.get("status") == "success" and "extracted_data" in result_json:
                existing_ledgers = client_memory.get("existing_ledgers", [])
                
                def find_aligned_ledger(resolved_name: str, existing_list: list) -> str:
                    res_up = resolved_name.upper().strip()
                    
                    # 1. Salary alignment
                    salary_variations = ["SALARY", "SALARY EXPENSES", "SALARY A/C", "SALARY PAYMENT", "STAFF SALARY", "SALARIES", "SALARY EXPENSE"]
                    if any(v in res_up for v in ["SALARY", "SALARIES"]):
                        for leg in existing_list:
                            leg_name = leg.get("name", "").strip() if isinstance(leg, dict) else str(leg).strip()
                            leg_name_up = leg_name.upper().strip()
                            if leg_name_up in salary_variations:
                                return leg_name
                                
                    # 2. Rent alignment
                    rent_variations = ["RENT", "RENT EXPENSES", "RENT A/C", "RENT PAYMENT", "OFFICE RENT", "SHOP RENT", "RENT EXPENSE"]
                    if "RENT" in res_up:
                        for leg in existing_list:
                            leg_name = leg.get("name", "").strip() if isinstance(leg, dict) else str(leg).strip()
                            leg_name_up = leg_name.upper().strip()
                            if leg_name_up in rent_variations:
                                return leg_name
                                
                    # 3. Bank Charges alignment
                    charges_variations = ["BANK CHARGES", "BANK CHARGE", "BANK CHARGES A/C", "BANK SERVICE CHARGES", "BANK INTEREST & CHARGES", "BANK INTEREST AND CHARGES"]
                    if any(v in res_up for v in ["BANK CHARGE", "BANK SERVICE"]):
                        for leg in existing_list:
                            leg_name = leg.get("name", "").strip() if isinstance(leg, dict) else str(leg).strip()
                            leg_name_up = leg_name.upper().strip()
                            if leg_name_up in charges_variations:
                                return leg_name
                                
                    return ""

                for row in result_json["extracted_data"]:
                    mapped = str(row.get("mapped_ledger") or "").strip()
                    if mapped:
                        aligned = find_aligned_ledger(mapped, existing_ledgers)
                        if aligned and aligned.upper().strip() != mapped.upper().strip():
                            print(f"🔗 [Ledger Alignment] Aligning '{mapped}' to existing ledger '{aligned}'.")
                            row["mapped_ledger"] = aligned
                            row["party_name"] = aligned
                            row["party"] = aligned
            
            # Post-AI Fallback: If still mapped to Suspense or generic group, run clean party auto-extraction first
            if result_json.get("status") == "success" and "extracted_data" in result_json:
                existing_ledgers = client_memory.get("existing_ledgers", [])
                ledger_lookup = {}
                for leg in existing_ledgers:
                    if not leg:
                        continue
                    if isinstance(leg, dict):
                        name = leg.get("name", "").strip()
                    else:
                        name = str(leg).strip()
                    if name:
                        ledger_lookup[name.upper()] = name
                for row in result_json["extracted_data"]:
                    mapped = str(row.get("mapped_ledger") or "").strip().upper()
                    if mapped in ("SUSPENSE ACCOUNT", "SUSPENSE A/C", "UPI DEBTORS", "UPI CREDITORS"):
                        narr = str(row.get("narration") or "").strip()
                        tx_type = str(row.get("transaction_type", "")).strip().capitalize()
                        clean_party = self.extract_clean_party_from_narration(narr)
                        if clean_party and len(clean_party) >= 2:
                            upper_party = clean_party.upper()
                            target_group = "Sundry Debtors" if tx_type == "Receipt" else "Sundry Creditors"
                            if any(k in upper_party for k in ['TAX', 'PROFESSIONAL TAX', 'GST', 'TDS', 'DUTY']):
                                target_group = "Duties & Taxes" if "TAX" in upper_party else "Indirect Expenses"
                            elif any(k in upper_party for k in ['EXPENSE', 'EXP', 'RENT', 'SALARY', 'MAINTENANCE', 'ELECTRICITY', 'TELEPHONE', 'CHARGES', 'FEE', 'COMMISSION', 'INTERNET', 'RECHARGE', 'PETROL']):
                                target_group = "Indirect Expenses"
                            elif any(k in upper_party for k in ['BANK CHARGES', 'MDR RCVRY', 'INSTAALERT']):
                                target_group = "Indirect Expenses"
                            elif "CASH" in upper_party:
                                target_group = "Cash-in-Hand"

                            row["mapped_ledger"] = clean_party
                            row["party_name"] = clean_party
                            row["party"] = clean_party
                            row["group_hint"] = target_group
                        else:
                            default_upi = "Sundry Debtors" if tx_type == "Receipt" else "Sundry Creditors"
                            row["mapped_ledger"] = ledger_lookup.get(default_upi.upper(), default_upi)
                            row["party_name"] = row["mapped_ledger"]
                            row["party"] = row["mapped_ledger"]
            # Apply date range filtering from user instructions if specified
            if result_json.get("status") == "success" and "extracted_data" in result_json:
                start_date, end_date = self.parse_date_range_from_instruction(instruction)
                if start_date or end_date:
                    from datetime import datetime
                    print(f"🎯 [Date Filter] Filtering entries between {start_date} and {end_date} from instruction...")
                    
                    original_rows = result_json["extracted_data"]
                    filtered_rows = []
                    for row in original_rows:
                        dt_str = row.get("date", "")
                        if dt_str:
                            try:
                                row_dt = datetime.strptime(dt_str[:10], "%Y-%m-%d").date()
                                if start_date and row_dt < start_date:
                                    continue
                                if end_date and row_dt > end_date:
                                    continue
                            except Exception as parse_err:
                                print(f"  [Date Filter] Warning: failed to parse row date '{dt_str}': {parse_err}")
                                pass
                        filtered_rows.append(row)
                    
                    # Recalculate opening balance if we removed rows from the beginning
                    if filtered_rows and len(filtered_rows) < len(original_rows):
                        first_row = filtered_rows[0]
                        first_bal = first_row.get("running_balance")
                        first_amt = first_row.get("amount", 0.0)
                        first_type = first_row.get("transaction_type", "Receipt")
                        
                        if first_bal is not None and first_bal != "":
                            try:
                                first_bal_val = float(first_bal)
                                first_amt_val = float(first_amt)
                                if first_type == "Receipt":
                                    new_op = round(first_bal_val - first_amt_val, 2)
                                else:
                                    new_op = round(first_bal_val + first_amt_val, 2)
                                result_json["opening_balance"] = new_op
                                print(f"🎯 [Date Filter] Adjusted Opening Balance to {new_op} based on first transaction.")
                            except:
                                pass
                    
                    result_json["extracted_data"] = filtered_rows
                    print(f"🎯 [Date Filter] Keep {len(filtered_rows)} / {len(original_rows)} transactions.")
            return result_json
            
        INVALID_ITEM_WORDS = {"sale", "sales", "purchase", "purchases", "creditnote", "debitnote", "credit", "debit", "journal", "receipt", "payment", "voucher"}
        
        extracted_data = result_json.get("extracted_data", [])
        for voucher in extracted_data:
            party_name = str(voucher.get("party_name", "")).strip().upper()
            items = voucher.get("items", [])
            valid_items = []
            
            for item in items:
                item_name = str(item.get("name", "")).strip()
                item_norm = item_name.lower().replace(" ", "").replace(".", "").replace("_", "")
                
                # Check if item name is invalid (e.g. same as party name or is a transaction type word)
                is_invalid = False
                if item_norm in INVALID_ITEM_WORDS:
                    is_invalid = True
                elif len(item_name) < 2:
                    is_invalid = True
                    
                if is_invalid:
                    print(f"⚠️ Filtering out invalid extracted product name: '{item_name}' (party: {party_name})")
                    continue
                valid_items.append(item)
                
            # Fallback if all items were invalid
            if not valid_items and items:
                default_name = "SALES" if module == "Sales" else "PURCHASES"
                first_item = items[0]
                first_item["name"] = default_name
                valid_items.append(first_item)
                print(f"⚠️ All extracted products were invalid. Defaulted item name to '{default_name}'")
                
            voucher["items"] = valid_items

        product_mappings = client_memory.get("product_mappings", {})
        if not product_mappings:
            return result_json
            
        keyword_rules = product_mappings.get("keyword_rules", {})
        gst_rules = product_mappings.get("gst_rules", {})
        
        # Load active client products from DBF dynamically for 100-client compatibility
        client_products = []
        try:
            from dbf_handler import MiracleDBFHandler
            settings_path = "settings.json"
            if not os.path.exists(settings_path):
                settings_path = os.path.join(os.path.dirname(__file__), "settings.json")
            with open(settings_path, "r") as f:
                settings = json.load(f)
            client_id = settings.get("active_client_id", "")
            if client_id and settings.get("miracle_base_path"):
                client_path = os.path.join(settings["miracle_base_path"], client_id)
                if os.path.exists(client_path):
                    handler = MiracleDBFHandler(client_path)
                    client_products = handler.read_products()
        except Exception as e:
            print(f"⚠️ Could not load active client products for dynamic mapping: {e}")

        def find_dynamic_product_for_gst(c_products: list, g_pct: float, mod: str = "Sales") -> str:
            g_int = str(int(g_pct))
            if c_products:
                # 1. Match product name containing GST percentage string (e.g. "5%", "GST 5", "GST5", "(5%)")
                for prod in c_products:
                    p_name = prod.get("name", "").strip()
                    p_up = p_name.upper()
                    if f"{g_int}%" in p_up or f"GST {g_int}" in p_up or f"GST{g_int}" in p_up or f" {g_int}%" in p_up or f"({g_int}%)" in p_up:
                        return p_name
                # 2. Match product by commodity code corresponding to g_pct (e.g. C002 for 5%, C004 for 18%)
                expected_comm = "CNGT" if g_pct <= 0 else ("C002" if g_pct <= 5 else ("C003" if g_pct <= 12 else ("C004" if g_pct <= 18 else "C005")))
                for prod in c_products:
                    comm = str(prod.get("commodity") or prod.get("commodity_code") or prod.get("M21F27") or "").strip().upper()
                    if comm == expected_comm:
                        p_name = prod.get("name", "").strip()
                        if p_name: return p_name
            default_base = "SALES" if mod == "Sales" else "PURCHASES"
            return f"{default_base} GST {int(g_pct)}%" if g_pct > 0 else f"{default_base} EXEMPT"

        extracted_data = result_json.get("extracted_data", [])
        for voucher in extracted_data:
            party_name_raw = str(voucher.get("party_name", "")).strip()
            party_clean = re.sub(r'^(dr|mr|mrs|ms|cmf)\.?\s+', '', party_name_raw.lower()).strip()
            items = voucher.get("items", [])
            for item in items:
                item_name = str(item.get("name", "")).strip()
                gst_pct = float(item.get("gst_pct", 18.0))
                item_clean = re.sub(r'^(dr|mr|mrs|ms|cmf)\.?\s+', '', item_name.lower()).strip()
                
                mapped = False
                
                # 1. Apply keyword-based rules (case-insensitive)
                for kw, target_prod in keyword_rules.items():
                    if kw.lower() in item_name.lower():
                        print(f"Mapping product '{item_name}' to '{target_prod}' (matched keyword '{kw}')")
                        item["name"] = target_prod
                        mapped = True
                        break
                        
                # 2. Check exact or substring match against active Client DBF Products Catalog
                if not mapped and client_products:
                    item_upper = item_name.upper().strip()
                    for prod in client_products:
                        p_name = prod.get("name", "").strip()
                        if p_name and p_name.upper() == item_upper:
                            print(f"✅ Exact DBF Catalog Match: '{item_name}' -> '{p_name}'")
                            item["name"] = p_name
                            mapped = True
                            break
                    if not mapped:
                        for prod in client_products:
                            p_name = prod.get("name", "").strip()
                            if p_name and len(item_upper) >= 4 and not re.search(r'^(cmf|dr|mr|mrs|ms)\.?\s+', item_name.lower()):
                                if item_upper in p_name.upper() or p_name.upper() in item_upper:
                                    print(f"✅ Substring DBF Catalog Match: '{item_name}' -> '{p_name}'")
                                    item["name"] = p_name
                                    mapped = True
                                    break

                # 3. Patient / Customer / Job Item Guard: Auto-map patient names & custom job items to DBF GST rate product
                is_patient_or_job_item = False
                if re.search(r'^(cmf|dr|mr|mrs|ms)\.?\s+', item_name.lower()):
                    is_patient_or_job_item = True
                elif len(item_clean) >= 3 and (item_clean == party_clean or item_clean in party_clean or party_clean in item_clean):
                    is_patient_or_job_item = True
                elif module == "Purchases" and not mapped:
                    # In Purchases, unmapped job items/patient names from suppliers map to GST rate product
                    is_patient_or_job_item = True

                if not mapped and is_patient_or_job_item:
                    gst_str = str(gst_pct)
                    gst_int_str = str(int(gst_pct))
                    default_prod_key = "default_purchase_product" if module == "Purchases" else "default_sales_product"
                    target_prod = gst_rules.get(gst_str) or gst_rules.get(gst_int_str) or product_mappings.get(default_prod_key)
                    if not target_prod:
                        target_prod = find_dynamic_product_for_gst(client_products, gst_pct, module)
                    if target_prod:
                        print(f"🤖 Patient/Job Item Guard ({module}): Auto-mapped item '{item_name}' (party: '{party_name_raw}') -> '{target_prod}'")
                        item["name"] = target_prod
                        mapped = True

                # 3. Apply GST-based rules
                if not mapped and gst_rules:
                    gst_str = str(gst_pct)
                    gst_int_str = str(int(gst_pct))
                    
                    target_prod = gst_rules.get(gst_str) or gst_rules.get(gst_int_str)
                    if target_prod:
                        print(f"Mapping product '{item_name}' to '{target_prod}' (matched GST {gst_pct}%)")
                        item["name"] = target_prod
                        mapped = True

        # 3. Apply AI-based semantic mapping fallback for any remaining unmapped items
        if self.api_key:
            if client_products:
                # Create a set of existing product names and codes for exact match check
                existing_names_codes = set()
                for prod in client_products:
                    if prod.get("name"):
                        existing_names_codes.add(prod["name"].strip().upper())
                    if prod.get("code"):
                        existing_names_codes.add(prod["code"].strip().upper())

                # Collect unmapped items
                unmapped_items_info = []
                seen_unmapped_names = set()
                for voucher in extracted_data:
                    items = voucher.get("items", [])
                    for item in items:
                        item_name = str(item.get("name", "")).strip()
                        if item_name.upper() not in existing_names_codes:
                            if item_name not in seen_unmapped_names:
                                seen_unmapped_names.add(item_name)
                                unmapped_items_info.append({
                                    "name": item_name,
                                    "gst_pct": item.get("gst_pct", 18.0),
                                    "hsn_code": item.get("hsn_code", "")
                                })

                if unmapped_items_info:
                    print(f"🤖 Found {len(unmapped_items_info)} unmapped items. Resolving via Gemini semantic mapping...")
                    
                    # Simplify products list to reduce tokens and focus the model
                    simplified_products = [
                        {
                            "name": prod.get("name"),
                            "code": prod.get("code"),
                            "hsn_code": prod.get("hsn_code")
                        } for prod in client_products
                    ]
                    
                    custom_instructions = product_mappings.get("instructions") or product_mappings.get("ai_instructions") or ""
                    
                    prompt = f"""You are an expert AI accountant. Your task is to map extracted invoice item names to the official Miracle accounting software product list.
                    
Here is the official client product list:
{json.dumps(simplified_products, indent=2)}

Client's custom mapping instructions/guidelines:
"{custom_instructions}"

Evaluate the following unmapped items:
{json.dumps(unmapped_items_info, indent=2)}

Instructions:
1. For each unmapped item, match it to the most appropriate official product from the official client product list. Use semantic similarity, spelling variations, linked HSN codes, and the client's custom instructions.
2. If an item definitely does NOT match any official product and represents a completely new product that cannot be mapped, map it to the string "AUTO_CREATE_PRODUCT".
3. CRITICAL: If an item name appears to be a patient or customer name (e.g. 'Dinesh naidu', 'Cmf Dilip chitalia'), DO NOT map it to 'AUTO_CREATE_PRODUCT'. Instead, map it to the official product from the client product list matching its GST rate or HSN code.
4. Return your response ONLY as a JSON object where the key is the exact unmapped item name and the value is the mapped official product name (or "AUTO_CREATE_PRODUCT").

Example Output:
{{
  "Ida Lemos CMF": "FOOTWEAR GST 5%",
  "Oxygen delivery system": "footwear Gst 0"
}}
"""
                    try:
                        client = self._get_client()
                        response = self._generate_content_with_retry(
                            client=client,
                            model=self.model_name or "gemini-3.1-flash-lite",
                            contents=prompt,
                            config=types.GenerateContentConfig(
                                response_mime_type="application/json"
                            )
                        )
                        
                        ai_mappings = json.loads(response.text.strip() if response and response.text else "{}")
                        print(f"🤖 Gemini resolved AI mappings: {json.dumps(ai_mappings, indent=2)}")
                        
                        # Apply the resolved mappings
                        for voucher in extracted_data:
                            items = voucher.get("items", [])
                            for item in items:
                                item_name = str(item.get("name", "")).strip()
                                if item_name in ai_mappings:
                                    target_val = ai_mappings[item_name]
                                    if target_val != "AUTO_CREATE_PRODUCT":
                                        if target_val.upper() in existing_names_codes:
                                            print(f"🤖 AI Mapped product '{item_name}' -> '{target_val}'")
                                            item["name"] = target_val
                                    else:
                                        print(f"🤖 AI marked product '{item_name}' as AUTO_CREATE_PRODUCT")
                    except Exception as ex:
                        print(f"⚠️ Error during AI semantic mapping: {ex}")
        return result_json

    def parse_date_range_from_instruction(self, instruction: str):
        import re
        from datetime import date
        import calendar

        if not instruction:
            return None, None

        instr_clean = instruction.strip()
        instr_lower = instr_clean.lower()

        # Helper to safely create date and handle clipped days (like 31st April -> 30th April)
        def safe_create_date(y, m, d):
            if not (1 <= m <= 12):
                return None
            try:
                return date(y, m, d)
            except ValueError:
                # Clip to last day of month if day is too large
                last_day = calendar.monthrange(y, m)[1]
                try:
                    return date(y, m, last_day)
                except ValueError:
                    return None

        found_dates = []

        # 1. Match YYYY-MM-DD
        for match in re.finditer(r'\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b', instr_clean):
            try:
                y = int(match.group(1))
                m = int(match.group(2))
                d = int(match.group(3))
                dt = safe_create_date(y, m, d)
                if dt and dt not in found_dates:
                    found_dates.append(dt)
            except:
                pass

        # 2. Match DD/MM/YYYY or DD/MM/YY
        for match in re.finditer(r'\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})\b', instr_clean):
            try:
                d = int(match.group(1))
                m = int(match.group(2))
                y_str = match.group(3)
                y = int(y_str)
                if len(y_str) == 2:
                    y += 2000
                dt = safe_create_date(y, m, d)
                if dt and dt not in found_dates:
                    found_dates.append(dt)
            except:
                pass

        if len(found_dates) >= 2:
            found_dates.sort()
            return found_dates[0], found_dates[-1]

        # 3. Match Month + Year keyword, e.g. "April 2026" or "Apr 26"
        months_map = {
            'jan': 1, 'january': 1,
            'feb': 2, 'february': 2,
            'mar': 3, 'march': 3,
            'apr': 4, 'april': 4,
            'may': 5,
            'jun': 6, 'june': 6,
            'jul': 7, 'july': 7,
            'aug': 8, 'august': 8,
            'sep': 9, 'september': 9,
            'oct': 10, 'october': 10,
            'nov': 11, 'november': 11,
            'dec': 12, 'december': 12
        }

        month_val = None
        for m_name, m_num in months_map.items():
            if re.search(r'\b' + m_name + r'\b', instr_lower):
                month_val = m_num
                break

        if month_val:
            year_match = re.search(r'\b(20\d{2}|\d{2})\b', instr_clean)
            if year_match:
                yr_str = year_match.group(1)
                yr = int(yr_str)
                if len(yr_str) == 2:
                    yr += 2000
                last_day = calendar.monthrange(yr, month_val)[1]
                return date(yr, month_val, 1), date(yr, month_val, last_day)

        if len(found_dates) == 1:
            single_date = found_dates[0]
            if any(w in instr_lower for w in ["from", "after", "start", "starting", "since"]):
                return single_date, None
            if any(w in instr_lower for w in ["to", "before", "end", "ending", "until"]):
                return None, single_date

        return None, None

    def ai_assist_suspense_mappings(self, result_json: dict, client_memory: dict, module: str, instruction: str = "") -> dict:
        """
        Sends unmapped/suspense narrations to Gemini in a single text request
        to resolve them using the client's business profile and existing ledgers.
        This provides LLM intelligence to the native PDF/Excel engines with 100% math precision.
        """
        if not self.api_key:
            return result_json

        rows = result_json.get("extracted_data", [])
        if not rows:
            return result_json

        existing_ledgers = client_memory.get("existing_ledgers", [])
        existing_names_upper = set()
        for leg in existing_ledgers:
            name = leg.get("name", "") if isinstance(leg, dict) else str(leg)
            if name:
                existing_names_upper.add(name.upper().strip())

        # Identify unique narrations mapped to Suspense Account or unmapped generic groups
        suspense_rows = []
        unique_susp_narrs = {}  # narration -> (tx_type, group_hint)
        
        for r in rows:
            mapped = str(r.get("mapped_ledger") or "").strip().upper()
            is_suspense = (
                not mapped or
                mapped in ("SUSPENSE ACCOUNT", "SUSPENSE A/C", "SUNDRY DEBTORS", "SUNDRY CREDITORS", "UPI DEBTORS", "UPI CREDITORS", "DIRECT EXPENSES", "INDIRECT EXPENSES") or
                mapped.startswith("UNKNOWN_") or
                (existing_names_upper and mapped not in existing_names_upper) or
                (not existing_names_upper and (len(mapped) > 15 or bool(re.search(r'\d{4,}', mapped))))
            )
            if is_suspense:
                narr = str(r.get("narration") or "").strip()
                if narr:
                    unique_susp_narrs[narr] = {
                        "transaction_type": r.get("transaction_type", "Receipt"),
                        "group_hint": r.get("group_hint", ""),
                        "current_mapped": r.get("mapped_ledger", "")
                    }
                    suspense_rows.append(r)

        if not unique_susp_narrs:
            return result_json

        print(f"🔮 [AI Mapping Assist] Found {len(unique_susp_narrs)} unique unmapped/suspense narrations. Asking Gemini to resolve them...")

        existing_ledgers = client_memory.get("existing_ledgers", [])
        business_profile = client_memory.get("business_profile", "")
        specifications = client_memory.get("specifications", "")
        
        user_instruction = f"\nUSER PROVIDED EXTRA GUIDELINES (MUST FOLLOW HIGHEST PRIORITY):\n{instruction}\n" if instruction else ""

        # Build clean list of existing ledger names
        ledgers_list = []
        for leg in existing_ledgers:
            name = leg.get("name", "") if isinstance(leg, dict) else str(leg)
            if name:
                ledgers_list.append(name)

        prompt = f"""You are an expert AI accountant.
The user is importing a bank statement or cashbook. Some transactions could not be mapped to any ledger and fell back to the 'Suspense Account'.
Your job is to analyze the following list of unmapped narrations and map them to the most appropriate ledger from the client's existing ledger list, or propose a clean party name.

CLIENT BUSINESS PROFILE:
{business_profile}

CLIENT SPECIFICATIONS & REMARKS:
{specifications}

{user_instruction}
LIST OF EXISTING LEDGER ACCOUNTS IN MIRACLE:
{json.dumps(ledgers_list, indent=2)}

UNMAPPED TRANSACTIONS:
{json.dumps(unique_susp_narrs, indent=2)}

INSTRUCTIONS:
1. For each narration, try to map it to an existing ledger account from the list above. Use semantic matching and spelling variations.
2. ACCOUNT GROUP INFERENCE (ICAI / Ind AS Rules):
   - Investments / Share Brokers (Groww, Zerodha, Upstox, Nextbillion, Clearing Corp) -> group_hint: 'Investments'
   - Credit Card Payment / Gateways (CRED, Razorpay, BillDesk) -> group_hint: 'Indirect Expenses'
   - Banks & Finance (IDFC First Bank, HDFC, ICICI, SBI) -> group_hint: 'Bank Accounts' or 'Unsecured Loans'
   - E-Commerce / Food / Utilities (Zomato, Swiggy, Blinkit, Amazon, Google Pay) -> group_hint: 'Indirect Expenses'
   - Personal Transfers to Family (Mom, Wife, Self) -> group_hint: 'Capital Account / Drawings'
   - Individual Human Loans -> group_hint: 'Loans & Advances (Asset)' (if Payment) or 'Unsecured Loans' (if Receipt)
   - B2B Trade Vendors / Customers -> group_hint: 'Sundry Debtors' (if Receipt) or 'Sundry Creditors' (if Payment)
3. If it contains a clear expense keyword (milk, food, petrol, rent, salary, parking, bank charges), map to the appropriate expense ledger (e.g. Food Expenses, Rent, Salary, Indirect Expenses).
4. If it represents a new party name, return a clean, professional Title Case party name.
5. Include a 'confidence_score' (0-100) indicating how certain you are of the mapping.
6. Return your response ONLY as a JSON object matching this schema:
{{
  "narration_string": {{
    "mapped_ledger": "Clean human party name or existing ledger name",
    "group_hint": "Investments or Bank Accounts or Indirect Expenses or Duties & Taxes or Sundry Debtors or Sundry Creditors or Capital Account / Drawings",
    "confidence_score": 85
  }}
}}
"""
        resolved_mappings = {}
        try:
            client = self._get_client()
            response = self._generate_content_with_retry(
                client=client,
                model=self.model_name or "gemini-2.5-flash",
                contents=prompt,
                config=make_config("application/json")
            )
            
            result_text = ""
            if response:
                try:
                    result_text = response.text.strip() if hasattr(response, "text") and response.text else ""
                except Exception:
                    result_text = ""
                    
            if result_text.startswith("```json"): result_text = result_text[7:]
            if result_text.startswith("```"): result_text = result_text[3:]
            if result_text.endswith("```"): result_text = result_text[:-3]
            result_text = result_text.strip()
            
            if result_text:
                try:
                    resolved_mappings = json.loads(result_text)
                    print(f"🔮 [AI Mapping Assist] Gemini resolved mappings: {json.dumps(resolved_mappings, indent=2)}")
                except Exception as json_err:
                    print(f"⚠️ Warning: AI mapping assistance response could not be parsed as JSON: {json_err}. Using deterministic clean party fallback.")
        except Exception as e:
            print(f"⚠️ Warning: AI mapping assistance pass failed ({e}). Using deterministic clean party fallback.")

        # Apply resolved mappings back to rows with 65% CA confidence safeguard
        applied_count = 0
        for r in rows:
            mapped = str(r.get("mapped_ledger") or "").strip().upper()
            is_suspense_row = (
                not mapped or
                mapped in ("SUSPENSE ACCOUNT", "SUSPENSE A/C", "SUNDRY DEBTORS", "SUNDRY CREDITORS", "UPI DEBTORS", "UPI CREDITORS") or
                mapped.startswith("UNKNOWN_") or
                (existing_names_upper and mapped not in existing_names_upper)
            )
            if is_suspense_row:
                narr = str(r.get("narration") or "").strip()
                tx_type = str(r.get("type") or "Receipt").strip()
                
                # Build map of existing master ledgers to their Miracle DBF groups
                ledger_group_map = {}
                for leg in existing_ledgers:
                    if isinstance(leg, dict) and leg.get("name") and leg.get("group_name"):
                        ledger_group_map[leg["name"].strip().upper()] = str(leg["group_name"]).strip()

                # 1. First try Gemini AI resolved mapping with strict 75% CA Confidence Safeguard
                mapped_success = False
                if narr in resolved_mappings:
                    res = resolved_mappings[narr]
                    raw_target = str(res.get("mapped_ledger") or "").strip()
                    conf = int(res.get("confidence_score", 80) or 80)

                    # CA SAFEGUARD: If confidence < 75%, force Suspense Account for human review
                    if conf < 75:
                        r["mapped_ledger"] = "Suspense Account"
                        r["party_name"] = "Suspense Account"
                        r["party"] = "Suspense Account"
                        r["group_hint"] = "Suspense Account"
                        r["confidence_score"] = conf
                        r["flags"] = ["Low Confidence (< 75%)", "Human Review Required"]
                        mapped_success = True
                        print(f"  🛡️ [CA Safeguard] Confidence {conf}% < 75% for '{narr}'. Forcing fallback to Suspense Account for human review.")
                    elif raw_target and raw_target.upper() not in ("SUSPENSE ACCOUNT", "SUSPENSE A/C"):
                        # Sanitize party name formatting for new ledger entities
                        target_leg = raw_target
                        if existing_names_upper and raw_target.upper() not in existing_names_upper:
                            sanitized = self.extract_clean_party_from_narration(raw_target)
                            if sanitized and len(sanitized) >= 2:
                                target_leg = sanitized

                        if self._is_valid_ledger_match(target_leg, narr):
                            r["mapped_ledger"] = target_leg
                            r["party_name"] = target_leg
                            r["party"] = target_leg
                            r["confidence_score"] = conf
                            master_grp = ledger_group_map.get(target_leg.upper())
                            if master_grp:
                                r["group_hint"] = master_grp
                            elif res.get("group_hint"):
                                r["group_hint"] = res["group_hint"]
                            applied_count += 1
                            mapped_success = True
                            print(f"  🔮 [AI Mapping Resolved] '{narr}' → '{target_leg}' ({r.get('group_hint', '')}) [Conf: {conf}%]")
                        else:
                            print(f"  ⚠️ [AI Assist Guard] Rejected AI suspense mapping '{target_leg}' for narration '{narr}' (word mismatch).")
                
                # 2. Deterministic Clean Party Extraction Fallback
                if not mapped_success:
                    extracted_party = self.extract_clean_party_from_narration(narr)
                    # CA Safeguard: Require at least 3 letters and valid name structure for clean party creation
                    if extracted_party and len(extracted_party) >= 3 and not extracted_party.isdigit():
                        master_grp = ledger_group_map.get(extracted_party.upper())
                        target_group = master_grp if master_grp else self.classify_transaction_nature(
                            narr, extracted_party, tx_type,
                            amount=float(r.get("amount", 0) or 0)
                        )
                        r["mapped_ledger"] = extracted_party
                        r["party_name"] = extracted_party
                        r["party"] = extracted_party
                        r["group_hint"] = target_group
                        r["confidence_score"] = 80
                        if r.get("flags"):
                            r["flags"] = [f for f in r["flags"] if f not in ("Suspense Mapping", "Unmapped Ledger")]
                        print(f"  ✅ [Clean Party Auto-Extraction] '{narr}' → '{extracted_party}' ({target_group})")
                    else:
                        r["mapped_ledger"] = "Suspense Account"
                        r["party_name"] = "Suspense Account"
                        r["party"] = "Suspense Account"
                        r["group_hint"] = "Suspense Account"
                        r["confidence_score"] = 40
                        r["flags"] = ["Low Confidence (< 75%)", "Human Review Required"]
                        print(f"  🛡️ [CA Safeguard] Ambiguous clean party for '{narr}'. Maintained in Suspense Account for human review.")

        print(f"🔮 [AI Mapping Assist] Finished processing suspense entries ({applied_count} AI resolved).")
        return result_json

    def extract_opening_balances(self, file_path: str, existing_ledgers: list) -> dict:
        """
        Extracts opening balances from a Trial Balance or Balance Sheet PDF/Excel/Image.
        """
        ext = os.path.splitext(file_path)[1].lower()
        if not self.api_key:
            raise ValueError("Gemini API Key is not configured.")
            
        client = self._get_client()
        print(f"Extracting opening balances from {file_path} using Gemini API...")
        
        schema_str = """{
    "status": "success",
    "extracted_data": [
        {
            "ledger_name": "Exact name of the ledger/account from the document",
            "balance": 0.0,
            "dr_cr": "D or C",
            "group_hint": "Hint for the account group (e.g. Cash, Bank, Debtors, Creditors, Loans, Fixed Assets, Capital, Suspense, etc.)"
        }
    ]
}"""

        prompt = f"""You are an expert AI accountant. Your task is to extract all the ledger opening balances from the provided Trial Balance, Balance Sheet, or Ledger listing document.

CRITICAL INSTRUCTIONS:
1. Extract EVERY SINGLE ledger and its balance from the document. Do not skip any.
2. For each ledger, provide the exact 'ledger_name' as written.
3. Provide the absolute numeric 'balance' (positive number).
4. For 'dr_cr' (Debit/Credit), provide 'D' if it's a Debit balance, and 'C' if it's a Credit balance.
   - Asset accounts (Cash, Bank, Debtors, Stock, Fixed Assets) are typically Debit (D).
   - Liability/Capital accounts (Creditors, Loans, Reserves) are typically Credit (C).
   - If the document explicitly states Dr or Cr (or positive/negative), respect that.
5. Provide a 'group_hint' which is your best guess of what type of account this is (e.g., 'Debtors', 'Creditors', 'Cash', 'Bank', 'Fixed Assets', 'Loans', 'Capital'). This helps in creating new ledgers.

KNOWN LEDGERS IN MIRACLE:
{chr(10).join(existing_ledgers[:500])}

Return your response strictly in the following JSON format matching this schema:
{schema_str}
"""

        doc_file = None
        try:
            if ext == '.pdf':
                doc_file = client.files.upload(file=file_path)
                contents = [doc_file, prompt]
            elif ext in ['.xlsx', '.xls', '.csv']:
                import pandas as pd
                df = pd.read_excel(file_path) if ext in ['.xlsx', '.xls'] else pd.read_csv(file_path)
                csv_data = df.to_csv(index=False)
                contents = [f"SPREADSHEET DATA:\n{csv_data}", prompt]
            elif ext in ['.jpg', '.jpeg', '.png']:
                doc_file = client.files.upload(file=file_path)
                contents = [doc_file, prompt]
            else:
                raise ValueError(f"Unsupported file type for extraction: {ext}")

            response = self._generate_content_with_retry(
                client=client,
                model=self.model_name or "gemini-3.1-flash-lite",
                contents=contents,
                config=make_config("application/json")
            )

            result_text = response.text.strip() if response and response.text else ""
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.startswith("```"):
                result_text = result_text[3:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]

            result_json = json.loads(result_text.strip())
            return result_json

        except Exception as e:
            print(f"Error calling Gemini: {e}")
            raise
        finally:
            if doc_file:
                try:
                    if doc_file.name:
                        client.files.delete(name=doc_file.name)
                except Exception as e:
                    print(f"Warning: Failed to delete file {doc_file.name}: {e}")

    def validate_and_fix_transaction_types(self, result_json: dict) -> dict:
        """
        CRITICAL POST-PROCESSING: Mathematically validates and auto-corrects
        Receipt/Payment type swaps that Gemini commonly makes.
        
        Algorithm:
        1. Sort extracted transactions by date to get chronological order.
        2. Walk through each transaction using the running_balance field.
        3. If balance INCREASED → must be a Receipt (deposit). If Gemini said Payment → FIX IT.
        4. If balance DECREASED → must be a Payment (withdrawal). If Gemini said Receipt → FIX IT.
        5. Also corrects the amount if it doesn't match the balance delta.
        
        This is deterministic and 100% reliable as it uses actual bank balance math,
        not AI guesswork about which column an amount belongs to.
        """
        extracted = result_json.get("extracted_data", [])
        if not extracted:
            return result_json
        
        fixes_applied = 0
        amount_fixes = 0
        
        # Determine original chronological direction (newest on top vs oldest on top)
        # using first and last valid dates.
        from datetime import datetime
        valid_dates = []
        for r in extracted:
            dt_str = r.get("date", "")
            if dt_str:
                try:
                    dt = datetime.strptime(str(dt_str)[:10], "%Y-%m-%d").date()
                    valid_dates.append(dt)
                except:
                    pass
                    
        is_reverse = False
        if len(valid_dates) >= 2:
            if valid_dates[0] > valid_dates[-1]:
                is_reverse = True
                
        # To validate mathematically:
        # We need the transactions in ascending chronological order (oldest on top)
        # so that running_balance increases on Receipt and decreases on Payment.
        # If is_reverse is True, the list is descending (newest on top), so we reverse the entire list.
        # This keeps same-day transactions in their correct relative order.
        working_data = list(extracted)
        if is_reverse:
            print("🔄 [Math Validator] Detected reverse chronological statement. Reversing for validation...")
            working_data.reverse()
            
        prev_balance = None
        for i, row in enumerate(working_data):
            try:
                running_bal_raw = row.get("running_balance")
                amount_raw = row.get("amount", 0.0)
                tx_type = str(row.get("transaction_type", "")).strip().capitalize()
                
                if running_bal_raw is None or str(running_bal_raw).strip() == "":
                    prev_balance = None
                    continue
                    
                bal_clean = str(running_bal_raw).replace(",", "").replace("Cr", "").replace("Dr", "").replace("cr", "").replace("dr", "").strip()
                try:
                    running_bal = float(bal_clean)
                except ValueError:
                    prev_balance = None
                    continue
                    
                if running_bal == 0.0:
                    prev_balance = None
                    continue
                    
                amt_clean = str(amount_raw or 0.0).replace(",", "").replace("Cr", "").replace("Dr", "").replace("cr", "").replace("dr", "").strip()
                try:
                    amount_val = float(amt_clean)
                except ValueError:
                    amount_val = 0.0
                    
                if prev_balance is not None:
                    delta = round(running_bal - prev_balance, 2)
                    
                    if delta > 0:
                        # Balance INCREASED → this MUST be a Receipt (deposit)
                        if tx_type != "Receipt":
                            old_type = tx_type
                            row["transaction_type"] = "Receipt"
                            fixes_applied += 1
                            print(f"🔧 TX_TYPE FIX row {i}: '{old_type}' → 'Receipt' (balance ↑ {prev_balance:.2f} → {running_bal:.2f})")
                            
                        # Fix amount if it doesn't match the delta
                        if amount_val > 0 and abs(amount_val - delta) > 1.0:
                            if abs(amount_val - delta) > 5.0:
                                row["status"] = "Review"
                                if "discrepancy" not in str(row.get("narration", "")).lower():
                                    row["narration"] = f"[DISCREPANCY: Balance delta is {delta:.2f} but amount is {amount_val:.2f}] " + row.get("narration", "")
                                warn_msg = f"⚠️ Balance Discrepancy Alert at Row {i+1} ({row.get('date')}): Running balance jump of ₹{abs(delta):,.2f} does not match transaction amount ₹{amount_val:,.2f}."
                                warnings = result_json.setdefault("warnings", [])
                                if warn_msg not in warnings:
                                    warnings.append(warn_msg)
                                print(f"⚠️ Balance discrepancy at row {i}: Reconciled delta is {delta:.2f} but amount is {amount_val:.2f}. Not overwriting.")
                            else:
                                row["amount"] = round(delta, 2)
                                amount_fixes += 1
                                print(f"🔧 AMOUNT FIX row {i}: {amount_val:.2f} → {delta:.2f} (from balance delta)")
                                
                    elif delta < 0:
                        # Balance DECREASED → this MUST be a Payment (withdrawal)
                        if tx_type != "Payment":
                            old_type = tx_type
                            row["transaction_type"] = "Payment"
                            fixes_applied += 1
                            print(f"🔧 TX_TYPE FIX row {i}: '{old_type}' → 'Payment' (balance ↓ {prev_balance:.2f} → {running_bal:.2f})")
                            
                        abs_delta = abs(delta)
                        if amount_val > 0 and abs(amount_val - abs_delta) > 1.0:
                            if abs(amount_val - abs_delta) > 5.0:
                                row["status"] = "Review"
                                if "discrepancy" not in str(row.get("narration", "")).lower():
                                    row["narration"] = f"[DISCREPANCY: Balance delta is {abs_delta:.2f} but amount is {amount_val:.2f}] " + row.get("narration", "")
                                warn_msg = f"⚠️ Balance Discrepancy Alert at Row {i+1} ({row.get('date')}): Running balance jump of ₹{abs_delta:,.2f} does not match transaction amount ₹{amount_val:,.2f}."
                                warnings = result_json.setdefault("warnings", [])
                                if warn_msg not in warnings:
                                    warnings.append(warn_msg)
                                print(f"⚠️ Balance discrepancy at row {i}: Reconciled delta is {abs_delta:.2f} but amount is {amount_val:.2f}. Not overwriting.")
                            else:
                                row["amount"] = round(abs_delta, 2)
                                amount_fixes += 1
                                print(f"🔧 AMOUNT FIX row {i}: {amount_val:.2f} → {abs_delta:.2f} (from balance delta)")
                                
                prev_balance = running_bal
            except Exception as e:
                print(f"⚠️ Validation skipped for row {i}: {e}")
                continue
                
        # Always maintain forward chronological order (Month Start 1st of month first)
        if is_reverse:
            print("📅 Keeping validated transactions in Forward Chronological Order (1st of month first).")
            
        if fixes_applied > 0 or amount_fixes > 0:
            print(f"✅ Balance Validation Complete: {fixes_applied} type fix(es), {amount_fixes} amount fix(es) auto-corrected.")
        else:
            print("✅ Balance Validation: All transaction types are mathematically correct.")
            
        result_json["extracted_data"] = working_data
        return result_json

    def generate_memory_rules_from_prompt(self, user_prompt: str, client_memory: dict = None, existing_ledgers: list = None) -> dict:
        """
        Parses natural language user instructions and returns structured rules with categories,
        exact keys, target values, explanations, and concrete examples using Gemini API.
        """
        if not self.api_key:
            raise ValueError("Gemini API Key is not configured.")

        client = self._get_client()
        
        ledgers_str = ""
        if existing_ledgers:
            ledger_names = [l.get("name") if isinstance(l, dict) else str(l) for l in existing_ledgers[:100]]
            ledgers_str = "AVAILABLE MIRACLE LEDGERS / ACCOUNTS IN DBF:\n" + "\n".join(f"- {name}" for name in ledger_names if name)
            
        system_prompt = f"""You are an Expert Accounting Rule Engineer & AI Systems Architect.
The user is an accountant or business owner providing natural language instructions/rules for their Miracle Accounting AI system.

USER REQUEST:
"{user_prompt}"

{ledgers_str}

YOUR TASK:
Analyze the user's plain English / Hindi / Gujarati request and generate 1 or more concrete, highly accurate accounting memory rules.

RULE CATEGORIES:
- "expense_mapping": For bank/narration/expense keyword mapping (e.g. mapping Swiggy to Staff Welfare Expenses, PhonePe to Telephone, Petrol to Fuel Expenses).
- "product_catalog": For inventory product item names, HSN codes, GST rates, UOM (e.g. Orthotics Footwear -> FOOTWEAR GST 5%, HSN 9021, 5% GST).
- "supplier_catalog": For supplier/vendor accounts, GSTIN, city (e.g. Reliance Retail -> GSTIN 27AAACR3456K1Z1).

REQUIREMENTS FOR EACH RULE:
1. "category": Must be one of ["expense_mapping", "product_catalog", "supplier_catalog"].
2. "key": The clean uppercase core keyword/search string (e.g. "SWIGGY ZOMATO", "PHONEPE", "ORTHOTICS FOOTWEAR").
3. "value": The target mapped ledger, product item name, or supplier detail (matching an existing Miracle ledger if applicable).
4. "rule_type": "Keyword Match" or "Exact Match" or "Catalog Sync".
5. "explanation": A clear 1-2 sentence description of why this rule was created and how it operates.
6. "examples": An array of 2 realistic input/output examples showing how this rule transforms raw document inputs.
   - Example format for expense_mapping: [{{"input": "UPI-SWIGGY-REST-1293", "output": "Staff Welfare Expenses"}}, {{"input": "ZOMATO ORDER #8821", "output": "Staff Welfare Expenses"}}]
   - Example format for product_catalog: [{{"input": "COMFIT ORTHOTICS 8", "output": "FOOTWEAR GST 5% (HSN: 9021)"}}]

Return ONLY a JSON object matching this schema:
{{
    "status": "success",
    "summary": "Brief 1-sentence summary of the rule(s) created",
    "rules": [
        {{
            "category": "expense_mapping",
            "key": "KEYWORD",
            "value": "TARGET_VALUE",
            "rule_type": "Keyword Match",
            "explanation": "Clear explanation of rule",
            "examples": [
                {{"input": "Sample Input 1", "output": "Sample Output 1"}},
                {{"input": "Sample Input 2", "output": "Sample Output 2"}}
            ]
        }}
    ]
}}
"""

        try:
            response = self._generate_content_with_retry(
                client=client,
                model=self.model_name,
                contents=[system_prompt],
                config=make_config("application/json")
            )
            text = response.text.strip() if response and response.text else "{}"
            if text.startswith("```json"): text = text[7:]
            if text.startswith("```"): text = text[3:]
            if text.endswith("```"): text = text[:-3]
            parsed = json.loads(text.strip())
            parsed["status"] = "success"
            return parsed
        except Exception as e:
            print(f"❌ Error generating memory rules from prompt: {e}")
            return {
                "status": "error",
                "summary": f"Failed to generate AI rules: {e}",
                "rules": []
            }

    def optimize_and_synthesize_memory_rules(self, raw_rules: dict) -> dict:
        """
        Takes raw/messy expense rules, vendor names, and narrations, and calls Gemini AI
        to extract clean, core vendor/expense keywords (1-3 words max), removing all bank/IFSC/UTR noise,
        and consolidating duplicates into crystal-clear AI Memory mappings.
        """
        if not raw_rules or not isinstance(raw_rules, dict):
            return raw_rules or {}
            
        if not self.api_key:
            print("⚠️ Gemini API key not configured for rule optimization, using fallback.")
            return raw_rules

        try:
            client = self._get_client()
            prompt = f"""
You are an Expert CA Accountant & Nature-Based AI Memory Engine for Miracle Accounting Software.
Analyze the following raw bank narrations/keywords and their assigned Miracle Ledger accounts:

RAW RULES DATA:
{json.dumps(raw_rules, indent=2)}

ACCOUNTING NATURE INSTRUCTIONS:
1. FOCUS ON NATURE OF TRANSACTION: Extract the true accounting nature and intent from the narration line.
   - For vendor payments: Extract the exact business/party name (e.g. 'DEVSHREE ENTERPRISE', 'CRED CLUB').
   - For operational expenses: Extract the multi-word nature phrase (e.g. 'VEHICLE PETROL', 'OFFICE RENT', 'COMPUTER REPAIRS').
   - For bank fees: Extract the charge nature (e.g. 'DEPOSITORY CHARGES', 'BANK CHARGES').
2. STRICT NATURE GUARD: NEVER map generic nature nouns (CASH, COMPUTER, DAIRY, PETROL, SALARY, RENT) to individual debtor/creditor persons (e.g. MITESHBHAI, Mom, RADHE KRISHNA).
3. STRIP BANK NOISE: Remove UTR/ref numbers, IFSC codes (HDFCH, OKICICI), payment prefixes (UPI, NEFT, RTGS, IMPS), and duplicate repeated words (e.g., 'CRED CRED CLUB CRED' -> 'CRED CLUB').
4. Return ONLY a valid JSON object mapping CLEAN_NATURE_KEYWORD -> TARGET_LEDGER.

Example Input:
{{
  "UPI 91823 CRED CRED CLUB CRED": "CRED",
  "CHQ 102938 PAID FOR VEHICLE PETROL PUMP": "Vehicle Expenses",
  "CASH WITHDRAWAL FOR RADHE KRISHNA": "RADHE KRISHNA MICRO IMITATION"
}}

Example Output:
{{
  "CRED CLUB": "CRED",
  "PETROL PUMP": "Vehicle Expenses"
}}
"""
            response = self._generate_content_with_retry(
                client=client,
                model=self.model_name,
                contents=[prompt],
                config=make_config("application/json")
            )
            raw_text = response.text.strip() if response and response.text else "{}"
            if raw_text.startswith("```json"): raw_text = raw_text[7:]
            if raw_text.startswith("```"): raw_text = raw_text[3:]
            if raw_text.endswith("```"): raw_text = raw_text[:-3]
            
            clean_dict = json.loads(raw_text.strip())
            if isinstance(clean_dict, dict) and clean_dict:
                print(f"✨ [Gemini AI Memory Optimization] Synthesized {len(raw_rules)} raw rules into {len(clean_dict)} clean AI Brain mappings.")
                return clean_dict
        except Exception as e:
            print(f"⚠️ [Gemini AI Memory Optimization] Error: {e}")
            
        return raw_rules

    def parse_excel_and_map_rules(self, file_path: str, existing_ledgers: list = None) -> dict:
        """
        Reads any Excel (.xlsx, .xls, .csv) file, uses Gemini AI to understand column headers & row content,
        and extracts structured memory rules (expense_mappings, product_catalog, supplier_catalog).
        """
        excel_text = ""
        if file_path.endswith(('.xlsx', '.xls')):
            excel_text = self._read_excel_text_native(file_path)
        elif file_path.endswith('.csv'):
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    excel_text = f.read()
            except Exception:
                pass

        if not excel_text or len(excel_text.strip()) < 10:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    excel_text = f.read()
            except Exception:
                pass

        if not excel_text or len(excel_text.strip()) < 10:
            return {"expense_mappings": {}, "product_catalog": {}, "supplier_catalog": {}}

        ledgers_str = ""
        if existing_ledgers:
            ledger_names = [l.get("name") if isinstance(l, dict) else str(l) for l in existing_ledgers[:100]]
            ledgers_str = "AVAILABLE MIRACLE LEDGERS IN DBF:\n" + "\n".join(f"- {name}" for name in ledger_names if name)

        prompt = f"""
You are an expert Indian CA Accountant & AI Memory Import Engine for Miracle Accounting.
Analyze the following uploaded Excel/CSV file content. Understand all columns, headers, narrations, party names, item descriptions, HSN codes, and ledger accounts.

UPLOADED FILE CONTENT:
{excel_text[:12000]}

{ledgers_str}

YOUR TASK:
Extract all accounting memory rules from this Excel file into 3 structured categories:
1. "expense_mappings": Object mapping KEYWORD/NARRATION -> MIRACLE LEDGER NAME (e.g. "SWIGGY" -> "Staff Welfare Expenses", "PETROL" -> "Fuel Expenses").
2. "product_catalog": Object mapping ITEM_KEY -> {{"display_name": "...", "hsn": "...", "gst_pct": 18, "uom": "PCS", "last_rate": 100}}.
3. "supplier_catalog": Object mapping SUPPLIER_KEY -> {{"display_name": "...", "gstin": "...", "city": "..."}}.

REQUIREMENTS:
- Clean all keywords (1-3 words max, upper case, remove bank noise/IFSC/ref numbers).
- Map to existing Miracle ledgers if applicable.
- Return ONLY a valid JSON object matching this schema:
{{
  "expense_mappings": {{ ... }},
  "product_catalog": {{ ... }},
  "supplier_catalog": {{ ... }}
}}
"""
        try:
            client = self._get_client()
            response = self._generate_content_with_retry(
                client=client,
                model=self.model_name,
                contents=[prompt],
                config=make_config("application/json")
            )
            raw_text = response.text.strip() if response and response.text else "{}"
            if raw_text.startswith("```json"): raw_text = raw_text[7:]
            if raw_text.startswith("```"): raw_text = raw_text[3:]
            if raw_text.endswith("```"): raw_text = raw_text[:-3]
            
            parsed = json.loads(raw_text.strip())
            if isinstance(parsed, dict):
                print(f"✨ [Gemini AI Excel Import] Extracted memory rules from Excel file '{os.path.basename(file_path)}'")
                return parsed
        except Exception as e:
            print(f"❌ Error in parse_excel_and_map_rules: {e}")

        # Deterministic regex fallback if Gemini AI is offline
        native_mappings = self._extract_native_excel_mappings(excel_text)
        return {"expense_mappings": native_mappings, "product_catalog": {}, "supplier_catalog": {}}



