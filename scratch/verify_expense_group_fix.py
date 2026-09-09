import sys
import os

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.insert(0, backend_dir)

from dbf_handler import MiracleDBFHandler

def test_group_resolution():
    # Instantiate handler with dummy path
    handler = MiracleDBFHandler.__new__(MiracleDBFHandler)
    
    test_cases = [
        ("Expenses", "G0000024"),
        ("Indirect Expenses", "G0000024"),
        ("INDIRECT EXP", "G0000024"),
        ("Direct Expense", "G0000023"),
        ("Indirect Income", "G0000022"),
        ("Direct Income", "G0000021"),
        ("Sundry Debtors", "G0000009"),
        ("Sundry Creditors", "G0000013"),
        ("Suspense", "G0000028"),
    ]
    
    passed = 0
    for hint, expected in test_cases:
        res = handler.resolve_group_code_from_hint(hint)
        if res == expected:
            print(f"✅ PASSED: '{hint}' -> '{res}'")
            passed += 1
        else:
            print(f"❌ FAILED: '{hint}' -> got '{res}', expected '{expected}'")
            
    print(f"\nTotal test results: {passed}/{len(test_cases)} passed.")
    assert passed == len(test_cases), "Group resolution test failed!"

if __name__ == "__main__":
    test_group_resolution()
