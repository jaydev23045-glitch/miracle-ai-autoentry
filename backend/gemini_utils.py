"""
Gemini Service Utilities & Spec Cache Handler
Provides JSON repair, bounded LRU caching, ledger validation, and prompt template caching.
"""

import re
import threading
from collections import OrderedDict

# ── Clean Letters Helper ──────────────────────────────────────────────────────
def clean_letters(s: str) -> str:
    """Strips all non-alphanumeric characters for clean letter-sequence comparison."""
    return re.sub(r"[^A-Z0-9]", "", str(s).upper())


# ── JSON Repair Utility ────────────────────────────────────────────────────────
def repair_json_string(json_str: str) -> str:
    """
    Robust multi-pass JSON repair utility.
    Strips markdown blocks, extracts JSON payload boundaries, injects missing commas,
    cleans non-ASCII hallucinations, and removes trailing commas.
    """
    if not json_str:
        return "{}"

    text = json_str.strip()

    # 1. Remove markdown code blocks
    if "```" in text:
        text = re.sub(r"```(?:json)?\s*", "", text)
        text = re.sub(r"```\s*$", "", text)

    # 2. Extract substring between first '{' and last '}'
    first_curly = text.find("{")
    last_curly = text.rfind("}")
    if first_curly != -1 and last_curly != -1 and last_curly > first_curly:
        text = text[first_curly : last_curly + 1]

    # 3. Inject missing commas between adjacent objects (e.g. `} {` or `} \n {`)
    text = re.sub(r"\}\s*\{", "},{", text)

    # 4. Strip stray non-ASCII hallucinated words appearing between JSON elements
    lines = []
    for line in text.splitlines():
        line_cleaned = re.sub(
            r"(?<=[\}\],])\s*[^\x00-\x7F]+\s*(?=[\{\[\"]|$)", "", line
        )
        line_cleaned = re.sub(r"^[^\x00-\x7F\s\{\}\[\]\",]+$", "", line_cleaned)
        line_cleaned = re.sub(r"[^\x00-\x7F]+", "", line_cleaned)
        if line_cleaned.strip():
            lines.append(line_cleaned)
    text = "\n".join(lines)

    # 5. Inject missing commas between adjacent objects (e.g. `} {` or `} \n {`)
    text = re.sub(r"\}\s*\{", "},{", text)
    text = re.sub(r"\}\s*\"", '},"', text)
    text = re.sub(r"\]\s*\{", "],{", text)

    # 6. Fix trailing commas before closing braces/brackets
    text = re.sub(r",\s*\}", "}", text)
    text = re.sub(r",\s*\]", "]", text)

    return text.strip()


# ── Ledger Match Validator (Issue #5 Fix) ─────────────────────────────────────
def is_valid_ledger_match(mapped_name: str, narr: str, bank_name: str = "") -> bool:
    """
    Validates whether a mapped ledger account name is physically present inside the narration text.
    Supports space-insensitive matching.
    Fixed in Issue #5: Removed soft-fallback that blindly returned True for any name >= 3 chars.
    """
    if not mapped_name or not narr:
        return False

    mapped_upper = mapped_name.upper().strip()

    # 0. Anti-Dummy & Generic Filler Ledger Guard
    BANNED_DUMMY_LEDGERS = {
        "REMARK",
        "REMARKS",
        "SUSPENSE",
        "SUSPENSE ACCOUNT",
        "SUSPENSE A/C",
        "DUMMY",
        "UNKNOWN",
        "UNKNOWN_EXPENSE",
        "UNKNOWN_PARTY",
        "PART PAYMENT",
        "NARRATION",
        "NOTE",
        "PAYMENT",
        "RECEIPT",
        "SUNDRY DEBTORS",
        "SUNDRY CREDITORS",
        "INDIRECT EXPENSES",
        "DIRECT EXPENSES",
        "INDIRECT INCOME",
        "DIRECT INCOME",
        "SALES ACCOUNTS",
        "PURCHASE ACCOUNTS",
        "BANK ACCOUNTS",
        "CASH-IN-HAND",
        "CASH ACCOUNT",
        "LOANS & ADVANCES",
        "LOANS & ADVANCES (ASSET)",
        "UNSECURED LOANS",
        "SECURED LOANS",
        "CAPITAL ACCOUNT",
        "CAPITAL ACCOUNT / DRAWINGS",
        "DUTIES & TAXES",
        "PROVISIONS",
        "CURRENT LIABILITIES",
        "CURRENT ASSETS",
        "FIXED ASSETS",
        "INVESTMENTS",
        "BRANCH / DIVISIONS",
        "CHEQUE DEPOSIT",
        "CHQ DEP",
        "CHQ DEPOSIT",
        "CHEQUE CLEARING",
        "CLEARING DEPOSIT",
        "CLEARING",
        "CLG DEPOSIT",
        "CHQ RETURN",
        "CHEQUE RETURN",
        "CHQ RET",
        "CHEQUE BOUNCE",
        "INWARD CHEQUE",
        "OUTWARD CHEQUE",
        "NEFT DEPOSIT",
        "RTGS DEPOSIT",
        "IMPS DEPOSIT",
    }
    if mapped_upper in BANNED_DUMMY_LEDGERS:
        return False

    # 1. Anti-Bank Contra Check: If mapped to the bank itself, reject!
    if bank_name and bank_name.upper() in mapped_upper:
        return False

    # 2. Universal 100-Client System & Generic Ledger Regex Classifier
    SYSTEM_LEDGER_PATTERNS = [
        r"\b(BANK\s*CHARG|CHARGES|INTEREST|SWEEP|FD|FIXED\s*DEPOSIT|MUTUAL\s*FUND|INVESTMENT|LOAN|ADVANCE|CAPITAL|DRAWING|OVERDRAFT|OD|CC|LOAN\s*A/C)\b",
        r"\b(SALARY|WAGES|STIPEND|BONUS|PF|ESI|WELFARE|INCENTIVE|REMUNERATION|STAFF|EMPLOYEE|ALLOWANCE|GRATUITY)\b",
        r"\b(RENT|ELECTRICITY|POWER|WATER|GAS|FUEL|PETROL|DIESEL|TELEPHONE|MOBILE|BROADBAND|INTERNET|WIFI|LEASE|OFFICE\s*EXP)\b",
        r"\b(GST|CGST|SGST|IGST|CESS|TDS|TCS|DUTY|DUTIES|TAX|INCOME\s*TAX|PROFESSIONAL\s*TAX|PTAX|PENALTY|LATE\s*FEE|CUSTOMS)\b",
        r"\b(REPAIR|REPAIRS|MAINTENANCE|SERVICE|SERVICING|WINDING|TOOLS|HARDWARE|SPARES|FITTING|EQUIPMENT|MACHINERY|VEHICLE|TESTING|CALIBRATION|LAB|WEIGHTBRIDGE|CUTTING)\b",
        r"\b(FREIGHT|CARTAGE|OCTROI|LOADING|UNLOADING|TRANSPORT|CONVEYANCE|TRAVEL|TRAVELLING|LODGING|BOARDING|COURIER|POSTAGE|DELIVERY)\b",
        r"\b(PRINTING|STATIONERY|SOFTWARE|SUBSCRIPTION|LICENSE|DOMAIN|HOSTING|CLOUD|IT\s*EXPENSE|LEGAL|AUDIT|PROFESSIONAL|FEES|COMMISSION|BROKERAGE|ADVERTISEMENT|PROMOTION|MARKETING)\b",
        r"\b(EXPENSE|EXPENSES|EXP|INCOME|CHARGES|SUSPENSE|MISC|ROUND\s*OFF|DISCOUNT|REBATE|CASH|ACCOUNT|A/C)\b",
    ]

    for pattern in SYSTEM_LEDGER_PATTERNS:
        if re.search(pattern, mapped_upper):
            return True

    mapped_clean = clean_letters(mapped_name)
    narr_clean = clean_letters(narr)

    # 1. Full space-insensitive name match
    if len(mapped_clean) >= 3 and mapped_clean in narr_clean:
        return True

    # 2. Key word letter sequence match
    mapped_words = [
        w
        for w in re.split(r"[\s\-\/@._]+", mapped_upper)
        if len(w) >= 3
        and w not in ("LTD", "PVT", "INC", "CORP", "BANK", "ACCOUNT", "A/C")
    ]
    if not mapped_words:
        return False

    for w in mapped_words:
        w_clean = clean_letters(w)
        if len(w_clean) >= 3 and w_clean in narr_clean:
            return True

    return False


# ── Bounded Thread-Safe True LRU Spec File Cache (Issue #14 Fix) ───────────────
_SPEC_FILE_CACHE = OrderedDict()
_SPEC_FILE_CACHE_LOCK = threading.Lock()
_SPEC_FILE_CACHE_MAX_SIZE = 100


def get_cached_spec(file_hash: str) -> str | None:
    """Gets cached spec text using true LRU eviction (moves accessed item to end)."""
    with _SPEC_FILE_CACHE_LOCK:
        if file_hash in _SPEC_FILE_CACHE:
            _SPEC_FILE_CACHE.move_to_end(file_hash)
            return _SPEC_FILE_CACHE[file_hash]
        return None


def store_cached_spec(file_hash: str, result_text: str):
    """Stores cached spec text using true LRU eviction (pops least recently used item)."""
    with _SPEC_FILE_CACHE_LOCK:
        if file_hash in _SPEC_FILE_CACHE:
            _SPEC_FILE_CACHE.move_to_end(file_hash)
        _SPEC_FILE_CACHE[file_hash] = result_text
        if len(_SPEC_FILE_CACHE) > _SPEC_FILE_CACHE_MAX_SIZE:
            _SPEC_FILE_CACHE.popitem(last=False)  # Evict oldest (LRU)


# ── Prompt Template Cache (Issue #9 Fix) ───────────────────────────────────────
_PROMPT_TEMPLATE_CACHE: dict[str, tuple[str, str]] = {}
_PROMPT_CACHE_LOCK = threading.Lock()


def get_cached_prompt_static_parts(module: str, rules_str: str, schema_str: str) -> tuple[str, str]:
    """Caches static prompt header and schema per module to avoid rebuilding strings every call."""
    with _PROMPT_CACHE_LOCK:
        if module not in _PROMPT_TEMPLATE_CACHE:
            header = f"You are an Expert AI Accountant extracting structured financial data for the '{module}' module."
            _PROMPT_TEMPLATE_CACHE[module] = (header, schema_str)
        return _PROMPT_TEMPLATE_CACHE[module]
