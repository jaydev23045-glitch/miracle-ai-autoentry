import dbf
import os

path_01 = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0006/YR26/rkacct01.dbf"
if not os.path.exists(path_01): path_01 = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0006/YR26/RKACCT01.DBF"

path_m01 = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0006/YR26/rkaccm01.dbf"
if not os.path.exists(path_m01): path_m01 = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0006/YR26/RKACCM01.DBF"

ledgers = {}
if os.path.exists(path_m01):
    table_m = dbf.Table(path_m01)
    table_m.open(mode=dbf.READ_ONLY)
    for r in table_m:
        if not dbf.is_deleted(r):
            ledgers[str(r['FIELD01']).strip()] = str(r['FIELD02']).strip()
    table_m.close()

if os.path.exists(path_01):
    table = dbf.Table(path_01)
    table.open(mode=dbf.READ_ONLY)
    
    june_bank_rows = []
    for r in table:
        if not dbf.is_deleted(r):
            dt = str(r['FIELD02'])
            typ = str(r['FIELD98']).strip()
            if "-06-" in dt and typ in ('BR', 'BP', 'BC', 'CV'):
                june_bank_rows.append({
                    'id': str(r['FIELD01']).strip(),
                    'date': dt,
                    'type': typ,
                    'l_code': str(r['FIELD03']).strip(),
                    'l_name': ledgers.get(str(r['FIELD03']).strip(), "Unknown"),
                    'party_code': str(r['FIELD04']).strip(),
                    'party_name': ledgers.get(str(r['FIELD04']).strip(), "Unknown"),
                    'amount': float(str(r['FIELD05']).strip() or 0),
                    'dr_cr': str(r['FIELD06']).strip(),
                    'f21': str(r['FIELD21']).strip()
                })
    table.close()
    
    print(f"Total June BANK rows in rkacct01: {len(june_bank_rows)}")
    for row in june_bank_rows[:50]:
        print(row)
else:
    print("Table not found!")
