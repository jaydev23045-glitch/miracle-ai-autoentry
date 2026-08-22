import re

def classify_transaction_nature(narr: str, party_name: str, tx_type: str = "Receipt") -> str:
    """
    Deep Transaction Nature Classifier for Indian Accounting.
    Analyzes narration & party name to determine the exact accounting group nature:
    - Indirect Expenses
    - Indirect Income
    - Duties & Taxes
    - Bank Charges
    - Cash-in-Hand
    - Loans & Advances (Asset) / Sundry Creditors (Payments to Persons)
    - Unsecured Loans / Sundry Debtors (Receipts from Persons)
    """
    text = f"{narr} {party_name}".upper()

    # 1. Statutory / Tax Keywords
    if any(k in text for k in ['PROFESSIONAL TAX', ' PTAX ', ' GST ', 'CGST', 'SGST', 'IGST', ' TDS ', ' TCS ', 'ADVANCE TAX', 'INCOME TAX', 'DUTIES & TAXES', 'CHALLAN']):
        return "Duties & Taxes"

    # 2. Bank Charges & Penalties
    if any(k in text for k in ['BANK CHARGES', 'MDR RCVRY', 'RUPAY MDR', 'INSTAALERT', 'SMS CHG', 'MIN BAL', 'ATM CHG', 'DEBIT CARD CHG', 'CHQ BOUNCE']):
        return "Indirect Expenses"

    # 3. Expense & Utility Keywords
    EXPENSE_KWS = [
        'EXPENSE', 'EXPENSES', ' RENT', 'SALARY', 'SALARIES', 'MAINTENANCE', 'ELECTRICITY',
        'TELEPHONE', 'MOBILE', 'RECHARGE', 'WIFI', 'BROADBAND', 'FUEL', 'PETROL', 'DIESEL',
        'SWIGGY', 'ZOMATO', 'MILK', 'TEA', 'COFFEE', 'FOOD', 'HOTEL', 'RESTAURANT', 'FARSAN',
        'AUDIT', 'LEGAL', 'FEE', 'FEES', 'COMMISSION', 'PRINTING', 'STATIONERY', 'COURIER',
        'POSTAGE', 'CLEANING', 'REPAIR', 'REPAIRS', 'SOFTWARE', 'DOMAIN', 'HOSTING', 'CLOUD',
        'TAXI', 'AUTO', 'CAB', 'TRAVEL', 'CONVEYANCE', 'SUBSCRIPTION', 'DONATION', 'WELFARE'
    ]
    if any(k in text for k in EXPENSE_KWS):
        return "Indirect Expenses"

    # 4. Income Keywords
    INCOME_KWS = [
        'INTEREST RECEIVED', 'DIVIDEND', 'REFUND', 'CASHBACK', 'SCHOLARSHIP',
        'COMMISSION RECEIVED', 'RENT RECEIVED', 'SUBSIDY', 'DISCOUNT RECEIVED'
    ]
    if any(k in text for k in INCOME_KWS):
        return "Indirect Income"

    # 5. Cash / Contra
    if any(k in text for k in ['CASH WITHDRAWAL', 'ATM CASH', 'CASH DEPOSIT', 'CASH ACCOUNT']):
        return "Cash-in-Hand"

    # 6. Person / Entity Default (Based on Receipt vs Payment)
    if tx_type.capitalize() == "Receipt":
        return "Sundry Debtors"
    else:
        return "Sundry Creditors"

test_samples = [
    ("UPI-120401000054-PROFESSIONAL TAX", "PROFESSIONAL TAX", "Payment"),
    ("UPI-643801517558-RUPAY MDR RCVRY", "Bank Charges", "Payment"),
    ("UPI-50100519464174-AIRTEL MOBILE BILL", "Airtel Mobile", "Payment"),
    ("UPI-8813069948-PETROL PUMP", "Petrol Pump", "Payment"),
    ("UPI-05011610013798-INTEREST RECEIVED", "Interest Received", "Receipt"),
    ("UPI-233100050316029-PALLAVI PANCHAL", "Pallavi Panchal", "Receipt"),
    ("UPI-917010034491816-BONY KUNCHIKORVE", "Bony Kunchikorve", "Payment")
]

print("=== DEEP TRANSACTION NATURE CLASSIFIER TEST RESULTS ===")
for narr, party, tx in test_samples:
    group = classify_transaction_nature(narr, party, tx)
    print(f"Narr:  '{narr[:40]}...' | Party: '{party}' ({tx})")
    print(f"Nature: {group}\n")
