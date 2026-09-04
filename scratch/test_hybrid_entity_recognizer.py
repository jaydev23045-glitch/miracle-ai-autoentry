import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

from modules.bank.parser import BankEntityRecognizer
from ai_memory import AIMemoryVault
from gemini_service import GeminiService

def test_hybrid_entity_recognizer():
    print("==================================================")
    print("   TESTING HYBRID BANK ENTITY RECOGNIZER (NER)   ")
    print("==================================================\n")

    test_narrations = [
        "NEFT DR-UTIB0000215-N402910391-RAMESH TRADERS PVT LTD-RAJKOT",
        "UPI-SHREE RAM ENTERPRISE-RAMESH@OKAXIS-402910391-31/03/2025",
        "IMPS/42819028/HETALBHIMANI26215/ICIC0000102",
        "ACH DR-5838 FOOT WEAR-01631000019173",
        "TRANSFER TO 01631000019173-SHREE KRISHNA TRADERS",
        "ATM WDL 31/03 5831 MUMBAI",
        "BANK CHARGES FOR SMS ALERT Q3 2025",
        "N103250239",
        "UTIB0000215",
        "SALARY PAYMENT MARCH 2025"
    ]

    for idx, narr in enumerate(test_narrations, start=1):
        clean_vendor, metadata = BankEntityRecognizer.extract_vendor_entity(narr)
        clean_mem_key = AIMemoryVault.clean_mapping_key(narr)
        clean_party_gemini = GeminiService.extract_clean_party_from_narration(narr)
        
        print(f"[{idx:02d}] RAW NARRATION: '{narr}'")
        print(f"     ├── Extracted Vendor Entity: '{clean_vendor}'")
        print(f"     ├── Metadata Entities    : {metadata}")
        print(f"     ├── Memory Key           : '{clean_mem_key}'")
        print(f"     └── Gemini Clean Party   : '{clean_party_gemini}'")
        print("-" * 50)

    print("\n✅ TEST COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    test_hybrid_entity_recognizer()
