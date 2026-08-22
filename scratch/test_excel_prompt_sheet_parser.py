import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from core.excel_parser import parse_excel_to_json

file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Test_Samples_And_Archives/DEMO SALES/PE PULSE/F.Y. 2026-27/April 2026/Sale_Report_01-04-2026_to_30-04-2026.xls'))

print(f"Testing parse_excel_to_json on file: {file_path}")
res = parse_excel_to_json(
    file_path=file_path,
    instruction="read only Miracle Sale Import"
)

data = res.get("extracted_data", [])
print(f"Total Vouchers Extracted: {len(data)}")
for i, v in enumerate(data[:10]):
    print(f" #{i+1} Date: {v.get('date')} | Bill No: '{v.get('bill_no')}' | Party: {v.get('party_name')} | Taxable: {v.get('taxable_amount')} | Total: {v.get('total')}")
