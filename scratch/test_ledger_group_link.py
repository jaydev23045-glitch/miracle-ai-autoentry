import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from gemini_service import GeminiService

def test_ledger_group_linking():
    service = GeminiService()
    
    # Mock client_memory with existing master ledgers from Miracle DBF
    mock_memory = {
        "existing_ledgers": [
            {"name": "Yash Mansukhbhai Ramani", "group_name": "Sundry Creditors"},
            {"name": "Axis Bank Ltd.", "group_name": "Bank Accounts"},
            {"name": "Torrent Power Ltd", "group_name": "Indirect Expenses"}
        ],
        "expense_mappings": {}
    }
    
    # Mock extracted row from bank statement
    mock_rows = [
        {
            "narration": "Clg/RAMANI YASH MANSUKHBHAI/K",
            "transaction_type": "Payment",
            "amount": 16892.0
        }
    ]
    
    results = service.match_and_classify_narrations(
        rows=mock_rows,
        client_memory=mock_memory,
        instruction=""
    )
    
    row = results[0]
    print("Mapped Ledger:", row.get("mapped_ledger"))
    print("Group Hint:", row.get("group_hint"))
    
    assert row.get("mapped_ledger") == "Yash Mansukhbhai Ramani", f"Expected 'Yash Mansukhbhai Ramani', got '{row.get('mapped_ledger')}'"
    assert row.get("group_hint") == "Sundry Creditors", f"Expected 'Sundry Creditors', got '{row.get('group_hint')}'"
    print("✅ TEST PASSED: Master ledger 'Yash Mansukhbhai Ramani' correctly mapped to group 'Sundry Creditors'!")

if __name__ == "__main__":
    test_ledger_group_linking()
