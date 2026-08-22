import os
import sys
import glob

# Add backend to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from dbf_handler import MiracleDBFHandler

base_path = "/Users/jaydevnakum/Work Place/WORK/APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank"

# Find all CMP folders
cmp_folders = [d for d in os.listdir(base_path) if d.startswith("CMP")]
print(f"Found CMP folders: {cmp_folders}")

for cmp in cmp_folders:
    cmp_path = os.path.join(base_path, cmp)
    if os.path.isdir(cmp_path):
        handler = MiracleDBFHandler(cmp_path)
        years = handler.get_available_year_folders()
        print(f"\n--- Client {cmp} (Years: {[y['name'] for y in years]}) ---")
        for y in years:
            yr_name = y['name']
            try:
                ledgers = handler.read_ledgers(yr_name)
                for l in ledgers:
                    name = l.get('name', '')
                    if 'BANK' in name.upper() or 'CHARG' in name.upper():
                        print(f"  [{yr_name}] Code: {l.get('code')}, Name: '{name}', GroupCode: {l.get('group_code')}, GroupName: '{l.get('group_name')}', Class: '{l.get('classification')}'")
            except Exception as e:
                print(f"  Error reading {yr_name}: {e}")
