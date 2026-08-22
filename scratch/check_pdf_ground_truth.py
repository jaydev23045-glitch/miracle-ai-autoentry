import pdfplumber
import re

pdf_path = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/Test_Samples_And_Archives/DEMO SALES/Aksharbrahm/259876778999_1785754792241.pdf"

total_withdrawals = 0.0
total_deposits = 0.0
transaction_rows = []

with pdfplumber.open(pdf_path) as pdf:
    for page_num, page in enumerate(pdf.pages):
        text = page.extract_text() or ""
        lines = text.split('\n')
        for line in lines:
            # Look for lines that look like transaction rows with amounts and running balances
            # Usually: date ... withdrawal/deposit balance
            # Find all floating numbers in the line
            # E.g. "2026-07-31 ... 1400.00 687336.70"
            numbers = re.findall(r'\b\d+\.\d{2}\b', line)
            if len(numbers) >= 2:
                # E.g. [1400.00, 687336.70] or [10000.00, 697836.70]
                # Check if the last number is running balance
                bal = float(numbers[-1])
                amt = float(numbers[-2])
                transaction_rows.append({
                    "page": page_num + 1,
                    "line": line,
                    "amount": amt,
                    "balance": bal,
                    "all_numbers": numbers
                })

print(f"📄 Found {len(transaction_rows)} potential transaction rows in PDF text.")
print("\nFirst 5 rows from PDF:")
for r in transaction_rows[:5]:
    print(r)
    
print("\nLast 5 rows from PDF:")
for r in transaction_rows[-5:]:
    print(r)
