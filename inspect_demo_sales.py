import os
import sys
import pandas as pd

sys.path.insert(0, os.path.abspath("backend"))

from core.excel_parser import parse_excel_to_json, find_and_clean_header, normalize_sheet_columns, clean_extracted_bill_no

file_path = "Test_Samples_And_Archives/DEMO SALES/PE PULSE/F.Y. 2025-26/MARCH-2026/Sale_Report_01-03-2026_to_31-03-2026.xls"

print("--- Inspecting Sheets ---")
xl = pd.ExcelFile(file_path)
print("Sheet Names:", xl.sheet_names)

for sheet in xl.sheet_names:
    df_raw = pd.read_excel(file_path, sheet_name=sheet)
    print(f"\n--- Sheet: '{sheet}' ---")
    print("Raw Columns:", list(df_raw.columns[:10]))
    df_cleaned = find_and_clean_header(df_raw)
    print("Cleaned Columns:", list(df_cleaned.columns[:10]))
    df_norm, resolved = normalize_sheet_columns(df_cleaned)
    print("Resolved Mapping:", resolved)
    if "bill_no" in df_norm.columns:
        print("First 5 bill_no values:", df_norm["bill_no"].head(5).tolist())

print("\n--- Running parse_excel_to_json ---")
res = parse_excel_to_json(file_path)
extracted = res.get("extracted_data", [])
print(f"Extracted {len(extracted)} vouchers.")
for vch in extracted[:10]:
    print("Vch Bill No:", vch.get("bill_no"), "| Party:", vch.get("party_name"), "| Date:", vch.get("date"), "| Total:", vch.get("total"))
