import dbf

path_41 = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0006/YR26/rkacct41.dbf"
t41 = dbf.Table(path_41)
t41.open()

print("Checking dates of surviving T40 memos...")
for r in t41:
    if not dbf.is_deleted(r) and 'DAY 2' in str(r['FIELD82']):
        print(f"Date: {r['FIELD02']}, VID: {r['FIELD01']}")
t41.close()
