import dbf

path_40 = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0006/YR26/rkacct40.dbf"
t40 = dbf.Table(path_40)
t40.open()

print("Scanning T40 for native records (not XXXX)...")
for r in t40:
    if not dbf.is_deleted(r):
        t = str(r['T40F09']).strip()
        if t != 'XXXX':
            n = str(r['T40F02']).strip()
            print(f"Native T40 found! Type='{t}', VID='{r['T40F01']}', Narration={repr(n[:50])}")

t40.close()
