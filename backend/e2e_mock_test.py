import os
import shutil
from pathlib import Path
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dbf_handler import MiracleDBFHandler

BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE_DIR = BASE_DIR / 'CMP0006' / 'yr25'
MOCK_CLIENT = 'mock_CMP9999'
MOCK_DIR = BASE_DIR / 'backend' / MOCK_CLIENT
MOCK_YR_DIR = MOCK_DIR / 'yr25'

def setup_mock_environment():
    print("Setting up mock environment...")
    if MOCK_DIR.exists():
        shutil.rmtree(MOCK_DIR)
    MOCK_YR_DIR.mkdir(parents=True)
    
    # Copy all dbf, fpt, cdx files to ensure consistency
    for ext in ['*.DBF', '*.dbf', '*.FPT', '*.fpt', '*.CDX', '*.cdx']:
        for src in SOURCE_DIR.glob(ext):
            dst = MOCK_YR_DIR / src.name
            shutil.copy2(src, dst)

def run_mock_injections():
    handler = MiracleDBFHandler(str(MOCK_DIR))
    
    sales_vouchers = [
        {
            "date": "2024-04-01",
            "voucher_no": "S-MOCK-01",
            "party_name": "CASH ACCOUNT",
            "party_gstin": "",
            "items": [
                {"item_name": "TEST ITEM", "qty": 1, "rate": 100, "amount": 100}
            ],
            "taxable": 100.0,
            "cgst": 9.0,
            "sgst": 9.0,
            "igst": 0.0,
            "total": 118.0
        }
    ]
    
    try:
        print("\n--- Running Mock Sales Injection ---")
        count = handler.inject_vouchers(
            module="Sales", 
            vouchers=sales_vouchers,
            year_folder="yr25",
            sales_prefix="SS,SS",
            purchase_prefix="PP,PP",
            sales_setup_id=5,
            purchase_setup_id=6,
            sales_series=""
        )
        print(f"Sales Injection SUCCESS: {count} records added")
    except Exception as e:
        print(f"Sales Injection Failed: {e}")

    purchase_vouchers = [
        {
            "date": "2024-04-02",
            "voucher_no": "P-MOCK-01",
            "party_name": "CASH ACCOUNT",
            "party_gstin": "",
            "items": [
                {"item_name": "TEST ITEM", "qty": 1, "rate": 200, "amount": 200}
            ],
            "taxable": 200.0,
            "cgst": 12.0,
            "sgst": 12.0,
            "igst": 0.0,
            "total": 224.0
        }
    ]
    
    try:
        print("\n--- Running Mock Purchase Injection ---")
        count = handler.inject_vouchers(
            module="Purchases", 
            vouchers=purchase_vouchers,
            year_folder="yr25",
            sales_prefix="SS,SS",
            purchase_prefix="PP,PP",
            sales_setup_id=5,
            purchase_setup_id=6,
            sales_series=""
        )
        print(f"Purchase Injection SUCCESS: {count} records added")
    except Exception as e:
        print(f"Purchase Injection Failed: {e}")
        
    bank_vouchers = [
        {
            "Date": "2024-04-03",
            "Narration": "TEST NEFT",
            "Withdrawal Amt": "100.00",
            "Deposit Amt": "0.00",
            "Balance": "1000.00",
            "mapped_ledger": "BANK CHARGES",
            "transaction_type": "Payment"
        }
    ]
    
    try:
        print("\n--- Running Mock Bank Injection ---")
        count = handler.inject_vouchers(
            module="Bank Statements", 
            vouchers=bank_vouchers,
            year_folder="yr25",
            bank_name="HDFC BANK",
            sales_prefix="SS,SS",
            purchase_prefix="PP,PP",
            sales_setup_id=5,
            purchase_setup_id=6,
            sales_series=""
        )
        print(f"Bank Injection SUCCESS: {count} records added")
    except Exception as e:
        print(f"Bank Injection Failed: {e}")

if __name__ == "__main__":
    setup_mock_environment()
    run_mock_injections()
