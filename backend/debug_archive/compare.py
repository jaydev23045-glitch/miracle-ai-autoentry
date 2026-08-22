import dbf
t_b = dbf.Table('../CMP0002/YR27/RKACCT01.DBF')
t_b.open()
b_recs = [r for r in t_b if not dbf.is_deleted(r) and r['FIELD01'].strip() == 'SSUX5P2EIPAX'] # type: ignore
t_b.close()
t_a = dbf.Table('../MIRRACLE CHECK AFTER DATA/CMP0002/YR27/rkacct01.dbf')
t_a.open()
a_recs = [r for r in t_a if not dbf.is_deleted(r) and r['FIELD01'].strip() == 'SSUX5P2EIPAX'] # type: ignore
t_a.close()
fields = t_a.field_names
diffs = []
for i in range(len(b_recs)):
    diff = {k: (b_recs[i][k], a_recs[i][k]) for k in fields if b_recs[i][k] != a_recs[i][k]}
    if diff: diffs.append(diff)
print('DIFFS:', diffs)
