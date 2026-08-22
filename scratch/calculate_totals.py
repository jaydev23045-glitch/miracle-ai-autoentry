import pdfplumber
import re

pdf_path = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/Test_Samples_And_Archives/DEMO SALES/Aksharbrahm/259876778999_1785754792241.pdf"

rows = []

with pdfplumber.open(pdf_path) as pdf:
    for page_num, page in enumerate(pdf.pages):
        text = page.extract_text() or ""
        lines = text.split('\n')
        for line in lines:
            numbers = re.findall(r'\b\d+\.\d{2}\b', line)
            if len(numbers) >= 2:
                bal = float(numbers[-1])
                amt = float(numbers[-2])
                rows.append({"line": line, "amount": amt, "balance": bal, "page": page_num + 1})

# Rows are extracted in PDF order (newest first). Let's process chronologically (reverse rows):
chronological_rows = list(reversed(rows))

opening_bal = 639713.29  # 624993.29 + 14720.00
cur_bal = opening_bal

total_withdrawals = 0.0
total_deposits = 0.0

for idx, r in enumerate(chronological_rows):
    bal = r["balance"]
    amt = r["amount"]
    
    # Determine if deposit or withdrawal based on balance delta
    delta = round(bal - cur_bal, 2)
    if abs(delta - amt) < 1.0:
        # Deposit
        tx_type = "Deposit"
        total_deposits += amt
    elif abs(delta + amt) < 1.0:
        # Withdrawal
        tx_type = "Withdrawal"
        total_withdrawals += amt
    else:
        # Fallback check
        tx_type = "Unknown"
        print(f"⚠️ Mismatch at row {idx+1} (Page {r['page']}): cur_bal={cur_bal}, new_bal={bal}, amt={amt}, delta={delta}")
        
    cur_bal = bal

print("📊 --- GROUND TRUTH METRICS FROM PDF ---")
print(f"Total Rows: {len(rows)}")
print(f"Opening Balance: ₹{opening_bal:,.2f}")
print(f"Total Deposits (Receipts): ₹{total_deposits:,.2f}")
print(f"Total Withdrawals (Payments): ₹{total_withdrawals:,.2f}")
print(f"Net Cash Flow: ₹{total_deposits - total_withdrawals:,.2f}")
print(f"Closing Balance: ₹{cur_bal:,.2f}")
