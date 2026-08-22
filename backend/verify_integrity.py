import sys
import os

# Set paths
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "core"))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "modules"))

from core.models import InvoiceSchema, BankTransactionSchema
from modules.sales.parser import SalesParser
from modules.purchases.parser import PurchaseParser
from modules.bank.parser import BankParser

def test_sales_gst_normalization():
    print("Executing Test 1: Sales GST Normalization...")
    parser = SalesParser()
    
    # 1. Test standard rate (18.0%)
    rate_1 = parser.parse_gst_pct("18.0%")
    assert rate_1 == 18.0, f"Expected 18.0, got {rate_1}"
    
    # 2. Test crazy rate (810.00) -> should default to 18.0%
    rate_2 = parser.parse_gst_pct("810.00")
    assert rate_2 == 18.0, f"Expected 18.0 fallback, got {rate_2}"
    
    # 3. Test standard CGST/SGST rate (9.0%) -> should remain 9.0%
    rate_3 = parser.parse_gst_pct("9.0%")
    assert rate_3 == 9.0, f"Expected 9.0, got {rate_3}"
    
    print("✅ Test 1: Sales GST Normalization passed.")

def test_sales_item_cleaning():
    print("Executing Test 2: Sales Item Cleaning & Validation...")
    parser = SalesParser()
    
    mock_input = {
        "status": "success",
        "extracted_data": [
            {
                "bill_no": "INV-101",
                "date": "2026-07-29",
                "party_name": "ABC CLIENT",
                "party_gstin": "24ABCDE1234F1Z1",
                "items": [
                    {
                        "name": "Footwear Gst 18%",
                        "gst_pct": 18.0,
                        "amount": 1000.0,
                        "qty": 1.0,
                        "rate": 1000.0
                    },
                    {
                        "name": "sales",  # Invalid name - should be filtered out
                        "gst_pct": 810.0,
                        "amount": 500.0
                    }
                ]
            }
        ]
    }
    
    result = parser.clean_invoice_data(mock_input, {})
    rows = result.get("extracted_data", [])
    assert len(rows) == 1, "Expected 1 invoice row"
    
    items = rows[0].get("items", [])
    # The invalid "sales" item should be filtered out
    assert len(items) == 1, f"Expected 1 valid item, got {len(items)}"
    assert items[0]["name"] == "Footwear Gst 18%"
    assert items[0]["gst_pct"] == 18.0
    
    print("✅ Test 2: Sales Item Cleaning passed.")

def test_bank_contra_safety():
    print("Executing Test 3: Bank Contra Safety Checker...")
    from modules.bank.injector import is_contra_brand_swap
    
    # 1. UPI payment containing bank domain name in narration should NOT trigger brand swap
    res_1 = is_contra_brand_swap("UPI-VIJAY JUMB-VIJAY@OKHDFCBANK", "HDFC BANK")
    assert res_1 == True, "Expected True (brand inside VPA suffix matches own bank, not a contra)"
    
    # 2. General narration not containing own bank ledger name should NOT trigger brand swap
    res_2 = is_contra_brand_swap("UPI-RAM SINGH-RAM@OKAXIS", "HDFC BANK")
    assert res_2 == False, "Expected False"
    
    print("✅ Test 3: Bank Contra Safety Checker passed.")

def test_bank_charges_expense_rule():
    print("Executing Test 4: Bank Charges Accounting & Contra Exclusion Rule...")
    from dbf_handler import MiracleDBFHandler
    handler = MiracleDBFHandler("./")
    
    code_to_class = {
        "A001": "Expense",
        "A002": "Indirect Expenses",
        "A003": "Bank",
        "A004": "Cash"
    }
    
    # 1. Bank Charges must NEVER be Contra (BC)
    res_1 = handler.is_true_contra_entry("BANK CHARGES", "A001", code_to_class, party_group_code="G0000009")
    assert res_1 == False, "Bank Charges must NOT be a Contra entry"
    
    res_2 = handler.is_true_contra_entry("HDFC BANK COMM", "A001", code_to_class, party_group_code="G0000009")
    assert res_2 == False, "HDFC BANK COMM must NOT be a Contra entry"
    
    res_3 = handler.is_true_contra_entry("SMS CHARGES", "A001", code_to_class, party_group_code="G0000009")
    assert res_3 == False, "SMS CHARGES must NOT be a Contra entry"
    
    res_4 = handler.is_true_contra_entry("RUPAY MDR RCVRY", "A001", code_to_class, party_group_code="G0000009")
    assert res_4 == False, "RUPAY MDR RCVRY must NOT be a Contra entry"
    
    # 2. Genuine Cash-to-Bank transfer MUST be Contra
    res_5 = handler.is_true_contra_entry("CASH ACCOUNT", "A004", code_to_class, party_group_code="G0000005")
    assert res_5 == True, "Cash Account transfer MUST be a Contra entry"
    
    print("✅ Test 4: Bank Charges Accounting Rule passed.")

def test_pre_push_validation_and_suspense():
    print("Executing Test 5: Pre-push Validation & Suspense Foundation Rule...")
    from core.config import validate_vouchers_pre_push
    
    mock_ledgers = [
        {"name": "HDFC BANK", "code": "A001", "group_code": "G0000004"}
    ]
    
    mock_vouchers = [
        {
            "date": "2025-06-02",
            "amount": 2000.0,
            "party_name": "Suspense Account",
            "mapped_ledger": "Suspense Account",
            "transaction_type": "Payment"
        },
        {
            "date": "2025-06-02",
            "amount": 236.0,
            "party_name": "BANK CHARGES",
            "mapped_ledger": "BANK CHARGES",
            "transaction_type": "Payment"
        }
    ]
    
    mock_dir = os.path.join(os.path.dirname(__file__), "mock_CMP9999")
    errors = validate_vouchers_pre_push("Bank Statements", mock_vouchers, mock_dir, "yr25", mock_ledgers)
    assert len(errors) == 0, f"Expected 0 errors, got {errors}"
    
    # Verify Suspense retained
    assert mock_vouchers[0].get("group_hint") == "Suspense Account"
    
    # Verify Bank Charges classified as Indirect Expenses
    assert mock_vouchers[1].get("group_hint") == "Indirect Expenses"
    
    print("✅ Test 5: Pre-push Validation & Suspense Foundation Rule passed.")

def test_user_guidelines_engine():
    print("Executing Test 6: STAGE -1 User Guidelines Engine...")
    from gemini_service import GeminiService
    service = GeminiService(api_key="mock", model_name="gemini-2.5-flash")
    
    extracted_data = {
        "extracted_data": [
            {
                "narration": "UPI-915010058869853-PREKSHA-6152906",
                "transaction_type": "Receipt",
                "mapped_ledger": "",
                "amount": 500.0
            },
            {
                "narration": "PETROL PURCHASE IOCL MUMBAI",
                "transaction_type": "Payment",
                "mapped_ledger": "",
                "amount": 1500.0
            }
        ]
    }
    
    client_memory = {
        "existing_ledgers": [
            {"name": "UPI Debtors", "code": "APM8EMHC"},
            {"name": "Vehicle Expense", "code": "APVEH01"}
        ]
    }
    
    instruction = "Map PETROL to Vehicle Expense; If narration contains UPI map to UPI Debtors"
    
    res = service.map_ledgers_for_statement(extracted_data, client_memory, module="Bank Statements", instruction=instruction)
    rows = res["extracted_data"]
    
    assert rows[0]["mapped_ledger"] == "UPI Debtors", f"Expected 'UPI Debtors', got {rows[0]['mapped_ledger']}"
    assert rows[0]["confidence_score"] == 98, f"Expected 98 confidence for user rule, got {rows[0]['confidence_score']}"
    
    assert rows[1]["mapped_ledger"] == "Vehicle Expense", f"Expected 'Vehicle Expense', got {rows[1]['mapped_ledger']}"
    assert rows[1]["confidence_score"] == 98, f"Expected 98 confidence for user rule, got {rows[1]['confidence_score']}"
    
    print("✅ Test 6: STAGE -1 User Guidelines Engine passed.")

def main():
    try:
        test_sales_gst_normalization()
        test_sales_item_cleaning()
        test_bank_contra_safety()
        test_bank_charges_expense_rule()
        test_pre_push_validation_and_suspense()
        test_user_guidelines_engine()
        print("\n🎉 ALL 6 INTEGRITY TESTS PASSED SUCCESSFULLY! Zero regressions detected.")
    except AssertionError as ae:
        print(f"\n❌ REGRESSION DETECTED: {ae}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ RUNTIME ERROR DURING VERIFICATION: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
