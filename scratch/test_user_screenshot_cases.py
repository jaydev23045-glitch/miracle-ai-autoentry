import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

from modules.bank.parser import BankEntityRecognizer
from gemini_service import GeminiService

def test_screenshot_cases():
    print("==================================================")
    print("  TESTING USER SCREENSHOT ENTRIES (DEBIT/BANK)   ")
    print("==================================================\n")

    test_cases = [
        {
            "narration": "UPI 103676176527 DEBIT BHARAT RANCHHODBHAI KHUT SBIN0016036 bharatvideo003 oksbi bharaykaka",
            "expected_party": "Bharat Ranchhodbhai Khut",
            "forbidden_group": "Bank Accounts",
            "tx_type": "Payment"
        },
        {
            "narration": "UPI 105316979255 DEBIT SBIMOPS SBIN0016209 sbimops sbi MOPSUPITxn",
            "expected_party": "Sbimops",
            "expected_group": "Indirect Expenses",
            "tx_type": "Payment"
        },
        {
            "narration": "UPI 105433160856 DEBIT SHREE SANWALIYAJI MANDIR MANDAL SBIN0031432 jaisawariyaji sbi savriya seth",
            "expected_party": "Shree Sanwaliyaji Mandir Mandal",
            "forbidden_group": "Bank Accounts",
            "tx_type": "Payment"
        }
    ]

    for tc in test_cases:
        narr = tc["narration"]
        clean_p, _ = BankEntityRecognizer.extract_vendor_entity(narr)
        group = GeminiService.classify_transaction_nature(narr, clean_p, tc["tx_type"], 5000.0)

        print(f"RAW NARRATION : '{narr}'")
        print(f"  ├── Clean Party Extracted : '{clean_p}' (Expected: '{tc['expected_party']}')")
        print(f"  └── Group Classified     : '{group}'")

        assert clean_p == tc["expected_party"], f"Expected party '{tc['expected_party']}', got '{clean_p}'"
        assert group != tc.get("forbidden_group"), f"Group should NOT be '{tc.get('forbidden_group')}'"
        if "expected_group" in tc:
            assert group == tc["expected_group"], f"Expected group '{tc['expected_group']}', got '{group}'"
        print("  --> ✅ PASS\n" + "-" * 50)

    print("\n🎉 ALL USER SCREENSHOT FIX TESTS PASSED 100%!")

if __name__ == "__main__":
    test_screenshot_cases()
