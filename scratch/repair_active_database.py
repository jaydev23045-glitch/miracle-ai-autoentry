import os
import sys
import json
import uuid
from pathlib import Path

# Add backend to path to import dbf
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../backend"))
import dbf

def repair_database():
    settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../backend/settings.json")
    if not os.path.exists(settings_path):
        print("❌ Error: settings.json not found!")
        return
        
    with open(settings_path, "r") as f:
        settings = json.load(f)
        
    base_path = settings.get("miracle_base_path", "")
    client_id = settings.get("active_client_id", "")
    
    if not base_path or not client_id:
        print("❌ Error: miracle_base_path or active_client_id not configured in settings.json!")
        return
        
    client_path = os.path.join(base_path, client_id)
    print(f"🔍 Checking database at: {client_path}")
    
    if not os.path.exists(client_path):
        print(f"❌ Error: Database path '{client_path}' does not exist.")
        print("👉 Please make sure your network share is mounted on your Mac!")
        print("👉 In Finder, press Cmd + K, enter smb://10.85.139.67/mirracle, and click Connect.")
        return
        
    # Discover years
    yr_folders = [d for d in os.listdir(client_path) if d.upper().startswith("YR") and os.path.isdir(os.path.join(client_path, d))]
    if not yr_folders:
        print("❌ Error: No financial year folders (e.g. YR26) found!")
        return
        
    print(f"📂 Found Year Folders: {yr_folders}")
    
    # 1. Fix RKACCGID.DBF in client root folder
    gid_path = os.path.join(client_path, "RKACCGID.DBF")
    if not os.path.exists(gid_path):
        gid_path = os.path.join(client_path, "rkaccgid.dbf")
        
    if os.path.exists(gid_path):
        print(f"🔧 Fixing GUID flags in {gid_path}...")
        tbl = dbf.Table(gid_path)
        tbl.open(mode=dbf.READ_WRITE)
        fixed_gid = 0
        for r in tbl:
            f01 = str(r.field01).strip()
            f02 = str(r.field02).strip()
            if f01 == 'YRT41':
                pfx = f02[:2].upper()
                if pfx in ('BR', 'BP', 'CR', 'CP', 'BC', 'CV'):
                    f04 = str(r.field04).strip()
                    if f04 != 'W':
                        dbf.write(r, field04='W'.ljust(25))
                        fixed_gid += 1
        tbl.reindex()
        tbl.close()
        print(f"✅ Fixed and reindexed {fixed_gid} records in RKACCGID.DBF")
    else:
        print("⚠️ Warning: RKACCGID.DBF not found in client folder!")
        
    # 2. Fix year specific tables
    for yr in yr_folders:
        yr_path = os.path.join(client_path, yr)
        t41_path = os.path.join(yr_path, "rkacct41.dbf")
        if not os.path.exists(t41_path):
            t41_path = os.path.join(yr_path, "RKACCT41.DBF")
            
        t40_path = os.path.join(yr_path, "rkacct40.dbf")
        if not os.path.exists(t40_path):
            t40_path = os.path.join(yr_path, "RKACCT40.DBF")

        # Load T40 long narrations to match and identify our pushed vouchers
        t40_narrations = {}
        if os.path.exists(t40_path):
            try:
                t40_tbl = dbf.Table(t40_path)
                t40_tbl.open(mode=dbf.READ_ONLY)
                for r in t40_tbl:
                    t40_narrations[str(r.t40f01).strip()] = str(r.t40f02).strip()
                t40_tbl.close()
            except Exception as e:
                print(f"⚠️ Warning: Could not read {t40_path} for matching: {e}")
            
        if os.path.exists(t41_path):
            print(f"🔧 Fixing Cash/Bank header fields in {t41_path}...")
            tbl = dbf.Table(t41_path)
            tbl.open(mode=dbf.READ_WRITE)
            fixed_t41 = 0
            for r in tbl:
                vtype = str(r.field98).strip()
                v_id = str(r.field01).strip()
                if vtype in ('BR', 'BP', 'BC') and v_id in t40_narrations:
                    f82_val = str(r.field82).strip()
                    t40_val = t40_narrations[v_id]
                    # If FIELD74, FIELD21 or FIELD82 need correcting:
                    is_our_voucher = False
                    if f82_val and t40_val.startswith(f82_val[:20]):
                        is_our_voucher = True
                    elif not f82_val:
                        is_our_voucher = True
                        
                    if is_our_voucher:
                        target_f82 = t40_val[:50].strip()
                        dbf.write(r, field74='CB', field21='O', field82=target_f82)
                        fixed_t41 += 1
            tbl.reindex()
            tbl.close()
            print(f"✅ Fixed and reindexed {fixed_t41} pushed records in {yr}/rkacct41.dbf")
            
            # Reindex other tables
            for other in ['rkacct40.dbf', 'rkacct01.dbf', 'rkacct02.dbf', 'rkacct52.dbf']:
                op = os.path.join(yr_path, other)
                if not os.path.exists(op):
                    op = os.path.join(yr_path, other.upper())
                if os.path.exists(op):
                    print(f"⚡ Reindexing {other} in {yr}...")
                    try:
                        otbl = dbf.Table(op)
                        otbl.open(mode=dbf.READ_WRITE)
                        otbl.reindex()
                        otbl.close()
                    except Exception as reindex_err:
                        print(f"⚠️ Warning: Could not reindex {other}: {reindex_err}")
                    
    print("\n🎉 Database repair completed successfully!")

if __name__ == "__main__":
    repair_database()


