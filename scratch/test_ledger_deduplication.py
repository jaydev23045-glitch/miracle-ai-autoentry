import os
import sys

def test_bank_ledger_filtering_and_deduplication():
    print("--- TEST: BANK LEDGER FILTERING & DEDUPLICATION ---")
    mock_ledgers = [
        {"code": "ALCV5SEE", "name": "ICICI BANK SB-8645", "print_name": "ICICI BANK SB-8645", "classification": "Bank", "group_code": "G0000004", "group_name": "BANK ACCOUNTS"},
        {"code": "ALCXYULX", "name": "BANK CHARGES", "print_name": "BANK CHARGES", "classification": "Expense", "group_code": "G0000024", "group_name": "INDIRECT EXPENSES"},
        {"code": "ALBRML5Y", "name": "ICICI BANK CA-0157", "print_name": "ICICI BANK CA-0157", "classification": "Bank", "group_code": "G0000004", "group_name": "BANK ACCOUNTS"},
        {"code": "ALFRLBCW", "name": "BANK INTREST", "print_name": "BANK INTREST", "classification": "Income", "group_code": "G0000022", "group_name": "INDIRECT INCOME"},
        {"code": "AGONVHNW", "name": "Kotak MAHINDRA BANK HOME LOAN", "print_name": "Kotak MAHINDRA BANK HOME LOAN", "classification": "Loan", "group_code": "G0000017", "group_name": "SECURED LOANS"},
        {"code": "ALCV5SEE", "name": "ICICI BANK SB-8645", "print_name": "ICICI BANK SB-8645", "classification": "Bank", "group_code": "G0000004", "group_name": "BANK ACCOUNTS"}, # Duplicate code & name
    ]

    NON_BANK_TERMS = ['PROFIT', 'P&L', 'LOSS', 'TRADING', 'CAPITAL', 'DRAWINGS', 'TAX', 'DUTY', 'GST', 'IGST', 'CGST', 'SGST', 'CHARGES', 'CHARGE', 'INTREST', 'INTEREST', 'COMMISSION', 'LOAN', 'OD', 'OVERDRAFT', 'FD', 'FIXED DEPOSIT']
    
    filtered_banks = []
    for led in mock_ledgers:
        cat = (led.get('classification') or '').upper()
        grp = (led.get('group_code') or '').upper()
        grpName = (led.get('group_name') or '').upper()
        name = (led.get('name') or '').upper()
        printName = (led.get('print_name') or '').upper()

        is_bad = any(term in name or term in printName for term in NON_BANK_TERMS) or led.get('code') == 'PROFLOSS'
        if is_bad:
            continue

        if cat == 'BANK' or grp == 'G0000004' or grpName == 'BANK ACCOUNTS' or ('BANK' in grpName and 'CHARGES' not in grpName and 'INTEREST' not in grpName):
            filtered_banks.append(led)

    # Deduplicate by Code + Name
    seen_keys = set()
    unique_banks = []
    for led in filtered_banks:
        unique_key = f"{led['code']}_{(led.get('print_name') or led.get('name')).upper().strip()}"
        if unique_key not in seen_keys:
            seen_keys.add(unique_key)
            unique_banks.append(led)

    print("Filtered & Deduplicated Bank Ledgers:")
    for b in unique_banks:
        print(f"  -> 🏦 {b['name']} ({b['code']})")

    bank_names = [b['name'] for b in unique_banks]
    assert "BANK CHARGES" not in bank_names, "BANK CHARGES should be excluded"
    assert "BANK INTREST" not in bank_names, "BANK INTREST should be excluded"
    assert "Kotak MAHINDRA BANK HOME LOAN" not in bank_names, "HOME LOAN should be excluded"
    assert len(unique_banks) == 2, f"Expected 2 unique bank ledgers, got {len(unique_banks)}"
    print("✅ All Bank Dropdown Filtering & Deduplication Tests Passed!\n")

if __name__ == "__main__":
    test_bank_ledger_filtering_and_deduplication()
