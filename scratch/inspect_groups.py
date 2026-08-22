import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from dbf_handler import MiracleDBFHandler

base_path = "/Users/jaydevnakum/Work Place/WORK/APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank"
handler = MiracleDBFHandler(os.path.join(base_path, "CMP0004"))
groups = handler.read_account_groups("YR26")
for g in groups:
    print(f"Code: {g['code']}, Name: '{g['name']}', Parent: '{g.get('parent_code')}' ('{g.get('parent_name')}'), Category: '{g.get('category')}'")
