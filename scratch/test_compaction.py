import os
import shutil
import dbf
from pathlib import Path

def compact_dbf_table(dbf_path: str):
    dbf_path_obj = Path(dbf_path)
    if not dbf_path_obj.exists():
        print(f"File {dbf_path} not found.")
        return
        
    temp_dir = dbf_path_obj.parent / "TEMP"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_file = temp_dir / f"temp_{dbf_path_obj.name}"
    
    # Open original table
    table = dbf.Table(str(dbf_path_obj))
    table.open(dbf.READ_WRITE)
    
    has_memos = len(table._meta.memofields) > 0
    has_deleted = any(dbf.is_deleted(rec) for rec in table)
    
    print(f"Table details: has_memos={has_memos}, has_deleted={has_deleted}")
    
    if not has_memos and not has_deleted:
        print("No memos and no deleted records. Skipping compaction.")
        table.close()
        return
        
    try:
        new_table = table.new(str(temp_file))
        new_table.open(dbf.READ_WRITE)
        
        copied_count = 0
        for record in table:
            if not dbf.is_deleted(record):
                new_table.append(dbf.scatter(record))
                copied_count += 1
                
        new_table.close()
        table.close()
        
        print(f"Copied {copied_count} records to temporary table.")
        
        # Replace original files
        for ext in [".dbf", ".DBF", ".fpt", ".FPT", ".cdx", ".CDX"]:
            orig_ext_path = dbf_path_obj.with_suffix(ext)
            temp_ext_path = temp_file.with_suffix(ext)
            
            if temp_ext_path.exists():
                if orig_ext_path.exists():
                    orig_ext_path.unlink()
                shutil.move(str(temp_ext_path), str(orig_ext_path))
                print(f"Compacted companion file replaced: {orig_ext_path.name}")
                
    except Exception as e:
        print(f"Error compacting table {dbf_path_obj.name}: {e}")
        try: table.close()
        except: pass
        try: new_table.close()
        except: pass
        for ext in [".dbf", ".DBF", ".fpt", ".FPT", ".cdx", ".CDX"]:
            temp_ext_path = temp_file.with_suffix(ext)
            if temp_ext_path.exists():
                try: temp_ext_path.unlink()
                except: pass
        raise e

def run_test():
    # Let's find an existing rkacct40.dbf in CMP0003 or similar to test
    src_dbf = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0006/YR26/RKACCT40.DBF"
    if not os.path.exists(src_dbf):
        # try lowercase
        src_dbf = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0006/YR26/rkacct40.dbf"
        
    if not os.path.exists(src_dbf):
        print(f"❌ Test aborted: Source file not found: {src_dbf}")
        return
        
    test_dir = Path("scratch/test_dbf_compaction")
    test_dir.mkdir(parents=True, exist_ok=True)
    
    test_dbf_path = test_dir / "RKACCT40.DBF"
    
    # Copy DBF and FPT
    for ext in [".dbf", ".DBF", ".fpt", ".FPT"]:
        src_file = Path(src_dbf).with_suffix(ext)
        dst_file = test_dbf_path.with_suffix(ext)
        if src_file.exists():
            shutil.copy2(src_file, dst_file)
            
    print(f"Copied test files to {test_dbf_path}")
    
    # Open, print initial record count, delete one record, print memo file size
    orig_fpt_size = Path(test_dbf_path.with_suffix(".FPT")).stat().st_size
    print(f"Original FPT size: {orig_fpt_size} bytes")
    
    t = dbf.Table(str(test_dbf_path))
    t.open(dbf.READ_WRITE)
    orig_count = len(t)
    orig_active_count = len([rec for rec in t if not dbf.is_deleted(rec)])
    print(f"Original record count: {orig_count} (Active: {orig_active_count})")
    
    if orig_count > 0:
        # Find first active record to delete
        for rec in t:
            if not dbf.is_deleted(rec):
                dbf.delete(rec)
                print("Marked first active record as deleted.")
                break
    t.close()
    
    # Compact
    compact_dbf_table(str(test_dbf_path))
    
    # Verify count and sizes
    t2 = dbf.Table(str(test_dbf_path))
    t2.open(dbf.READ_ONLY)
    new_count = len(t2)
    t2.close()
    
    new_fpt_size = Path(test_dbf_path.with_suffix(".FPT")).stat().st_size
    print(f"New record count: {new_count}")
    print(f"New FPT size: {new_fpt_size} bytes")
    
    assert new_count == orig_active_count - 1, f"Compaction failed: record count {new_count} did not match expected active count {orig_active_count - 1}"
    assert new_fpt_size <= orig_fpt_size, "Compaction failed: FPT size did not decrease or stay same"
    print("✅ DBF and Memo Compaction verification test PASSED!")

if __name__ == "__main__":
    run_test()
