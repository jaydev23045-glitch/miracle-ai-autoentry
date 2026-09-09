import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from gemini_service import GeminiService

def test_accounting_classification():
    service = GeminiService()

    narr_rent = "19173-TPT-RENT-HASMUKH SHANTIL"
    narr_parking = "19173-TPT-PARKING-HASMUKH SHAN"

    group_rent = service.classify_transaction_nature(narr_rent, "PARKING", "Payment", 32550)
    group_parking = service.classify_transaction_nature(narr_parking, "PARKING", "Payment", 1250)

    print(f"Narr 1: '{narr_rent}' → Group: '{group_rent}'")
    print(f"Narr 2: '{narr_parking}' → Group: '{group_parking}'")

    assert group_rent in ("Direct Expenses", "Indirect Expenses"), f"Unexpected group for rent: {group_rent}"
    assert group_parking in ("Direct Expenses", "Indirect Expenses"), f"Unexpected group for parking: {group_parking}"
    assert "Loans & Advances" not in group_parking, "PARKING must NEVER classify as Loans & Advances!"

    print("✅ All accounting group classification tests PASSED successfully!")

if __name__ == "__main__":
    test_accounting_classification()
