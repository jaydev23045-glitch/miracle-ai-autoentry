import dbf

path_40 = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0006/YR26/rkacct40.dbf"
t40 = dbf.Table(path_40)
t40.open()

print("Scanning T40 for existing valid memos...")
count = 0
for r in t40:
    if not dbf.is_deleted(r):
        n = str(r['T40F02']).strip()
        t = str(r['T40F09']).strip()
        if len(n) > 5 and not n.startswith('UPI-0000'):
            print(f"Valid Memo found! Type T40F09='{t}', T40F02='{n}'")
            count += 1
            if count > 5:
                break
t40.close()
