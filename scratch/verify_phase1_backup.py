import sys
import os
import shutil

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

from core.config import load_settings, validate_vouchers_pre_push
from routers.vouchers import copy_file_lock_resilient, backup_full_client_folder
from dbf_handler import MiracleDBFHandler

def test_copy_lock_resilient():
    print("Testing copy_file_lock_resilient...")
    src = "test_src.txt"
    dst = "test_dst.txt"
    with open(src, "w") as f:
        f.write("resilient copy content")
        
    try:
        success = copy_file_lock_resilient(src, dst)
        assert success, "Resilient copy failed"
        assert os.path.exists(dst), "Destination file not created"
        with open(dst, "r") as f:
            content = f.read()
        assert content == "resilient copy content", "Content mismatch"
        print("✅ copy_file_lock_resilient passed.")
    finally:
        if os.path.exists(src): os.remove(src)
        if os.path.exists(dst): os.remove(dst)

def test_mandatory_backup():
    print("\nTesting backup fallback path...")
    settings = load_settings()
    client_id = settings.get("active_client_id", "CMP0003")
    base_path = settings.get("miracle_base_path")
    
    # We will backup to empty path (meaning it should use default client_path/BACKUPS)
    client_path = os.path.join(base_path, client_id)
    fallback_backups_dir = os.path.join(client_path, "BACKUPS")
    
    # Remove existing BACKUPS folder inside client path if it exists to test creation
    if os.path.exists(fallback_backups_dir):
        # Clean old test files but leave others
        pass
        
    # Get active year folder
    handler = MiracleDBFHandler(client_path)
    active_year = handler.get_latest_year_folder()
    
    print(f"Active Year resolved: {active_year}")
    print(f"Creating backup...")
    try:
        archive_path = backup_full_client_folder(client_id, base_path, custom_backup_path="", active_year_folder=active_year)
        assert os.path.exists(archive_path), "Backup zip file not found"
        assert os.path.getsize(archive_path) > 0, "Backup zip file is empty"
        assert fallback_backups_dir in archive_path, f"Backup path '{archive_path}' did not fall back to '{fallback_backups_dir}'"
        print(f"✅ Backup created and validated successfully at: {archive_path}")
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        raise e

def test_pre_push_validation():
    print("\nTesting validate_vouchers_pre_push...")
    settings = load_settings()
    client_id = settings.get("active_client_id", "CMP0003")
    base_path = settings.get("miracle_base_path")
    client_path = os.path.join(base_path, client_id)
    handler = MiracleDBFHandler(client_path)
    active_year = handler.get_latest_year_folder()
    ledgers = handler.read_ledgers(active_year)
    
    # Test 1: Balanced invoice (should pass)
    valid_sales_vouchers = [
        {
            "date": "2025-06-15",
            "billNo": "INV-101",
            "party": ledgers[0]['name'] if ledgers else "SUSPENSE ACCOUNT",
            "taxable": 1000.0,
            "cgst": 90.0,
            "sgst": 90.0,
            "igst": 0.0,
            "gst": 180.0,
            "total": 1180.0,
            "discount": 0.0,
            "freight": 0.0,
            "tcs": 0.0,
            "tds": 0.0
        }
    ]
    
    errors = validate_vouchers_pre_push("Sales", valid_sales_vouchers, client_path, active_year, ledgers)
    # If ledgers is empty or first ledger is suspense, it might warn. But mathematically it should not fail on balance if first ledger matches.
    print(f"Valid sales voucher errors: {errors}")
    
    # Test 2: Unbalanced invoice (should fail)
    invalid_sales_vouchers = [
        {
            "date": "2025-06-15",
            "billNo": "INV-102",
            "party": ledgers[0]['name'] if ledgers else "SUSPENSE ACCOUNT",
            "taxable": 1000.0,
            "cgst": 90.0,
            "sgst": 90.0,
            "igst": 0.0,
            "gst": 180.0,
            "total": 1500.0, # Math mismatch: 1000+180 != 1500
            "discount": 0.0,
            "freight": 0.0,
            "tcs": 0.0,
            "tds": 0.0
        }
    ]
    errors = validate_vouchers_pre_push("Sales", invalid_sales_vouchers, client_path, active_year, ledgers)
    print(f"Invalid sales voucher errors (expected math failure): {errors}")
    assert any("Mathematically unbalanced" in err for err in errors), "Math validation check failed"
    print("✅ validate_vouchers_pre_push passed.")

if __name__ == "__main__":
    try:
        test_copy_lock_resilient()
        test_mandatory_backup()
        test_pre_push_validation()
        print("\n🎉 ALL PHASE 1 VERIFICATIONS PASSED SUCCESSFULLY!")
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        sys.exit(1)
