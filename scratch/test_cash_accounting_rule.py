import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

from gemini_service import GeminiService

def test_cash_accounting_rule():
    print("==================================================")
    print("  TESTING CASH IN HAND ACCOUNTING RULE           ")
    print("==================================================\n")

    srv = GeminiService()
    test_narrations = [
        ("CASH RECEIVED", "Receipt", 35000.0),
        ("CASH DEPOSIT BY SELF", "Receipt", 12500.0),
        ("CASH WITHDRAWAL ATM", "Payment", 5000.0),
        ("BY CASH RECEIVED AT BRANCH", "Receipt", 39000.0),
        ("TO CASH PAID TO DRIVER", "Payment", 2500.0),
    ]

    for narr, tx_type, amt in test_narrations:
        group_nature = srv.classify_transaction_nature(narr, narr, tx_type=tx_type, amount=amt)
        res_stmt = srv.map_ledgers_for_statement(
            {"extracted_data": [{"narration": narr, "transaction_type": tx_type, "amount": amt}]},
            client_memory={"existing_ledgers": ["Cash Account", "ICICI Bank CA", "Sundry Debtors", "Sundry Creditors"]}
        )
        row = res_stmt["extracted_data"][0]
        print(f"NARRATION: '{narr}'")
        print(f"  ├── classify_transaction_nature : '{group_nature}'")
        print(f"  ├── Mapped Ledger               : '{row.get('mapped_ledger')}'")
        print(f"  └── Group Hint                  : '{row.get('group_hint')}'")

        assert group_nature == "Cash in Hand", f"Expected 'Cash in Hand', got '{group_nature}'"
        assert row.get('group_hint') == "Cash in Hand", f"Expected group_hint 'Cash in Hand', got '{row.get('group_hint')}'"
        assert row.get('mapped_ledger') in ("Cash Account", "Cash"), f"Expected Cash ledger, got '{row.get('mapped_ledger')}'"
        print("  --> ✅ PASS")
        print("-" * 50)

    print("\n🎉 ALL CASH IN HAND ACCOUNTING RULE TESTS PASSED 100%!")

if __name__ == "__main__":
    test_cash_accounting_rule()
