import dbf
import os

path41 = '../CMP0020/YR26/RKACCT41.DBF'
if not os.path.exists(path41): path41 = '../CMP0020/YR26/rkacct41.dbf'

t41 = dbf.Table(path41)
t41.open()
purchases = []
for r in t41:
    if not dbf.is_deleted(r) and r['FIELD98'] == 'PP':
        purchases.append(r['FIELD01'].strip()) # type: ignore
t41.close()

if len(purchases) < 2:
    print("Not enough purchases found to compare.")
else:
    # We will just grab the LAST 3 purchases to be safe.
    last_vids = purchases[-3:]
    
    path02 = '../CMP0020/YR26/RKACCT02.DBF'
    if not os.path.exists(path02): path02 = '../CMP0020/YR26/rkacct02.dbf'
    
    t02 = dbf.Table(path02)
    t02.open()
    
    for vid in last_vids:
        rec = [r for r in t02 if not dbf.is_deleted(r) and r['FIELD01'].strip() == vid] # type: ignore
        if rec:
            print(f"VID: {vid}")
            d = {f: rec[0][f] for f in t02.field_names if type(rec[0][f]) in [int, float] or f in ['FIELD03', 'FIELD04', 'FIELD12', 'FIELD38', 'T02F83', 'T02F96', 'FIELD18', 'FIELD19']}
            print(d)
            print("-" * 20)
    t02.close()
