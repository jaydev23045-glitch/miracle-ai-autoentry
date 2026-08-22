import dbf

path_41 = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0006/YR26/rkacct41.dbf"
t41 = dbf.Table(path_41)
t41.open()
print("FIELD82 info:", t41.field_info('FIELD82'))
t41.close()
