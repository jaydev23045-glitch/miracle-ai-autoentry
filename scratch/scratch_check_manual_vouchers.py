import dbf

path_41 = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0006/YR26/rkacct41.dbf"
t41 = dbf.Table(path_41)
t41.open()

print("Scanning for non-injected or interesting vouchers in RKACCT41:")
patterns = {}
count = 0
for r in t41:
    if dbf.is_deleted(r):
        continue
    v_id = str(r['FIELD01']).strip()
    f98 = str(r['FIELD98']).strip()
    # Check if the ID doesn't look like our generated 12-char ID (e.g. starts with BR, BP, BC, PP, SS and is 12 chars long)
    is_injected = len(v_id) == 12 and v_id[:2] in ('BR', 'BP', 'BC', 'PP', 'SS', 'CV')
    
    if not is_injected:
        f82 = str(r['FIELD82']).strip()
        f17 = str(r['FIELD17']).strip()
        f74 = str(r['FIELD74']).strip()
        f12 = str(r['FIELD12']).strip()
        print(f"Manual/Non-Injected -> ID: {v_id} | Type: {f98} | VouNo: {f12} | F17: {f17} | F74: {f74} | F82: {repr(f82)}")
        count += 1
        if count >= 30:
            break

t41.close()
