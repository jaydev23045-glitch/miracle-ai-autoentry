import dbf
import os
import shutil

path_40 = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0006/YR26/rkacct40.dbf"
path_40_cdx = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0006/YR26/rkacct40.cdx"
path_40_cdx_bak = path_40_cdx + ".bak"

# Rename CDX to simulate safe_cdx_context
if os.path.exists(path_40_cdx):
    os.rename(path_40_cdx, path_40_cdx_bak)

try:
    t40 = dbf.Table(path_40)
    t40.open(mode=dbf.READ_WRITE)

    test_rec = {
        'T40F01': 'TESTINGID456',
        'T40F09': 'XXXX',
        'T40F02': 'UPI-THIS IS A VERY LONG NARRATION THAT SHOULD GO TO THE FPT FILE'
    }
    rec = t40.append(test_rec)
    print("Appended record!")

    # Now read it back
    for r in t40:
        if str(r['T40F01']).strip() == 'TESTINGID456':
            print(f"Read back T40F02: {repr(r['T40F02'])}")

    dbf.delete(rec)
    t40.pack()
    t40.close()
finally:
    # Restore CDX
    if os.path.exists(path_40_cdx_bak):
        os.rename(path_40_cdx_bak, path_40_cdx)
