import dbf
import os

path = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0006/YR26/rkacct01.dbf"
if not os.path.exists(path):
    path = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0006/YR26/RKACCT01.DBF"

if os.path.exists(path):
    table = dbf.Table(path)
    table.open(mode=dbf.READ_ONLY)
    print(f"Total active records in rkacct01: {len([r for r in table if not dbf.is_deleted(r)])}")
    dates = set()
    for r in table:
        if not dbf.is_deleted(r):
            dates.add(str(r['FIELD02']))
    table.close()
    print("Unique dates in YR26 rkacct01.dbf:")
    for d in sorted(list(dates)):
        print(d)
else:
    print("Table not found!")
