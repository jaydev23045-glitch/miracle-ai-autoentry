import os
import sys
import pandas as pd

file_path = "Test_Samples_And_Archives/DEMO SALES/PE PULSE/F.Y. 2025-26/MARCH-2026/Sale_Report_01-03-2026_to_31-03-2026.xls"

xl = pd.ExcelFile(file_path)
print("Sheet Names:", xl.sheet_names)

for sheet in ["Miracle Registered B2B", "Miracle Unregistered B2C", "Miracle Cash Sales"]:
    if sheet in xl.sheet_names:
        df = pd.read_excel(file_path, sheet_name=sheet)
        print(f"\n================ SHEET: {sheet} ================")
        print("Raw Columns:", list(df.columns))
        print("\nFirst 3 rows:")
        print(df.head(3).to_string())
