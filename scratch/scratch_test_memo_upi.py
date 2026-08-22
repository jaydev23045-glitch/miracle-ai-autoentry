import dbf
import os

path_40 = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0006/YR26/rkacct40.dbf"

t40 = dbf.Table(path_40)
t40.open(mode=dbf.READ_WRITE)

test_rec = {
    'T40F01': 'TESTINGID789',
    'T40F09': 'XXXX',
    'T40F02': 'UPI-00000020150886290-ANANTDEVRUKHKAR006 -1@OKSBI-'
}
rec = t40.append(test_rec)
print("Appended record!")

for r in t40:
    if str(r['T40F01']).strip() == 'TESTINGID789':
        print(f"Read back T40F02: {repr(r['T40F02'])}")

dbf.delete(rec)
t40.pack()
t40.close()
