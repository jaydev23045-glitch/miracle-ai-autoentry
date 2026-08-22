import re

def extract_clean_party_from_narration(narr: str) -> str:
    if not narr:
        return ""
    narr_str = str(narr).strip()

    # 1. Bank handles, gateways, transaction prefixes, and noise tokens
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
        'SELF', 'NEHRU', 'NAGAR', 'KURLA', 'EAST', 'WEST', 'BRANCH'
    }

    MONTH_NAMES = {'JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC',
                   'JANUARY', 'FEBRUARY', 'MARCH', 'APRIL', 'JUNE', 'JULY', 'AUGUST', 'SEPTEMBER', 'OCTOBER', 'NOVEMBER', 'DECEMBER'}

    def _sanitize_party(candidate: str) -> str:
        if not candidate:
            return ""
        # 1. Strip @handle domain suffixes (@OKAXIS, @OKICICI, @PTYES, etc.)
        cand = re.sub(r'@[A-Za-z0-9_\-\.]+', '', candidate)
        
        # 2. Strip standalone bank IFSC codes (e.g. BARB0DBWADA, INDB0000282, ICIC0000035)
        cand = re.sub(r'\b[A-Z]{4}[0-9][A-Z0-9]{4,6}\b', '', cand, flags=re.IGNORECASE)
        
        # 3. Strip standalone long numeric ref numbers/UTRs (11+ digits), keeping 10-digit mobile handles
        cand = re.sub(r'\b\d{11,}\b', '', cand)
        
        tokens = []
        for w in re.split(r'[\s\-\/@._]+', cand):
            w_upper = w.upper()
            if w_upper in NOISE_TOKENS or w_upper in MONTH_NAMES:
                continue
            if w.isdigit() and len(w) != 10: # keep 10-digit mobile UPI handles, drop others
                continue
            tokens.append(w)
        
        clean = " ".join(tokens).strip()
        if clean:
            return clean
        return ""

    # Try explicit pattern matches first
    m1 = re.search(r'UPI[/\-]\d+[/\-](?:DR|CR)[/\-]([A-Za-z0-9_\-\s&\.@]+?)(?:[/\-]|$)', narr_str, re.IGNORECASE)
    if m1:
        res = _sanitize_party(m1.group(1))
        if res and len(res) >= 2:
            return res

    m2 = re.search(r'UPI[/\-]\d+[/\-]([A-Za-z0-9_\-\s&\.@]+?)(?:[/\-]|$)', narr_str, re.IGNORECASE)
    if m2:
        res = _sanitize_party(m2.group(1))
        if res and len(res) >= 2:
            return res

    m3 = re.search(r'UPI[/\-]([A-Za-z0-9_\-\s&\.@]+?)(?:[/\-@]|$)', narr_str, re.IGNORECASE)
    if m3:
        res = _sanitize_party(m3.group(1))
        if res and len(res) >= 2:
            return res

    m4 = re.search(r'IMPS[/\-](?:P2A|P2P|MOB)?[/\-]?\d+[/\-][A-Za-z0-9]+[/\-]([A-Za-z0-9_\-\s&\.@]+)', narr_str, re.IGNORECASE)
    if m4:
        res = _sanitize_party(m4.group(1))
        if res and len(res) >= 2:
            return res

    m5 = re.search(r'(?:NEFT|RTGS)[/\-][A-Za-z0-9]+[/\-]([A-Za-z0-9_\-\s&\.@]+)', narr_str, re.IGNORECASE)
    if m5:
        res = _sanitize_party(m5.group(1))
        if res and len(res) >= 2:
            return res

    # General fallback
    res = _sanitize_party(narr_str)
    if res and len(res) >= 2:
        return res

    return ""

test_narrations = [
    "UPI-344802010901108-AFIFAMETKAR@OKAXIS-6570862224",
    "UPI-54982210013475-DU82848@PTYES-211684284158-SENT USING PAYTM",
    "UPI-015101015097-SAURABHPANDEY.700@PTYES-31078461",
    "UPI-0549366315-7304637944@NAVIAXIS-620438848847-PAYMENT",
    "UPI-4911366989-9619106098@YESCRED-657009000231-PAYMENT",
    "50200116476990-TPT-JUNE 1-S S R FOOTCARE",
    "NEFT DR-BARB0DBWADA-ANAND KUMAR ANIL SHARMA-NETBANK",
    "50200110127794-TPT-HAND LOAN-GIBZ SOLUTIONS PRIVATE LIMITED",
    "UPI-643801517558-AATHIRACHANDRAN2014-5@OKICICI-65",
    "UPI-RESHAM AJAY KUKREJA-DR.R.A.KUKREJA@OKHDFCBANK"
]

print("=== FINAL TEST NARRATION CLEANER RESULTS ===")
for narr in test_narrations:
    clean_party = extract_clean_party_from_narration(narr)
    print(f"RAW:   '{narr}'")
    print(f"CLEAN: '{clean_party}'\n")
