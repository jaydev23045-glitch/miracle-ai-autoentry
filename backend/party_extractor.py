"""
Universal Narration Party Extractor
Parses Indian bank statement narrations (UPI, IMPS, NEFT, RTGS, Transfers)
to extract the true party/vendor/person name.
Loads name parts dataset from backend/data/indian_names.json (Issue #12 Fix).
"""

import json
import os
import re

# ── Load Indian Name Parts Dataset ───────────────────────────────────────────
_COMMON_NAME_PARTS: list[str] = []

def _load_name_parts() -> list[str]:
    global _COMMON_NAME_PARTS
    if _COMMON_NAME_PARTS:
        return _COMMON_NAME_PARTS
    json_path = os.path.join(os.path.dirname(__file__), "data", "indian_names.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                _COMMON_NAME_PARTS = json.load(f)
                return _COMMON_NAME_PARTS
        except Exception:
            pass
    # Fallback default
    _COMMON_NAME_PARTS = [
        "AATHIRA", "CHANDRAN", "PALLAVI", "PANCHAL", "RUPALI", "WAGH", "NIKHILA",
        "KIRALE", "PAWAN", "KUMAR", "SHAH", "SHASHANK", "GAWDE", "GAWD", "SAMPADA",
        "VEDAK", "SWATI", "TILAK", "RINDA", "FERNS", "JAYEETA", "DOKERAJU", "SAURABH",
        "PANDEY", "HIRAL", "CHANDARANA", "ANJANAVELIL", "VARSHA", "SHRIKANT", "DANGE",
        "NAMRATA", "GANGTOK", "PRADEEP", "SHAW", "SUNEETA", "HARSHA", "PAREKH", "DIGAMBAR",
        "KHETLE", "SONAWANE", "JAYWANT", "TAUSIF", "SIRAJ", "SHAIKH", "CHANDRAKANT",
        "PARTE", "BONY", "YALLAPPA", "KUNCHI", "KORVE", "MASALI", "ANAND", "SHARMA",
        "SANJAY", "DEEPAK", "RARESH", "RAJESH", "PRIYA", "AMJAD", "MITUL", "MANISH",
        "HASMUKH", "SHANTILAL", "MEENA", "PATIDAR", "KALAMBE", "PANDURANG", "NATROX",
        "GIBZ", "VANIA", "VARUN", "SINGH", "PATEL", "VERMA", "GUPTA", "JAIN", "MEHTA",
        "DESHMUKH", "CHAVAN", "PAWAR", "JADHAV", "MORE", "JOSHI", "KULKARNI", "PATIL",
        "AGRAWAL", "SURI", "BHATIA", "KAPOOR", "KHAN", "RODRIGUES", "FERNANDES",
        "ALMEIDA", "DOUZA", "SOARES", "CHAUDHARY", "REDDY", "NAIR", "MENON", "PILLAI"
    ]
    return _COMMON_NAME_PARTS


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

    # Delegate to BankEntityRecognizer for primary NER extraction if available
    try:
        from modules.bank.parser import BankEntityRecognizer
        clean_entity, _ = BankEntityRecognizer.extract_vendor_entity(narr_str)
        if clean_entity:
            sanitized = _sanitize_party(clean_entity)
            if sanitized and len(sanitized) >= 3 and not sanitized.isdigit():
                return sanitized
    except Exception:
        pass

    # 0. Strip leading transaction type prefixes and DEBIT/CREDIT tokens
    narr_str = re.sub(
        r"^(ACH\s*[CD]?\s*[-_]?\s*|ACH\s*DR\s*[-_]?\s*|ACH\s*CR\s*[-_]?\s*|NEFT\s*[DR|CR]*\s*[-_]?\s*|RTGS\s*[DR|CR]*\s*[-_]?\s*|IMPS\s*[-_]?\s*|TPT\s*[-_]?\s*|DEBIT\s*[-_]?\s*|CREDIT\s*[-_]?\s*)",
        "",
        narr_str,
        flags=re.IGNORECASE,
    ).strip()
    narr_str = re.sub(r"\b(DEBIT|CREDIT|DR|CR)\b", " ", narr_str, flags=re.IGNORECASE).strip()

    # 1. Pre-clean @handle and VPA domain suffixes
    raw_no_handle = re.sub(
        r"@[A-Za-z0-9_\-\.\s]{1,25}(?:AXIS|ICICI|HDFC|DFCBANK|FCBANK|SBI|YES|PAYTM|YBL|KOTAK|UPI|PTYES|YESCRED|NAVIAXIS|PTAXIS|WAAXIS|AXL|IPL|IBL|OKAXIS|OKICICI|OKSBI|MAHB|BARB|INDB|TMBL|SVCB)",
        "",
        narr_str,
        flags=re.IGNORECASE,
    )
    raw_no_handle = re.sub(r"@[A-Za-z0-9_\-\.]+", "", raw_no_handle)
    raw_no_handle = re.sub(
        r"[\.\-](?:SBI|OKSBI|OKICICI|OKAXIS|KHDFCBANK|YBL|KOTAK|PAYTM|PHONEPE|GPAY|BHIM|PTYES|AXIS|ICICI|HDFC)\b",
        "",
        raw_no_handle,
        flags=re.IGNORECASE,
    )
    raw_no_handle = re.sub(
        r"\b(X{2,10}|XXXXX)\b", "", raw_no_handle, flags=re.IGNORECASE
    )
    raw_no_handle = re.sub(
        r"\b(OKH|OKICIC|OKICICI|OKAXIS|OKSBI|KHDFCBANK|FCBANK|DFCBANK|KOTAK|PAYTM|PHONEPE|GPAY|BHIM|PTYES|YESCRED|NAVIAXIS|PTAXIS|WAAXIS|AXL|YBL|IPL|IBL)\b",
        "",
        raw_no_handle,
        flags=re.IGNORECASE,
    )

    # 2. Strip standard IFSC codes
    raw_no_ifsc = re.sub(
        r"\b[A-Za-z]{4}0[A-Za-z0-9]{6}\b", "", raw_no_handle, flags=re.IGNORECASE
    )
    raw_no_ifsc = re.sub(
        r"\b[A-Za-z]{4}[0-9][A-Za-z0-9]{4,6}\b",
        "",
        raw_no_ifsc,
        flags=re.IGNORECASE,
    )

    # 3. Strip long standalone numeric ref numbers
    raw_no_ids = re.sub(r"\b\d{11,}\b", "", raw_no_ifsc)

    NOISE_TOKENS = {
        "UPI", "IMPS", "NEFT", "RTGS", "P2A", "P2P", "MOB", "DR", "CR", "NOREF",
        "PAYMENT", "RECEIPT", "TRANSFER", "TRF", "FRM", "TO", "INB", "BY", "CHQ",
        "PAID", "YESB", "SBIN", "HDFC", "ICIC", "UTIB", "KKBK", "BARB", "CNRB",
        "UBIN", "PUNB", "TM", "AB", "TPT", "NETBANK", "NETB", "HDFCH", "HDFCN",
        "HDFCE", "HDFCBANK", "ICICI", "AXIS", "MAHB", "SVCB", "TMBL", "INDB", "CCBL",
        "OKAXIS", "OKICICI", "OKHDFCBANK", "OKSBI", "PTYES", "YESCRED", "NAVIAXIS",
        "PTAXIS", "WAAXIS", "AXL", "YBL", "IPL", "IBL", "KOTAK", "PAYTM", "PHONEPE",
        "GPAY", "BHIM", "SENT", "USING", "REMARKS", "REMARK", "INSTAALERTCHG",
        "SMS", "CDT", "HAND", "LOAN", "SELF", "NEHRU", "NAGAR", "KURLA", "EAST",
        "WEST", "BRANCH", "KAXIS", "IS", "CI", "FCBANK", "KHDFCBANK", "OKICIC",
        "OKS", "OKI", "OKA", "XIS"
    }

    MONTH_NAMES = {
        "JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT",
        "NOV", "DEC", "JANUARY", "FEBRUARY", "MARCH", "APRIL", "JUNE", "JULY",
        "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"
    }

    CORPORATE_MAP = {
        "PVT LTD": "Pvt Ltd",
        "PRIVATE LIMITED": "Private Limited",
        "LLP": "LLP",
        "ENTERPRISES": "Enterprises",
        "TRADERS": "Traders",
        "INDUSTRIES": "Industries",
        "SERVICES": "Services",
        "SOLUTIONS": "Solutions",
        "TECHNOLOGIES": "Technologies",
        "MOTORS": "Motors",
        "HARDWARE": "Hardware",
        "STORES": "Stores",
        "AGENCIES": "Agencies",
        "LOGISTICS": "Logistics",
    }

    name_parts = _load_name_parts()

    def _sanitize_party(candidate: str) -> str:
        if not candidate:
            return ""
        cand = re.sub(r"[\s\-]\d+$", "", candidate)

        tokens = []
        for w in re.split(r"[\s\-\/@._]+", cand):
            w_clean = w
            if not re.match(r"^[A-Z]{2}\d{4,6}$", w, re.IGNORECASE):
                w_clean = re.sub(r"(?<=[A-Za-z]{3})\d{1,4}$", "", w)
            w_upper = w_clean.upper()

            if not w_clean or w_upper in NOISE_TOKENS or w_upper in MONTH_NAMES:
                continue
            if w_clean.isdigit() and len(w_clean) != 10:
                continue
            tokens.append(w_clean)

        clean_raw = " ".join(tokens).strip()
        if not clean_raw:
            return ""

        BANNED_PARTY_WORDS = {
            "REMARK", "REMARKS", "SUSPENSE", "SUSPENSE ACCOUNT", "SUSPENSE A/C", "DUMMY", "UNKNOWN",
            "UNKNOWN_EXPENSE", "UNKNOWN_PARTY", "PART PAYMENT", "NARRATION", "NOTE", "PAYMENT", "RECEIPT",
            "SUNDRY DEBTORS", "SUNDRY CREDITORS", "INDIRECT EXPENSES", "DIRECT EXPENSES",
            "INDIRECT INCOME", "DIRECT INCOME", "SALES ACCOUNTS", "PURCHASE ACCOUNTS",
            "BANK ACCOUNTS", "CASH-IN-HAND", "CASH ACCOUNT", "LOANS & ADVANCES", "LOANS & ADVANCES (ASSET)",
            "UNSECURED LOANS", "SECURED LOANS", "CAPITAL ACCOUNT", "CAPITAL ACCOUNT / DRAWINGS",
            "DUTIES & TAXES", "PROVISIONS", "CURRENT LIABILITIES", "CURRENT ASSETS", "FIXED ASSETS",
            "INVESTMENTS", "BRANCH / DIVISIONS", "CHEQUE DEPOSIT", "CHQ DEP", "CHQ DEPOSIT",
            "CHEQUE CLEARING", "CLEARING DEPOSIT", "CLEARING", "CLG DEPOSIT", "CHQ RETURN",
            "CHEQUE RETURN", "CHQ RET", "CHEQUE BOUNCE", "INWARD CHEQUE", "OUTWARD CHEQUE"
        }
        if (
            re.match(r"^[A-Z]{1,4}\d{4,12}$", clean_raw, re.IGNORECASE)
            or clean_raw.isdigit()
            or len(clean_raw) < 3
            or clean_raw.upper() in BANNED_PARTY_WORDS
        ):
            return ""

        formatted_words = []
        words = clean_raw.split()
        i = 0
        while i < len(words):
            w = words[i]
            w_up = w.upper()

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
            for seg in sorted(name_parts, key=len, reverse=True):
                if seg in rem:
                    idx = rem.find(seg)
                    matched_segments.append((idx, seg))
                    rem = rem[:idx] + (" " * len(seg)) + rem[idx + len(seg) :]

            if matched_segments:
                matched_segments.sort(key=lambda x: x[0])
                built_parts = []
                curr_idx = 0
                for seg_idx, seg_str in matched_segments:
                    if seg_idx > curr_idx:
                        between = w_up[curr_idx:seg_idx].strip()
                        if between:
                            built_parts.append(
                                between.upper()
                                if len(between) <= 2
                                else between.title()
                            )
                    built_parts.append(seg_str.title())
                    curr_idx = seg_idx + len(seg_str)
                if curr_idx < len(w_up):
                    trailing = w_up[curr_idx:].strip()
                    if trailing:
                        built_parts.append(
                            trailing.upper()
                            if len(trailing) <= 2
                            else trailing.title()
                        )
                formatted_words.append(" ".join(built_parts))
            else:
                formatted_words.append(w.title())
            i += 1

        result = " ".join(formatted_words).strip()
        return re.sub(r"\s+", " ", result)

    mA = re.search(
        r"UPI[/\-]\d*[/\-]?(?:DR|CR)?[/\-]?([A-Za-z0-9_\-\s&\.]+?)(?:[/\-]|$)",
        raw_no_ids,
        re.IGNORECASE,
    )
    if mA:
        res = _sanitize_party(mA.group(1))
        if res and len(res) >= 2:
            return res

    mB = re.search(
        r"(?:NEFT|RTGS|IMPS)[/\-\s]+(?:CR|DR|P2A|P2P)?[/\-\s]*[A-Za-z0-9]*[/\-\s]*([A-Za-z0-9_\-\s&\.]+?)(?:[/\-]|$)",
        raw_no_ids,
        re.IGNORECASE,
    )
    if mB:
        res = _sanitize_party(mB.group(1))
        if res and len(res) >= 2:
            return res

    mC = re.search(
        r"TPT[/\-\s]+(?:[A-Za-z0-9]+\s*)*[/\-\s]+([A-Za-z0-9_\-\s&\.]+?)$",
        raw_no_ids,
        re.IGNORECASE,
    )
    if mC:
        res = _sanitize_party(mC.group(1))
        if res and len(res) >= 2:
            return res

    res = _sanitize_party(raw_no_ids)
    if res and len(res) >= 2:
        return res

    return ""
