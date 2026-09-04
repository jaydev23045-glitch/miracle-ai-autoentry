import os
import sys
import json

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))
from routers.vouchers import sanitize_surrogates
from dbf_handler import MiracleDBFHandler

def test_surrogate_cleaning():
    print("==================================================")
    print("  TESTING SURROGATE UNICODE SANITIZER FIX        ")
    print("==================================================\n")

    # Create string containing lone surrogate \udfe6 (Position 44 error from user screenshot)
    corrupted_str = "577 S815665 11-Aug-2025 UPI/GANE " + chr(0xDDFE6) if hasattr(chr, '__call__') else "577 S815665 11-Aug-2025 UPI/GANE "
    # Construct exact surrogate string
    corrupted_str = "577 S815665 11-Aug-2025 UPI/GANE\udfe612345"

    print(f"Original Corrupted String Length: {len(corrupted_str)}")

    # 1. Test sanitize_surrogates helper
    clean_str = sanitize_surrogates(corrupted_str)
    print(f"Sanitized Clean String          : '{clean_str}'")

    # 2. Test JSON serialization (must NOT raise UnicodeEncodeError)
    payload_dict = {"narration": corrupted_str, "party": "Upi Ganes Hamba Pay Upi"}
    sanitized_payload = sanitize_surrogates(payload_dict)
    json_bytes = json.dumps(sanitized_payload)

    print(f"JSON Output                     : {json_bytes}")

    # 3. Test MiracleDBFHandler fit_dbf_str and clean_dbf_string
    dbf_clean = MiracleDBFHandler.clean_dbf_string(corrupted_str)
    print(f"DBF Cleaned String              : '{dbf_clean}'")

    dbf_fit = MiracleDBFHandler.fit_dbf_str(corrupted_str, 50)
    print(f"DBF Fitted String               : '{dbf_fit}'")

    assert "\udfe6" not in clean_str, "Surrogate \\udfe6 should be stripped from clean_str"
    assert "\udfe6" not in dbf_clean, "Surrogate \\udfe6 should be stripped from dbf_clean"

    print("\n🎉 ALL SURROGATE SANITIZER TESTS PASSED 100%!")

if __name__ == "__main__":
    test_surrogate_cleaning()
