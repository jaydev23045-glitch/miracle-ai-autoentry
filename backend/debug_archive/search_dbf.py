import dbf
import os

path02 = '../CMP0002/YR27/RKACCT02.DBF'
if not os.path.exists(path02): path02 = '../CMP0002/YR27/rkacct02.dbf'

t02 = dbf.Table(path02)
t02.open()

for r in t02:
    if not dbf.is_deleted(r) and type(r['FIELD08']) in (float, int):
        amt = r['FIELD08']
        if abs(amt - 17500) < 1 or abs(amt - 5904.76) < 1: # type: ignore
            print(f"Found Amount={r['FIELD08']}! VID: {r['FIELD01']}")
            d = {f: r[f] for f in t02.field_names if type(r[f]) in [int, float] or f in ['FIELD03', 'FIELD04', 'FIELD12', 'FIELD38', 'T02F83', 'T02F96', 'FIELD18', 'FIELD19']}
            print(d)
            print("-" * 20)
t02.close()
