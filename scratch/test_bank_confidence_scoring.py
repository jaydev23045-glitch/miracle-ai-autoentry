import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

from ai_memory import AIMemoryVault
from gemini_service import GeminiService

def test_narration_cleaning():
    print("--- TEST 1: NARRATION ENTITY CLEANING ---")
    test_cases = [
        ("NEFT DR-UTIB0000215-N402910391-RAMESH TRADERS PVT LTD-RAJKOT", "RAMESH TRADERS"),
        ("UPI-RAMESH TRADERS-RAMESH@OKAXIS-402910391-31/03/2025", "RAMESH TRADERS"),
        ("IMPS/42819028/HETALBHIMANI26215/ICIC0000102", "HETALBHIMANI"),
        ("ACH DR-5838 FOOT WEAR-01631000019173", "FOOT WEAR"),
        ("ATM WDL 31/03 5831 MUMBAI", ""),
        ("N103250239", ""),
        ("UTIB0000215", "")
    ]
    
    for raw_narr, expected_contain in test_cases:
        clean_k = AIMemoryVault.clean_mapping_key(raw_narr)
        print(f"Raw: '{raw_narr}'")
        print(f"  -> Cleaned Key: '{clean_k}'")
        if expected_contain:
            assert expected_contain in clean_k, f"Expected '{expected_contain}' in '{clean_k}'"
        else:
            assert clean_k == "", f"Expected empty key for noise '{raw_narr}', got '{clean_k}'"
    print("✅ All narration cleaning tests passed!\n")

def test_dynamic_confidence_scoring():
    print("--- TEST 2: DYNAMIC CONFIDENCE SCORING ---")
    ledger_lookup = {
        "RAMESH TRADERS": "Ramesh Traders",
        "STAFF SALARY": "Staff Salary",
        "OFFICE RENT": "Office Rent",
        "SUSPENSE ACCOUNT": "Suspense Account"
    }
    clean_memory = {
        "RAMESH TRADERS": "Ramesh Traders"
    }
    
    # 1. User Instruction
    s1 = GeminiService.calculate_dynamic_accounting_confidence(
        narration="NEFT-RAMESH TRADERS",
        mapped_ledger="Ramesh Traders",
        match_stage="S-UserInstruction",
        ledger_lookup=ledger_lookup,
        clean_memory=clean_memory
    )
    print(f"User Instruction Score: {s1} (Expected >= 95)")
    assert s1 >= 95
    
    # 2. Exact Master Ledger Match
    s2 = GeminiService.calculate_dynamic_accounting_confidence(
        narration="NEFT DR-RAMESH TRADERS-RAJKOT",
        mapped_ledger="Ramesh Traders",
        match_stage="S1-PartyExact",
        ledger_lookup=ledger_lookup,
        clean_memory=clean_memory
    )
    print(f"Exact Master Match Score: {s2} (Expected >= 90)")
    assert s2 >= 90
    
    # 3. Keyword Match
    s3 = GeminiService.calculate_dynamic_accounting_confidence(
        narration="SALARY PAID FOR MARCH",
        mapped_ledger="Staff Salary",
        match_stage="S3-Keyword",
        ledger_lookup=ledger_lookup,
        clean_memory=clean_memory
    )
    print(f"Keyword Match Score: {s3} (Expected >= 85)")
    assert s3 >= 85
    
    # 4. Illegal Nature Mapping Audit Penalty
    s4 = GeminiService.calculate_dynamic_accounting_confidence(
        narration="INCOME TAX PMT CHALLAN 280",
        mapped_ledger="Ramesh Traders",  # Illegal mapping! Tax should not map to trade vendor
        match_stage="S5-Fuzzy",
        ledger_lookup=ledger_lookup,
        clean_memory=clean_memory
    )
    print(f"Illegal Nature Mapping Score: {s4} (Expected < 60 due to penalty)")
    assert s4 < 60
    
    print("✅ All dynamic confidence scoring tests passed!\n")

if __name__ == "__main__":
    test_narration_cleaning()
    test_dynamic_confidence_scoring()
    print("🎉 ALL BANK SYSTEM VERIFICATION TESTS PASSED SUCCESSFULLY!")
