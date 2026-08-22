import dbf
import os

path = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0006/YR26/rkacct40.dbf"
if not os.path.exists(path):
    path = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/mock_CMP9999/YR26/rkacct40.dbf"

t40 = dbf.Table(path)
t40.open()
for field in t40.field_names:
    print(field, t40.field_info(field))
t40.close()
