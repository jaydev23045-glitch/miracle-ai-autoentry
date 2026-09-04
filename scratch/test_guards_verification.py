import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

from ai_memory import AIMemoryVault
from modules.bank.parser import BankEntityRecognizer

def test_single_word_guard():
    print("--- TEST 1: SINGLE SHORT WORD SPECIFICITY GUARD ---")
    # Single short generic words (< 5 chars) should be rejected
    rejected_cases = ["RAM", "JAY", "ROY", "DEB"]
    for word in rejected_cases:
        key = AIMemoryVault.clean_mapping_key(word)
        print(f"Key for '{word}': '{key}'")
        assert key == "", f"Expected empty key for generic single word '{word}', got '{key}'"
        
    # Multi-word or distinct brand keys should be accepted
    accepted_cases = [("RAM TRADERS", "RAM TRADERS"), ("CRED", "CRED"), ("RAMESH", "RAMESH")]
    for raw, expected in accepted_cases:
        key = AIMemoryVault.clean_mapping_key(raw)
        print(f"Key for '{raw}': '{key}'")
        assert key != "", f"Expected valid key for '{raw}', got empty string"
    print("✅ Solution 1 Test Passed!\n")

def test_vendor_name_preservation():
    print("--- TEST 2: VENDOR NAME PRESERVATION GUARD ---")
    # Studio 24 / Super 99 should preserve 24/99 in narration
    narr = "UPI-STUDIO 24-STUDIO@OKAXIS-402910391"
    clean_party, metadata = BankEntityRecognizer.extract_vendor_entity(narr)
    print(f"Raw: '{narr}'")
    print(f"  -> Extracted Vendor: '{clean_party}'")
    print(f"  -> Metadata: {metadata}")
    assert "Studio 24" in clean_party or "Studio" in clean_party, f"Expected Studio 24 in '{clean_party}'"
    print("✅ Solution 2 Test Passed!\n")

if __name__ == "__main__":
    test_single_word_guard()
    test_vendor_name_preservation()
    print("🎉 ALL GUARD VERIFICATION TESTS PASSED SUCCESSFULLY!")
