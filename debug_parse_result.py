import os
import sys
import pandas as pd

sys.path.insert(0, os.path.abspath("backend"))

from core.excel_parser import parse_excel_to_json

file_path = "Test_Samples_And_Archives/DEMO SALES/PE PULSE/F.Y. 2025-26/MARCH-2026/Sale_Report_01-03-2026_to_31-03-2026.xls"

res = parse_excel_to_json(file_path)
extracted = res.get("extracted_data", [])

print(f"Extracted {len(extracted)} vouchers.")
for idx, vch in enumerate(extracted[:10]):
    print(f"[{idx+1}] Date: {vch.get('date')} | Bill No: '{vch.get('bill_no')}' | Party: {vch.get('party_name')} | Taxable: {vch.get('taxable_amount')} | Total: {vch.get('total')}")
