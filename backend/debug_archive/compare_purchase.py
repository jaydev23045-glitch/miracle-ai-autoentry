import dbf

for comp in ['CMP0003', 'CMP0006']:
    try:
        t41 = dbf.Table(f'../{comp}/YR27/RKACCT41.DBF')
        t41.open()
        native_vids = []
        for r in t41:
            if not dbf.is_deleted(r) and r['FIELD98'] == 'PP':
                vid = r['FIELD01'].strip() # type: ignore
                if len(vid) == 12 and not vid[2:].isalpha():
                    native_vids.append(vid)
        t41.close()

        if native_vids:
            native_vid = native_vids[-1]
            t02 = dbf.Table(f'../{comp}/YR27/RKACCT02.DBF')
            t02.open()
            native_rec = [r for r in t02 if not dbf.is_deleted(r) and r['FIELD01'].strip() == native_vid] # type: ignore
            if native_rec:
                print(f"Native Purchase Found in {comp}: {native_vid}")
                n_dict = {f: native_rec[0][f] for f in t02.field_names}
                for k in n_dict:
                    if type(n_dict[k]) not in [float, int] or k in ['FIELD34', 'FIELD21', 'FIELD22', 'FIELD06', 'FIELD10']:
                        print(f"{k}: {repr(n_dict[k])}")
                break
            t02.close()
    except Exception as e:
        print(f"Error on {comp}: {e}")
