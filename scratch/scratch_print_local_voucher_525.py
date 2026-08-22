import dbf
import os

yr_dir = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0006/YR26"

t41_path = None
for f in os.listdir(yr_dir):
    if f.lower() == 'rkacct41.dbf':
        t41_path = os.path.join(yr_dir, f)
        break

t40_path = None
for f in os.listdir(yr_dir):
    if f.lower() == 'rkacct40.dbf':
        t40_path = os.path.join(yr_dir, f)
        break

t41 = dbf.Table(t41_path)
t41.open()

t40 = dbf.Table(t40_path)
t40.open()

print("Inspecting local Voucher No. 525:")
for r in t41:
    if dbf.is_deleted(r):
        continue
    vou_no = str(r['FIELD12']).strip()
    if vou_no == '525':
        vid = str(r['FIELD01']).strip()
        print(f"Header found in RKACCT41:")
        print(f"  Voucher ID: {vid}")
        print(f"  Voucher Type: {r['FIELD98']}")
        print(f"  Date: {r['FIELD02']}")
        print(f"  FIELD21: {repr(r['FIELD21'])}")
        print(f"  FIELD74: {repr(r['FIELD74'])}")
        print(f"  FIELD82 (narration): {repr(r['FIELD82'])}")
        print(f"  T41F83: {repr(r['T41F83'])}")
        
        # Look up memo
        for r40 in t40:
            if not dbf.is_deleted(r40) and str(r40['T40F01']).strip() == vid:
                print(f"Memo found in RKACCT40:")
                print(f"  T40F01: {r40['T40F01']}")
                print(f"  T40F09: {repr(r40['T40F09'])}")
                print(f"  T40F02 (memo): {repr(r40['T40F02'])}")
                break

t41.close()
t40.close()
