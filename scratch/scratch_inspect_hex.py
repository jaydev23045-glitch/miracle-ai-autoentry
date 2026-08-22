import dbf

path_40 = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0006/YR26/rkacct40.dbf"
t40 = dbf.Table(path_40)
t40.open()

for r in t40:
    if str(r['T40F01']).strip() == 'BRJRJB2UBXEC':
        n = r['T40F02']
        print(f"T40F02 length: {len(n)}")
        print(f"T40F02 repr: {repr(n)}")
        print(f"T40F02 hex: {n.encode('utf-8').hex()}")
t40.close()
