import os
import sys
import pandas as pd

sys.path.insert(0, os.path.abspath("backend"))

from core.excel_parser import parse_excel_to_json
from modules.sales.parser import SalesParser

print("Testing Direct Sales Parser & InvoiceSchema...")

# Create mock sales Excel
df = pd.DataFrame([
    {"bill_no": "304", "date": "2026-03-06", "party_name": "Mr Gopal Iyer", "item_name": "Cmf Gopal Iyer sandal", "qty": 1, "rate": 5714.29, "taxable_amt": 5714.29, "gst_pct": 5.0, "gst_amt": 285.71, "total_amt": 6000.0, "payment_type": "Pe Pulse Private Limited"},
    {"bill_no": "304", "date": "2026-03-06", "party_name": "Mr Gopal Iyer", "item_name": "Cmf mould for Gopalkrishnan Iyer", "qty": 1, "rate": 5932.20, "taxable_amt": 5932.20, "gst_pct": 18.0, "gst_amt": 1067.80, "total_amt": 7000.0, "payment_type": "Pe Pulse Private Limited"},
    {"bill_no": "304", "date": "2026-03-06", "party_name": "Mr Gopal Iyer", "item_name": "Foam box", "qty": 1, "rate": 423.73, "taxable_amt": 423.73, "gst_pct": 18.0, "gst_amt": 76.27, "total_amt": 500.0, "payment_type": "Pe Pulse Private Limited"},
    {"bill_no": "305", "date": "2026-03-07", "party_name": "Cash Sale Customer", "item_name": "Plastic Box", "qty": 2, "rate": 500.0, "taxable_amt": 1000.0, "gst_pct": 18.0, "gst_amt": 180.0, "total_amt": 1180.0, "payment_type": "Cash"}
])

excel_path = "test_sales_direct.xlsx"
df.to_excel(excel_path, index=False)

try:
    excel_res = parse_excel_to_json(excel_path)
    extracted = excel_res.get("extracted_data", [])
    print(f"Excel Extracted {len(extracted)} raw vouchers.")

    parser = SalesParser()
    cleaned_res = parser.process_extracted_data(extracted, module="Sales")
    cleaned_data = cleaned_res.get("extracted_data", [])

    print(f"SalesParser processed {len(cleaned_data)} cleaned vouchers successfully!")
    for vch in cleaned_data:
        print(" -> Bill:", vch.get("bill_no"), "| Party:", vch.get("party_name"), "| GST%:", vch.get("gst_pct"), "| Taxable:", vch.get("taxable_amount"), "| GST:", vch.get("gst"), "| Total:", vch.get("total"), "| Payment Type:", vch.get("payment_type"))

finally:
    if os.path.exists(excel_path):
        os.remove(excel_path)

print("🎉 Test Finished Successfully with 0 Errors!")
