import dbf

path_41 = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0006/YR26/rkacct41.dbf"
path_40 = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0006/YR26/rkacct40.dbf"

t41 = dbf.Table(path_41)
t40 = dbf.Table(path_40)
t41.open()
t40.open()

print("Checking ALL native Miracle transactions for T40F09...")
count = 0
for r41 in t41:
    if dbf.is_deleted(r41): continue
    if r41['FIELD17'] != 'U0000000':
        vid = str(r41['FIELD01']).strip()
        for r40 in t40:
            if not dbf.is_deleted(r40) and str(r40['T40F01']).strip() == vid:
                print(f"Native {r41['FIELD98']} T40F09: {repr(r40['T40F09'])}, T40F02: {repr(r40['T40F02'])}")
                count += 1
                break
    if count >= 5: break

t41.close()
t40.close()
