import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

from modules.bank.parser import BankEntityRecognizer
from ai_memory import AIMemoryVault
from gemini_service import GeminiService

def test_debit_credit_token_removal():
    print("==================================================")
    print("  TEST 1: UNIVERSAL DEBIT/CREDIT TOKEN REMOVAL    ")
    print("==================================================\n")

    test_cases = [
        ("UPI 102438284429 DEBIT PUNJANI SAMIR", "Punjani Samir"),
        ("UPI 102483742751 DEBIT KETANBHAI DOBARIYA", "Ketanbhai Dobariya"),
        ("UPI 509320953947 CREDIT Azharuddin Mal", "Azharuddin Mal"),
        ("UPI 102568166131 DEBIT SROMPL INC", "Srompl Inc"),
        ("UPI 103002622340 DEBIT AJAY MAKWANA", "Ajay Makwana")
    ]

    for raw, expected_sub in test_cases:
        clean_party, metadata = BankEntityRecognizer.extract_vendor_entity(raw)
        clean_mem = AIMemoryVault.clean_mapping_key(raw)
        clean_gemini = GeminiService.extract_clean_party_from_narration(raw)
        print(f"RAW: '{raw}'")
        print(f"  ├── BankEntityRecognizer : '{clean_party}'")
        print(f"  ├── Memory Key           : '{clean_mem}'")
        print(f"  └── Gemini Party Cleaner : '{clean_gemini}'")

        assert "DEBIT" not in clean_party.upper(), f"DEBIT found in clean_party '{clean_party}'"
        assert "CREDIT" not in clean_party.upper(), f"CREDIT found in clean_party '{clean_party}'"
        assert "DEBIT" not in clean_mem, f"DEBIT found in clean_mem '{clean_mem}'"
        assert "CREDIT" not in clean_mem, f"CREDIT found in clean_mem '{clean_mem}'"
        print("  --> ✅ PASS")
        print("-" * 50)

    print("\n✅ Universal DEBIT/CREDIT Token Removal Test Passed!\n")

def test_counterparty_group_guard():
    print("==================================================")
    print("  TEST 2: COUNTERPARTY BANK ACCOUNTS GROUP GUARD   ")
    print("==================================================\n")

    srv = GeminiService()
    # Ajay Makwana payment must NOT map to Bank Accounts
    group1 = srv.classify_transaction_nature("UPI 103002622340 DEBIT AJAY MAKWANA", "Ajay Makwana", tx_type="Payment", amount=1300.0)
    print(f"Group for 'Ajay Makwana' Payment: '{group1}'")
    assert "BANK" not in group1.upper(), f"Counterparty payment wrongly assigned to Bank Accounts: '{group1}'"

    # Actual bank transfer (ICICI Bank CA) should map to Bank Accounts
    group2 = srv.classify_transaction_nature("TRANSFER TO ICICI BANK CA-0157", "ICICI Bank CA-0157", tx_type="Payment", amount=50000.0)
    print(f"Group for 'ICICI Bank CA-0157' Transfer: '{group2}'")
    assert group2 == "Bank Accounts", f"Actual bank transfer expected Bank Accounts, got '{group2}'"

    print("✅ Counterparty Bank Accounts Group Guard Test Passed!\n")

if __name__ == "__main__":
    test_debit_credit_token_removal()
    test_counterparty_group_guard()
    print("🎉 ALL DEBIT/CREDIT REMOVAL & GROUP GUARD TESTS PASSED 100%!")
