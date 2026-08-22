import re

COMMON_NAME_PARTS = [
    'AATHIRA', 'CHANDRAN', 'PALLAVI', 'PANCHAL', 'RUPALI', 'WAGH', 'NIKHILA', 'KIRALE',
    'PAWAN', 'KUMAR', 'SHAH', 'SHASHANK', 'GAWDE', 'GAWD', 'SAMPADA', 'VEDAK', 'SWATI', 'TILAK',
    'RINDA', 'FERNS', 'JAYEETA', 'DOKERAJU', 'SAURABH', 'PANDEY', 'HIRAL', 'CHANDARANA',
    'ANJANAVELIL', 'VARSHA', 'SHRIKANT', 'DANGE', 'NAMRATA', 'GANGTOK', 'PRADEEP', 'SHAW',
    'SUNEETA', 'HARSHA', 'PAREKH', 'DIGAMBAR', 'KHETLE', 'SONAWANE', 'JAYWANT', 'TAUSIF',
    'SIRAJ', 'SHAIKH', 'CHANDRAKANT', 'PARTE', 'BONY', 'YALLAPPA', 'KUNCHI', 'KORVE', 'MASALI',
    'ANAND', 'SHARMA', 'SANJAY', 'DEEPAK', 'RARESH', 'RAJESH', 'PRIYA', 'AMJAD', 'MITUL', 'MANISH',
    'HASMUKH', 'SHANTILAL', 'MEENA', 'PATIDAR', 'KALAMBE', 'PANDURANG', 'NATROX', 'GIBZ'
]

def format_clean_human_name(raw_party: str) -> str:
    if not raw_party:
        return ""
    txt = str(raw_party).strip()

    # 1. Pre-clean trailing bank handles & handle fragments
    txt = re.sub(r'@[A-Za-z0-9_\-\.\s]{1,15}(?:AXIS|ICICI|HDFC|SBI|YES|PAYTM|YBL|KOTAK|UPI|PTYES|YESCRED|NAVIAXIS)', '', txt, flags=re.IGNORECASE)
    txt = re.sub(r'@[A-Za-z0-9_\-\.]+', '', txt)

    # 2. Strip hyphenated / spaced trailing index numbers (e.g. NIKHILAKIRALE-1 -> NIKHILAKIRALE, DOKERAJU-4 -> DOKERAJU)
    txt = re.sub(r'[\s\-]\d+$', '', txt)

    # 3. Strip standalone noise words
    NOISE = {
        'UPI', 'IMPS', 'NEFT', 'RTGS', 'P2A', 'P2P', 'MOB', 'DR', 'CR',
        'NOREF', 'PAYMENT', 'RECEIPT', 'TRANSFER', 'TRF', 'FRM', 'TO',
        'INB', 'BY', 'CHQ', 'PAID', 'YESB', 'SBIN', 'HDFC', 'ICIC', 'UTIB',
        'KKBK', 'BARB', 'CNRB', 'UBIN', 'PUNB', 'TM', 'AB', 'TPT', 'NETBANK',
        'NETB', 'HDFCH', 'HDFCN', 'HDFCE', 'HDFCBANK', 'ICICI', 'AXIS', 'MAHB',
        'SVCB', 'TMBL', 'INDB', 'CCBL', 'KAXIS', 'IS', 'CI', 'FCBANK', 'KHDFCBANK', 'OKICIC', 'OKS', 'OKI', 'OKA', 'XIS'
    }

    words = [w for w in re.split(r'[\s\-\/@._]+', txt) if w.upper() not in NOISE]
    txt = " ".join(words).strip()

    # 4. Strip numbers at end of words (e.g. RUPALIWAGH39 -> RUPALIWAGH, AATHIRACHANDRAN2014 -> AATHIRACHANDRAN)
    txt = re.sub(r'(?<=[A-Za-z]{3})\d{1,4}\b', '', txt)
    txt = re.sub(r'\b\d{1,4}(?=[A-Za-z]{3})', '', txt)
    txt = " ".join(txt.split()).strip()

    # If pure code/alphanumeric ref (e.g. DU82848, PSURVE810), keep intact
    if re.match(r'^[A-Z]{2}\d{4,6}$', txt, re.IGNORECASE):
        return txt.upper()

    # 5. Smart Word Boundary Insertion for merged names
    words = txt.split()
    formatted_words = []

    for w in words:
        w_up = w.upper()
        matched_segments = []
        rem = w_up
        for seg in sorted(COMMON_NAME_PARTS, key=len, reverse=True):
            if seg in rem:
                idx = rem.find(seg)
                matched_segments.append((idx, seg))
                rem = rem[:idx] + (" " * len(seg)) + rem[idx + len(seg):]

        if len(matched_segments) >= 2:
            matched_segments.sort(key=lambda x: x[0])
            split_name = " ".join(s[1].title() for s in matched_segments)
            formatted_words.append(split_name)
        elif len(matched_segments) == 1:
            # Check if there is a single letter initial inside
            matched_segments.sort(key=lambda x: x[0])
            seg = matched_segments[0][1]
            idx = w_up.find(seg)
            prefix = w_up[:idx].strip()
            suffix = w_up[idx + len(seg):].strip()

            parts = []
            if prefix: parts.append(prefix.title())
            parts.append(seg.title())
            if suffix: parts.append(suffix.title())
            formatted_words.append(" ".join(parts))
        else:
            formatted_words.append(w.title())

    result = " ".join(formatted_words).strip()
    result = re.sub(r'\s+', ' ', result)
    return result

test_user_parties = [
    "RUPALIWAGH39",
    "THISISJAYEETA",
    "PAWANKUMARSHAH04 OKICIC",
    "AATHIRACHANDRAN2014",
    "SHASHANKGAWD",
    "RSMASALI2014",
    "SAMPADAVEDAK",
    "SWATIBTILAK",
    "PALLAVIPANCHAL793@OKA XIS",
    "NIKHILAKIRALE-1",
    "RINDAFERNS-1",
    "DOKERAJU-4",
    "DU82848"
]

print("=== REFINED AI SMART NAME FORMATTER TEST RESULTS ===")
for p in test_user_parties:
    clean = format_clean_human_name(p)
    print(f"RAW:   '{p}'")
    print(f"CLEAN: '{clean}'\n")
