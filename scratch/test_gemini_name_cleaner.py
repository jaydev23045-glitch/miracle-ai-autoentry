import re

def clean_party_name_v3(narr: str, tx_type: str = "Receipt") -> tuple:
    if not narr:
        return ("", "Sundry Debtors" if tx_type == "Receipt" else "Sundry Creditors")

    raw = str(narr).strip()

    # 1. Pre-clean @handle domain suffixes including handles with spaces (e.g. @OKA XIS, @OK ICICI)
    raw_no_handle = re.sub(r'@[A-Za-z0-9_\-\.\s]{1,15}(?:AXIS|ICICI|HDFC|SBI|YES|PAYTM|YBL|KOTAK|UPI|PTYES|YESCRED|NAVIAXIS)', '', raw, flags=re.IGNORECASE)
    raw_no_handle = re.sub(r'@[A-Za-z0-9_\-\.]+', '', raw_no_handle)

    # 2. Strip standard IFSC codes (4 alpha + 0 + 6 alphanumeric)
    raw_no_ifsc = re.sub(r'\b[A-Za-z]{4}0[A-Za-z0-9]{6}\b', '', raw_no_handle, flags=re.IGNORECASE)
    raw_no_ifsc = re.sub(r'\b[A-Za-z]{4}[0-9][A-Za-z0-9]{4,6}\b', '', raw_no_ifsc, flags=re.IGNORECASE)

    # 3. Strip long standalone numeric ref numbers/UTRs (11+ digits)
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
        'KAXIS', 'IS', 'CI', 'FCBANK', 'KHDFCBANK', 'OKICIC', 'OKS', 'OKI', 'OKA', 'XIS',
        'PEPULSE', 'PE', 'PULSE', 'PVT', 'LTD', 'PRIVATE', 'LIMITED'
    }

    MONTH_NAMES = {'JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC',
                   'JANUARY', 'FEBRUARY', 'MARCH', 'APRIL', 'JUNE', 'JULY', 'AUGUST', 'SEPTEMBER', 'OCTOBER', 'NOVEMBER', 'DECEMBER'}

    def _sanitize_party(candidate: str) -> str:
        if not candidate:
            return ""
        tokens = []
        for w in re.split(r'[\s\-\/@._]+', candidate):
            w_clean = w
            if not re.match(r'^[A-Z]{2}\d{4,6}$', w, re.IGNORECASE):
                # Strip up to 4 trailing digits from party names (e.g. AATHIRACHANDRAN2014 -> AATHIRACHANDRAN)
                w_clean = re.sub(r'(?<=[A-Za-z]{3})\d{1,4}$', '', w)
            w_upper = w_clean.upper()

            if not w_clean or w_upper in NOISE_TOKENS or w_upper in MONTH_NAMES:
                continue
            if w_clean.isdigit() and len(w_clean) != 10:
                continue
            tokens.append(w_clean)

        clean = " ".join(tokens).strip()
        if clean:
            return clean
        return ""

    mA = re.search(r'UPI[/\-]\d*[/\-]?(?:DR|CR)?[/\-]?([A-Za-z0-9_\-\s&\.]+?)(?:[/\-]|$)', raw_no_ids, re.IGNORECASE)
    if mA:
        res = _sanitize_party(mA.group(1))
        if res and len(res) >= 2:
            return res

    res = _sanitize_party(raw_no_ids)
    return res

test_rows = [
    "UPI-643801517558-AATHIRACHANDRAN2014-5@OKICICI-65",
    "UPI-05011610013798-9890688147@PTHDFC-618",
    "UPI-50100519464174-PALLAVIPANCHAL793@OKA XIS-618290225908-UPI",
    "UPI-8813069948-NIKHILAKIRALE-1@OKICICI-618"
]

print("=== TEST NARRATION PARTY CLEANER V3 ===")
for r in test_rows:
    cleaned = clean_party_name_v3(r)
    print(f"RAW:   '{r}'")
    print(f"CLEAN: '{cleaned}'\n")
