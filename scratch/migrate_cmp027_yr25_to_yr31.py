import os
import sys
import datetime
import dbf

CLIENT_DIR = "/Users/jaydevnakum/Work Place/WORK/APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0027"
SRC_YR = os.path.join(CLIENT_DIR, "YR25")
TGT_YR = os.path.join(CLIENT_DIR, "YR31")

def run_migration():
    print(f"=== CMP0027 BANK VOUCHER MIGRATION: YR25 -> YR31 ===")
    
    src_t41_p = os.path.join(SRC_YR, "RKACCT41.DBF")
    src_t01_p = os.path.join(SRC_YR, "RKACCT01.DBF")
    src_t40_p = os.path.join(SRC_YR, "RKACCT40.DBF")
    
    tgt_t41_p = os.path.join(TGT_YR, "RKACCT41.DBF")
    tgt_t01_p = os.path.join(TGT_YR, "RKACCT01.DBF")
    tgt_t40_p = os.path.join(TGT_YR, "RKACCT40.DBF")
    
    if not os.path.exists(src_t41_p) or not os.path.exists(tgt_t41_p):
        print("❌ Error: Target or source DBF files missing!")
        sys.exit(1)

    print(f"Opening source tables in {SRC_YR}...")
    table_src41 = dbf.Table(src_t41_p)
    table_src01 = dbf.Table(src_t01_p)
    table_src40 = dbf.Table(src_t40_p) if os.path.exists(src_t40_p) else None
    
    table_src41.open(dbf.READ_WRITE)
    table_src01.open(dbf.READ_WRITE)
    if table_src40: table_src40.open(dbf.READ_WRITE)

    # Find target misrouted voucher IDs
    target_vids = set()
    rows_to_move_41 = []
    
    for r in table_src41:
        prefix = str(r['FIELD98']).strip()
        vdate = r['FIELD02']
        if prefix in ['BP', 'BR', 'BC'] and vdate and vdate >= datetime.date(2025, 4, 1):
            vid = str(r['FIELD01']).strip()
            target_vids.add(vid)
            rows_to_move_41.append(r)
            
    print(f"Found {len(rows_to_move_41)} header vouchers in YR25 to migrate to YR31.")
    
    rows_to_move_01 = [r for r in table_src01 if str(r['FIELD01']).strip() in target_vids]
    rows_to_move_40 = [r for r in table_src40 if str(r['T40F01']).strip() in target_vids] if table_src40 else []
    
    print(f"Found {len(rows_to_move_01)} line item rows in YR25/RKACCT01.DBF.")
    print(f"Found {len(rows_to_move_40)} memo rows in YR25/RKACCT40.DBF.")
    
    if len(rows_to_move_41) == 0:
        print("No misrouted vouchers found in YR25. Exiting.")
        table_src41.close()
        table_src01.close()
        if table_src40: table_src40.close()
        return

    # Open target tables in YR31
    print(f"\nOpening target tables in {TGT_YR}...")
    table_tgt41 = dbf.Table(tgt_t41_p).open(dbf.READ_WRITE)
    table_tgt01 = dbf.Table(tgt_t01_p).open(dbf.READ_WRITE)
    table_tgt40 = dbf.Table(tgt_t40_p).open(dbf.READ_WRITE) if os.path.exists(tgt_t40_p) else None
    
    # Check existing VIDs in target to avoid duplicates
    existing_tgt_vids = set(str(r['FIELD01']).strip() for r in table_tgt41)
    
    injected_41_cnt = 0
    injected_01_cnt = 0
    injected_40_cnt = 0
    
    print("Appending headers to YR31/RKACCT41.DBF...")
    for r in rows_to_move_41:
        vid = str(r['FIELD01']).strip()
        if vid in existing_tgt_vids:
            continue
            
        r_dict = {}
        for fname in table_tgt41.field_names:
            if fname in table_src41.field_names:
                val = r[fname]
            else:
                val = None
            if fname == 'T41F45':
                val = 31  # Year suffix for YR31
            r_dict[fname] = val
            
        table_tgt41.append(r_dict)
        injected_41_cnt += 1
        
    print("Appending line details to YR31/RKACCT01.DBF...")
    for r in rows_to_move_01:
        r_dict = {}
        for fname in table_tgt01.field_names:
            if fname in table_src01.field_names:
                val = r[fname]
            else:
                val = None
            r_dict[fname] = val
        table_tgt01.append(r_dict)
        injected_01_cnt += 1

    if table_tgt40 and rows_to_move_40:
        print("Appending memo narrations to YR31/RKACCT40.DBF...")
        for r in rows_to_move_40:
            r_dict = {}
            for fname in table_tgt40.field_names:
                if fname in table_src40.field_names:
                    val = r[fname]
                else:
                    val = None
                r_dict[fname] = val
            table_tgt40.append(r_dict)
            injected_40_cnt += 1

    table_tgt41.close()
    table_tgt01.close()
    if table_tgt40: table_tgt40.close()
    
    print(f"✅ Successfully appended {injected_41_cnt} headers, {injected_01_cnt} line items, {injected_40_cnt} memo records to YR31!")
    
    # Delete misrouted rows from YR25
    print("\nDeleting misrouted records from YR25...")
    deleted_41 = 0
    for r in rows_to_move_41:
        dbf.delete(r)
        deleted_41 += 1
        
    deleted_01 = 0
    for r in rows_to_move_01:
        dbf.delete(r)
        deleted_01 += 1
        
    if rows_to_move_40:
        for r in rows_to_move_40:
            dbf.delete(r)

    table_src41.pack()
    table_src01.pack()
    if table_src40: table_src40.pack()
    
    table_src41.close()
    table_src01.close()
    if table_src40: table_src40.close()

    print(f"✅ Cleaned {deleted_41} header records and {deleted_01} line items from YR25!")
    print("=== MIGRATION COMPLETE ===")

if __name__ == "__main__":
    run_migration()
