import dbf
import os

path_01 = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0006/YR26/rkacct01.dbf"

t01 = dbf.Table(path_01)
t01.open()

print("RKACCT01 Field Names and Types:")
for name in t01.field_names:
    field_info = t01.field_info(name)
    print(f"  {name}: {field_info}")

t01.close()
