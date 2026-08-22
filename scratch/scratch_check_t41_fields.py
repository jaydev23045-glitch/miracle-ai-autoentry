import dbf

path_41 = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0006/YR26/rkacct41.dbf"
t41 = dbf.Table(path_41)
t41.open()

for field in t41.field_names:
    info = t41.field_info(field)
    if info[1] > 50: # Length > 50
        print(f"Long field: {field}, {info}")
    if info[0] == 77: # Type M (Memo)
        print(f"Memo field: {field}, {info}")

t41.close()
