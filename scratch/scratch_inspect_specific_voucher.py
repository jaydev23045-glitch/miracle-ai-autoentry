import dbf

path_41 = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0003/YR27/rkacct41.dbf"
path_40 = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0003/YR27/rkacct40.dbf"

t41 = dbf.Table(path_41)
t40 = dbf.Table(path_40)
t41.open()
t40.open()

print("Searching for voucher with Date: 2026-06-13, Amount: 2627.00...")
found_v_id = None
for r in t41:
    if dbf.is_deleted(r):
        continue
    try:
        amt = float(r['FIELD06'])
    except:
        amt = 0.0
    dt = str(r['FIELD02']).strip()
    if dt == '2026-06-13' and abs(amt - 2627.00) < 0.01:
        found_v_id = str(r['FIELD01']).strip()
        print("--- RKACCT41 Header ---")
        for fn in t41.field_names:
            print(f"{fn}: {repr(r[fn])}")
        break

if found_v_id:
    print(f"\nSearching for Voucher ID {found_v_id} in RKACCT40...")
    found_t40 = False
    for r40 in t40:
        if not dbf.is_deleted(r40) and str(r40['T40F01']).strip() == found_v_id:
            print("--- RKACCT40 Record ---")
            for fn in t40.field_names:
                print(f"{fn}: {repr(r40[fn])}")
            found_t40 = True
            break
    if not found_t40:
        print("Voucher ID NOT found in RKACCT40!")
else:
    print("Voucher NOT found in RKACCT41!")

t41.close()
t40.close()
