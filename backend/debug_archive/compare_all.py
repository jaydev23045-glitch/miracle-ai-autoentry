import dbf
v_id = 'SSJJ6AH0MB8T'

for tbl in ['RKACCT41.DBF', 'RKACCT02.DBF', 'RKACCT52.DBF', 'RKACCT01.DBF']:
    try:
        t_b = dbf.Table(f'../CMP0002/YR27/{tbl}')
        t_b.open()
        b_recs = [r for r in t_b if not dbf.is_deleted(r) and r['FIELD01'].strip() == v_id] # type: ignore
        t_b.close()
        
        t_a = dbf.Table(f'../MIRRACLE CHECK AFTER DATA/CMP0002/YR27/{tbl.lower()}')
        t_a.open()
        a_recs = [r for r in t_a if not dbf.is_deleted(r) and r['FIELD01'].strip() == v_id] # type: ignore
        t_a.close()
        
        fields = t_a.field_names
        diffs = []
        for i in range(min(len(b_recs), len(a_recs))):
            diff = {k: (b_recs[i][k], a_recs[i][k]) for k in fields if b_recs[i][k] != a_recs[i][k]}
            if diff: diffs.append(diff)
        print(f'{tbl} DIFFS: {diffs} | Len B: {len(b_recs)}, Len A: {len(a_recs)}')
    except Exception as e:
        print(f"Error on {tbl}: {e}")
