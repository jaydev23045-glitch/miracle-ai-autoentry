import re

def parse_user_guidelines_v2(instruction: str) -> list:
    rules = []
    if not instruction or not instruction.strip():
        return rules

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

        # Ultra-flexible regex for user guidelines mapping instructions
        m_rule = re.search(
            r'(?:map|if|when|narration|amount)?\s*([a-zA-Z0-9_\-\s&/]+?)\s*'
            r'(?:->|:|=|map to|mapped to|mapping to|map with|mapped with|mapping with|put in|put into|send to|set as|assign to|to|with)\s*'
            r'([a-zA-Z0-9_\-\s&/]+)',
            item_s, re.IGNORECASE
        )
        if m_rule:
            src_kw = m_rule.group(1).strip()
            tgt_name = m_rule.group(2).strip()

            # Clean noise tokens from source keyword
            src_kw_clean = re.sub(r'\b(if|when|narration|contains|is|has|all|any|deposit|withdrawal|payment|receipt|come|first|then|amount|site)\b', '', src_kw, flags=re.IGNORECASE)
            src_kw_clean = " ".join(src_kw_clean.split()).upper()

            # Clean noise tokens from target name
            tgt_clean = re.sub(r'\b(account|ac|a/c)\b', '', tgt_name, flags=re.IGNORECASE).strip()
            tgt_clean = " ".join(tgt_clean.split())

            if src_kw_clean and tgt_clean:
                rules.append((src_kw_clean, tgt_clean, tx_type_req))

    return rules

test_instructions = [
    "AMOUNT IF NARRATION COME UPI FIRST THEN MAPPING WITH UPI DEBTORS ACCOUNT",
    "If narration contains SWIGGY map to Staff Welfare Expenses",
    "deposit side upi map with UPI Debtors",
    "payment of petrol -> Petrol Expenses",
    "when UPI then set as UPI Creditors for withdrawal"
]

print("=== USER GUIDELINES PARSER V2 TEST RESULTS ===")
for inst in test_instructions:
    parsed = parse_user_guidelines_v2(inst)
    print(f"PROMPT: '{inst}'")
    print(f"PARSED: {parsed}\n")
