import dbf
import os

path_40 = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0003/YR26/RKACCT40.DBF"

t40 = dbf.Table(path_40)
t40.open()

print("Inspecting RKACCT40 fields for BP2AMZ7R3HUZ:")
for r in t40:
    if dbf.is_deleted(r):
        continue
    vid = str(r['T40F01']).strip()
    if vid == 'BP2AMZ7R3HUZ':
        for name in t40.field_names:
            print(f"  Field {name}: {repr(r[name])}")
            
t40.close()
