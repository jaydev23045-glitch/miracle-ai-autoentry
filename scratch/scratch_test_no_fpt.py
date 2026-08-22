import dbf
import os
import shutil

path_40 = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0006/YR26/rkacct40.dbf"
path_fpt = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0006/YR26/rkacct40.fpt"
path_fpt_bak = path_fpt + ".bak"

if os.path.exists(path_fpt):
    os.rename(path_fpt, path_fpt_bak)

try:
    t40 = dbf.Table(path_40)
    t40.open(mode=dbf.READ_WRITE)

    test_rec = {
        'T40F01': 'TESTMISSFPT1',
        'T40F09': 'XXXX',
        'T40F02': 'UPI-THIS SHOULD BE TRUNCATED IF FPT IS MISSING'
    }
    rec = t40.append(test_rec)
    print("Appended record without FPT!")

    for r in t40:
        if str(r['T40F01']).strip() == 'TESTMISSFPT1':
            print(f"Read back T40F02: {repr(r['T40F02'])}")

    dbf.delete(rec)
    t40.pack()
    t40.close()
except Exception as e:
    print(f"Failed: {e}")
finally:
    if os.path.exists(path_fpt_bak):
        os.rename(path_fpt_bak, path_fpt)
