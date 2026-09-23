import os
import sys
import pandas as pd

sys.path.insert(0, os.path.abspath("backend"))

from core.excel_parser import parse_excel_to_json, clean_extracted_bill_no, get_group_key
from modules.sales.parser import SalesParser

print("=== Running Comprehensive Universal Sales & Purchase Engine Test Suite ===")

# Test 1: Financial Year Bill No Cleaning
print("\n[Test 1] Financial Year Bill No Prefix Preservation:")
b1 = clean_extracted_bill_no("2025-26/286")
b2 = clean_extracted_bill_no("2026-27/304")
b3 = clean_extracted_bill_no("CR/2025-26/395")
print(f" -> '2025-26/286' cleaned to: '{b1}' (Expected: '2025-26/286')")
print(f" -> '2026-27/304' cleaned to: '{b2}' (Expected: '2026-27/304')")
print(f" -> 'CR/2025-26/395' cleaned to: '{b3}' (Expected: 'CR/2025-26/395')")
assert b1 == "2025-26/286", f"Failed: {b1}"
assert b2 == "2026-27/304", f"Failed: {b2}"
assert b3 == "CR/2025-26/395", f"Failed: {b3}"
print("✅ Test 1 Passed!")

# Test 2: Composite Group Key Generation
print("\n[Test 2] Composite Group Key Generation (BILL_NO + DATE + PARTY_NAME):")
row1 = {"bill_no": "2025-26/286", "date": "2026-03-01", "party_name": "Mr Tawde"}
row2 = {"bill_no": "2025-26/286", "date": "2026-03-02", "party_name": "Mr Ebraheem Motiwala"}
gk1 = get_group_key(row1)
gk2 = get_group_key(row2)
print(f" -> Row 1 Group Key: '{gk1}'")
print(f" -> Row 2 Group Key: '{gk2}'")
assert gk1 != gk2, "Group keys should be distinct for different parties/dates!"
print("✅ Test 2 Passed!")

# Test 3: Multi-Rate GST Excel Parsing
print("\n[Test 3] Multi-Rate GST & Payment Type Excel Extraction:")
df = pd.DataFrame([
    {"bill_no": "2025-26/304", "date": "2026-03-06", "party_name": "Mr Gopal Iyer", "item_name": "Cmf Gopal Iyer sandal", "qty": 1, "rate": 5714.29, "taxable_amt": 5714.29, "gst_pct": 5.0, "gst_amt": 285.71, "total_amt": 6000.0, "payment_type": "Pe Pulse Private Limited"},
    {"bill_no": "2025-26/304", "date": "2026-03-06", "party_name": "Mr Gopal Iyer", "item_name": "Cmf mould for Gopalkrishnan Iyer", "qty": 1, "rate": 5932.20, "taxable_amt": 5932.20, "gst_pct": 18.0, "gst_amt": 1067.80, "total_amt": 7000.0, "payment_type": "Pe Pulse Private Limited"},
    {"bill_no": "2025-26/304", "date": "2026-03-06", "party_name": "Mr Gopal Iyer", "item_name": "Foam box", "qty": 1, "rate": 423.73, "taxable_amt": 423.73, "gst_pct": 18.0, "gst_amt": 76.27, "total_amt": 500.0, "payment_type": "Pe Pulse Private Limited"},
    {"bill_no": "2025-26/305", "date": "2026-03-07", "party_name": "Cash Counter Customer", "item_name": "Plastic Box", "qty": 2, "rate": 500.0, "taxable_amt": 1000.0, "gst_pct": 18.0, "gst_amt": 180.0, "total_amt": 1180.0, "payment_type": "Cash"}
])

test_excel = "test_universal_temp.xlsx"
df.to_excel(test_excel, index=False)

try:
    excel_res = parse_excel_to_json(test_excel)
    extracted = excel_res.get("extracted_data", [])
    print(f" -> Extracted {len(extracted)} vouchers.")
    
    vch_304 = next((v for v in extracted if "304" in v.get("bill_no", "")), None)
    assert vch_304 is not None, "Bill 304 not found!"
    print(" -> Bill 304 Taxable:", vch_304.get("taxable_amount"), "(Expected: 12070.22)")
    print(" -> Bill 304 GST:", vch_304.get("gst"), "(Expected: 1429.78)")
    print(" -> Bill 304 Total:", vch_304.get("total"), "(Expected: 13500.0)")
    print(" -> Bill 304 GST %:", vch_304.get("gst_pct"), "(Expected: Multi)")

    assert abs(vch_304.get("taxable_amount") - 12070.22) < 0.05
    assert abs(vch_304.get("gst") - 1429.78) < 0.05
    assert abs(vch_304.get("total") - 13500.0) < 0.05
    assert vch_304.get("gst_pct") == "Multi"

    vch_305 = next((v for v in extracted if "305" in v.get("bill_no", "")), None)
    assert vch_305 is not None, "Bill 305 not found!"
    print(" -> Bill 305 Payment Type:", vch_305.get("payment_type"), "(Expected: Cash)")
    assert vch_305.get("payment_type") == "Cash"

    # Test SalesParser pipeline
    parser = SalesParser()
    cleaned_res = parser.process_extracted_data(extracted, module="Sales")
    cleaned = cleaned_res.get("extracted_data", [])
    print(f" -> SalesParser Output: {len(cleaned)} cleaned vouchers.")
    assert len(cleaned) == 2, f"Expected 2 vouchers, got {len(cleaned)}"
    print("✅ Test 3 Passed!")

finally:
    if os.path.exists(test_excel):
        os.remove(test_excel)

print("\n🎉 ALL TESTS PASSED SUCCESSFULLY WITH 100% PRECISION!")
