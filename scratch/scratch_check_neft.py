import dbf

path_41 = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0006/YR26/rkacct41.dbf"
path_40 = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0006/YR26/rkacct40.dbf"

t41 = dbf.Table(path_41)
t40 = dbf.Table(path_40)
t41.open()
t40.open()

print("Checking NEFT DR mismatches...")
mismatches = 0
for r41 in t41:
    if dbf.is_deleted(r41): continue
    vid = str(r41['FIELD01']).strip()
    f82 = str(r41['FIELD82']).strip()
    
    if f82.startswith('NEFT DR-'):
        # Find matching T40
        for r40 in t40:
            if not dbf.is_deleted(r40) and str(r40['T40F01']).strip() == vid:
                t40_nar = str(r40['T40F02']).strip()
                print(f"VID {vid} T41='{f82}', T40='{t40_nar}'")
                if len(t40_nar) < len(f82) - 5: 
                    mismatches += 1
                break
    if mismatches > 10: break

t41.close()
t40.close()
