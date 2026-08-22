import dbf
import os
import json

with open("backend/settings.json", "r") as f:
    settings = json.load(f)

base_path = settings["miracle_base_path"]
client_id = settings["active_client_id"]

path_41 = os.path.join(base_path, client_id, "YR26", "rkacct41.dbf")
if not os.path.exists(path_41):
    path_41 = os.path.join(base_path, client_id, "YR26", "RKACCT41.DBF")

t41 = dbf.Table(path_41)
t41.open()

path_40 = os.path.join(base_path, client_id, "YR26", "rkacct40.dbf")
if not os.path.exists(path_40):
    path_40 = os.path.join(base_path, client_id, "YR26", "RKACCT40.DBF")

t40 = dbf.Table(path_40)
t40.open()

print("Searching RKACCT41 for BRWDGR6OVGFI:")
for r in t41:
    if dbf.is_deleted(r):
        continue
    vid = str(r['FIELD01']).strip()
    if vid.upper() == 'BRWDGR6OVGFI':
        print(f"Header found in RKACCT41:")
        for name in t41.field_names:
            val = r[name]
            if val is not None and str(val).strip():
                print(f"  Field {name}: {repr(val)}")
                
        # Look up memo
        for r40 in t40:
            if not dbf.is_deleted(r40) and str(r40['T40F01']).strip() == vid:
                print(f"Memo found in RKACCT40:")
                print(f"  T40F01: {r40['T40F01']}")
                print(f"  T40F09: {repr(r40['T40F09'])}")
                print(f"  T40F02 (memo): {repr(r40['T40F02'])}")
                break

t41.close()
t40.close()
