import dbf
import os

yr_dir = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0006/YR26"

t01_path = None
for f in os.listdir(yr_dir):
    if f.lower() == 'rkacct01.dbf':
        t01_path = os.path.join(yr_dir, f)
        break

if not t01_path:
    print("RKACCT01.DBF not found.")
    sys.exit(1)

t01 = dbf.Table(t01_path)
t01.open()

print("Searching RKACCT01 for BRH6JA8ATWU6:")
found = False
for r in t01:
    if dbf.is_deleted(r):
        continue
    vid = str(r['FIELD01']).strip()
    if vid.upper() == 'BRH6JA8ATWU6':
        found = True
        print(f"Row found! ID: {vid}")
        for name in t01.field_names:
            val = r[name]
            if val is not None and str(val).strip():
                print(f"  Field {name}: {repr(val)}")

if not found:
    print("No matching rows found in RKACCT01.DBF.")
t01.close()
