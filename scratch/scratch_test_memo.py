import dbf
import os

path_40 = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0006/YR26/rkacct40.dbf"

t40 = dbf.Table(path_40)
t40.open(mode=dbf.READ_WRITE)

test_rec = {
    'T40F01': 'TESTINGID123',
    'T40F09': 'XXXX',
    'T40F02': 'THIS IS A VERY LONG NARRATION THAT SHOULD GO TO THE FPT FILE NOT TRUNCATE'
}
rec = t40.append(test_rec)
print("Appended record!")

# Now read it back
for r in t40:
    if str(r['T40F01']).strip() == 'TESTINGID123':
        print(f"Read back T40F02: {repr(r['T40F02'])}")

# Delete the test record
dbf.delete(rec)
t40.pack()
t40.close()
