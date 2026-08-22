import re

# Active client company name tokens to strip from narrations
CLIENT_COMPANY_TOKENS = {'PEPULSE', 'PE', 'PULSE', 'PVT', 'LTD', 'PRIVATE', 'LIMITED', 'MIRACLE'}

def clean_party_name_ultimate(narr: str, tx_type: str = "Receipt") -> tuple:
    """
    Ultimate Indian Bank Narration Party Extractor & Auto-Classifier.
    Returns (clean_party_name, target_group_hint).
    """
    if not narr:
        return ("", "Sundry Debtors" if tx_type == "Receipt" else "Sundry Creditors")

    raw = str(narr).strip()

    # 1. Pre-clean @handle domain suffixes BEFORE any regex splitting!
    # Strip @OKAXIS, @OKICICI, @OKHDFCBANK, @OKSBI, @PTYES, @YESCRED, @NAVIAXIS etc.
    raw_no_handle = re.sub(r'@[A-Za-z0-9_\-\.]+', '', raw)

    # 2. Strip standard IFSC codes (4 alpha + 0 + 6 alphanumeric)
    raw_no_ifsc = re.sub(r'\b[A-Za-z]{4}0[A-Za-z0-9]{6}\b', '', raw_no_handle, flags=re.IGNORECASE)
    raw_no_ifsc = re.sub(r'\b[A-Za-z]{4}[0-9][A-Za-z0-9]{4,6}\b', '', raw_no_ifsc, flags=re.IGNORECASE)

    # 3. Strip long standalone numeric ref numbers/UTRs (11+ digits), keeping party IDs like DU82848 or 10-digit mobile handles
    raw_no_ids = re.sub(r'\b\d{11,}\b', '', raw_no_ifsc)

    # 4. Pattern extraction
    candidate = raw_no_ids

    # UPI Pattern: UPI-ref-NAME or UPI/ref/NAME
    mA = re.search(r'UPI[/\-]\d*[/\-]?(?:DR|CR)?[/\-]?([A-Za-z0-9_\-\s&\.]+?)(?:[/\-]|$)', raw_no_ids, re.IGNORECASE)
    if mA and len(mA.group(1).strip()) >= 2:
        candidate = mA.group(1).strip()

    # NEFT Pattern: NEFT CR-IFSC-NAME-NETB or NEFT DR-IFSC-NAME-NETB
    mB = re.search(r'(?:NEFT|RTGS|IMPS)[/\-\s]+(?:CR|DR|P2A|P2P)?[/\-\s]*[A-Za-z0-9]*[/\-\s]*([A-Za-z0-9_\-\s&\.]+?)(?:[/\-]|$)', raw_no_ids, re.IGNORECASE)
    if mB and len(mB.group(1).strip()) >= 2:
        candidate = mB.group(1).strip()

    # TPT Pattern: TPT-REMARK-NAME
    mC = re.search(r'TPT[/\-\s]+(?:[A-Za-z0-9]+\s*)*[/\-\s]+([A-Za-z0-9_\-\s&\.]+?)$', raw_no_ids, re.IGNORECASE)
    if mC and len(mC.group(1).strip()) >= 2:
        candidate = mC.group(1).strip()

    # 5. Token-level Sanitization & Noise Elimination
    BANK_NOISE = {
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
        'KAXIS', 'IS', 'CI', 'FCBANK', 'KHDFCBANK', 'OKICIC', 'OKS', 'OKI', 'OKA',
        'PEPULSE', 'PE', 'PULSE', 'PVT', 'LTD', 'PRIVATE', 'LIMITED'
    }

    MONTH_NAMES = {'JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC',
                   'JANUARY', 'FEBRUARY', 'MARCH', 'APRIL', 'JUNE', 'JULY', 'AUGUST', 'SEPTEMBER', 'OCTOBER', 'NOVEMBER', 'DECEMBER'}

    tokens = []
    for w in re.split(r'[\s\-\/@._]+', candidate):
        # Strip trailing digits if attached to common bank handles (e.g. DANGE56 -> DANGE, PAWANKUMARSHAH04 -> PAWANKUMARSHAH)
        # But KEEP party codes like DU82848, PSURVE810, SUNEETA89, AATHIRACHANDRAN2014
        w_clean = w
        if not re.match(r'^[A-Z]{2}\d{4,6}$', w, re.IGNORECASE): # don't strip DU82848
            w_clean = re.sub(r'(?<=[A-Za-z]{3})\d{1,3}$', '', w) # strip 1-3 trailing digits from name: DANGE56 -> DANGE
        w_upper = w_clean.upper()

        if not w_clean or w_upper in BANK_NOISE or w_upper in MONTH_NAMES:
            continue
        if w_clean.isdigit() and len(w_clean) != 10: # keep 10-digit mobile handles
            continue
        tokens.append(w_clean)

    clean_name = " ".join(tokens).strip()

    # Fallback to full string tokens if clean_name is empty
    if not clean_name:
        for w in re.split(r'[\s\-\/@._]+', raw_no_ids):
            w_clean = w
            if not re.match(r'^[A-Z]{2}\d{4,6}$', w, re.IGNORECASE):
                w_clean = re.sub(r'(?<=[A-Za-z]{3})\d{1,3}$', '', w)
            w_upper = w_clean.upper()
            if not w_clean or w_upper in BANK_NOISE or w_upper in MONTH_NAMES or (w_clean.isdigit() and len(w_clean) != 10):
                continue
            tokens.append(w_clean)
        clean_name = " ".join(tokens).strip()

    # 6. Priority Name-Based Group Overrides (Rule 20)
    upper_name = clean_name.upper()
    target_group = "Sundry Debtors" if tx_type == "Receipt" else "Sundry Creditors"

    if any(k in upper_name for k in ['TAX', 'PROFESSIONAL TAX', 'GST', 'TDS', 'DUTY']):
        target_group = "Duties & Taxes" if "TAX" in upper_name else "Indirect Expenses"
    elif any(k in upper_name for k in ['EXPENSE', 'RENT', 'SALARY', 'MAINTENANCE', 'ELECTRICITY', 'TELEPHONE', 'CHARGES', 'FEE', 'COMMISSION', 'INTERNET', 'RECHARGE', 'PETROL']):
        target_group = "Indirect Expenses"
    elif any(k in upper_name for k in ['BANK CHARGES', 'MDR RCVRY', 'INSTAALERT']):
        target_group = "Indirect Expenses"
    elif "CASH" in upper_name:
        target_group = "Cash-in-Hand"

    return (clean_name, target_group)


# Test cases from user's screenshot:
test_cases = [
    ("UPI-120401000054-NAMRATAGANGTOK@OKICICI-619286922", "Receipt"),
    ("UPI-50100094872006-PRADEEPKUMARSHAW@OKHDFCBANK-1261154", "Receipt"),
    ("UPI-00000030265377392-SHRIKANT.DANGE56@OKAXIS-6192433", "Receipt"),
    ("UPI-922010054183409-ANJANAVELILVARSHA-1@OKAXIS-6560111", "Receipt"),
    ("NEFT CR-IBKL0NEFT01-SCUBE-PE PULSE PVT LTD-0706I29952371541", "Receipt"),
    ("NEFT CR-ICIC0SF0002-YASHWANT HEALTHCARE-PEPULSE-IN42619252117467", "Receipt"),
    ("UPI-020901515756-PAWANKUMARSHAH04@OKICICI-6188283", "Receipt"),
    ("UPI-50200030536796-VKSHARMAMUMBAI.7988@OKHDFCBANK", "Receipt"),
    ("UPI-00000020010849974-MAILS4SADHNAM@OKAXIS-655705", "Receipt"),
    ("UPI-006401530070-DEEPSHIKHA.DHOMSE@OKICICI-655876", "Receipt"),
    ("UPI-9111589039-9619963111@PTAXIS-620126295421-SEN PROFESSIONAL TAX", "Payment"),
    ("82082204 RUPAY MDR RCVRY-12/07/26", "Payment"),
    ("MAYMAY26 INSTAALERTCHG 3 SMS-CDT26205416 43940", "Payment"),
    ("50200116476990-TPT-JUNE 1-S S R FOOTCARE", "Receipt"),
    ("UPI-344802010901108-AFIFAMETKAR@OKAXIS-6570862224", "Receipt"),
    ("UPI-54982210013475-DU82848@PTYES-211684284158-SENT USING PAYTM", "Receipt")
]

print("=== REFINED SCREENSHOT TEST CASES RESULTS ===")
for narr, txtype in test_cases:
    party, group = clean_party_name_ultimate(narr, txtype)
    print(f"RAW:   '{narr}'")
    print(f"CLEAN: '{party}' → [{group}]\n")
