import re

def test_keyword_match_bug():
    narr1 = "UPI-233100050316029-BONYKUNCHIKORVE@OKICICI-620126295421-SENT USING PHONEPE"
    narr2 = "UPI-917010034491816-9359456142@OKAXIS-620126295421-SENT USING PHONEPE"
    narr3 = "AIRTEL MOBILE BILL PAYMENT 9890688147"

    keywords = ["MOBILE", "PHONE", "TELEPHONE", "JIOTEL", "AIRTEL", "VODAFONE", "BSNL"]

    print("--- OLD BUGGY MATCH (Substring) ---")
    for narr in [narr1, narr2, narr3]:
        matched = any(kw in narr.upper() for kw in keywords)
        print(f"'{narr[:45]}...' -> Matched TELEPHONE EXP? {matched}")

    print("\n--- FIXED MATCH (Word Boundaries \\b and Excluding PHONEPE) ---")
    for narr in [narr1, narr2, narr3]:
        # Strip payment gateway names before checking utility keywords
        narr_no_gateway = re.sub(r'\b(PHONEPE|PAYTM|GPAY|BHIM|AMAZONPAY|PAYU)\b', '', narr.upper())
        matched = any(re.search(rf'\b{re.escape(kw)}\b', narr_no_gateway) for kw in keywords)
        print(f"'{narr[:45]}...' -> Matched TELEPHONE EXP? {matched}")

test_keyword_match_bug()
