#!/usr/bin/env python3
"""
Test script for DBF Ledger Sanitization and Strict Word Boundary Substring Match.
Verifies fix for false 'REMARK' and 'KOTAK' mappings seen in UI screenshots.
"""
import sys
import os

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from gemini_service import GeminiService

def main():
    print("=" * 70)
    print("🚀 TESTING DBF LEDGER SANITIZER & RESERVED WORD MATCH GUARD")
    print("=" * 70)

    service = GeminiService()

    # Simulate existing DBF ledgers from RKACCM01.DBF (containing historical dirty entries)
    mock_dbf_ledgers = [
        {"name": "REMARK", "group_name": "SUNDRY DEBTORS"},
        {"name": "KOTAK", "group_name": "BANK ACCOUNTS"},
        {"name": "SAMKEN05 OKICICI", "group_name": "SUNDRY DEBTORS"},
        {"name": "SAURABHPANDEY PTYES SENT USING PAYTM", "group_name": "SUNDRY CREDITORS"},
        {"name": "DU82848 PTYES SENT USING PAYTM", "group_name": "SUNDRY CREDITORS"},
        {"name": "PRADEEPKUMARSHAW OKHD FCBANK", "group_name": "SUNDRY CREDITORS"},
        {"name": "MITALISOHANI", "group_name": "SUNDRY DEBTORS"},
        {"name": "Pushpa", "group_name": "SUNDRY DEBTORS"},
    ]

    mock_vouchers = [
        {"narration": "UPI-00000010093490489-PUSHPA-REMARK", "type": "Receipt"},
        {"narration": "4860-CUSTOMIZED SHOE ADVANCE MITALISOHANI", "type": "Receipt"},
        {"narration": "<-618 417442763-PAIDVIAKOTAKAPP", "type": "Payment"},
        {"narration": "UPI-002001585512-SAMKEN05@OI", "type": "Receipt"},
        {"narration": "NEFT CR-IBKL0NEFT01-SCUBE-PEP", "type": "Receipt"},
        {"narration": "NEFT DR-REMARK", "type": "Payment"},
    ]

    mock_input = {"status": "success", "extracted_data": mock_vouchers}
    mock_memory = {"existing_ledgers": mock_dbf_ledgers, "expense_mappings": {}}

    res = service.map_ledgers_for_statement(mock_input, mock_memory, module="Bank Statements")
    rows = res.get("extracted_data", [])

    print("\n--- MAPPING RESULTS ---")
    for r in rows:
        narr = r.get("narration")
        mapped = r.get("mapped_ledger")
        print(f"  Narration: '{narr[:45]}' -> Mapped: '{mapped}' ({r.get('group_hint', '')})")

    # Verification assertions
    r_pushpa = rows[0]
    assert r_pushpa["mapped_ledger"].upper() != "REMARK", "FAIL: Narration mapped to REMARK!"
    print("\n✅ PASS: 'REMARK' is blocked from false substring matching!")

    r_kotak = rows[2]
    assert r_kotak["mapped_ledger"].upper() != "KOTAK", "FAIL: Narration mapped to KOTAK bank account!"
    print("✅ PASS: 'KOTAK' bank account is excluded from false party matching!")

    r_samken = rows[3]
    assert "OKICICI" not in r_samken["mapped_ledger"].upper(), "FAIL: Dirty DBF handle string returned!"
    print("✅ PASS: Dirty DBF ledger 'SAMKEN05 OKICICI' sanitized cleanly!")

    print("\n=" * 70)
    print("ALL VERIFICATION CHECKS PASSED 100%!")
    print("=" * 70)

if __name__ == "__main__":
    main()
