import dbf
import os

path_41 = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0006/YR26/rkacct41.dbf"

t41 = dbf.Table(path_41)
t41.open()

for r in t41:
    try:
        amt = float(r['FIELD06'])
    except:
        amt = 0.0
    if not dbf.is_deleted(r) and str(r['FIELD02']).strip() == '2026-06-19' and abs(amt - 3100.0) < 0.1:
        print(f"VID: {r['FIELD01']}, Narration: {repr(r['FIELD82'])}")

t41.close()
