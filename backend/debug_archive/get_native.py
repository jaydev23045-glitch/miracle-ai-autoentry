import dbf
t41 = dbf.Table('../MIRRACLE CHECK AFTER DATA/CMP0002/YR27/rkacct41.dbf')
t41.open()
# find a record that doesn't start with 'SS' or 'PP' maybe?
recs = [r['FIELD01'] for r in t41 if not dbf.is_deleted(r)]
t41.close()

t02 = dbf.Table('../MIRRACLE CHECK AFTER DATA/CMP0002/YR27/rkacct02.dbf')
t02.open()
print("Total T02:", len([r for r in t02 if not dbf.is_deleted(r)]))
t02.close()
