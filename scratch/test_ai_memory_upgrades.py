import sys
import os

# Add backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

def test_ai_memory_upgrades():
    from ai_memory import AIMemoryVault
    vault = AIMemoryVault()
    
    # 1. Test Fuzzy Expense Mapping
    test_client = "CMP0021"
    vault.add_expense_mapping(test_client, "SWIGGY FOOD ORDER", "STAFF WELFARE")
    
    # Test exact match
    m1, k1 = vault.find_fuzzy_expense_mapping(test_client, "SWIGGY FOOD ORDER")
    print(f"Test 1 (Exact): '{m1}', key='{k1}'")
    assert m1 == "STAFF WELFARE"
    
    # Test fuzzy match with minor typo
    m2, k2 = vault.find_fuzzy_expense_mapping(test_client, "SWIGGY FOOD ORDR")
    print(f"Test 2 (Fuzzy): '{m2}', key='{k2}'")
    assert m2 == "STAFF WELFARE"
    
    # 2. Test Supplier Catalog with State Code
    sample_vouchers = [
        {
            "party_name": "TEST SUPPLIER PRIVATE LIMITED",
            "party_gstin": "24AAACB1234C1Z5",
            "party_city": "RAJKOT",
            "items": [{"name": "STEEL BAR 12MM"}]
        }
    ]
    mem = vault.load_memory(test_client)
    mem = vault._update_supplier_catalog(mem, sample_vouchers)
    sup_entry = mem.get("supplier_catalog", {}).get("test supplier private limited", {})
    print("Supplier Catalog Entry:", sup_entry)
    assert sup_entry.get("gstin") == "24AAACB1234C1Z5"
    assert sup_entry.get("state_code") == "24"
    
    # 3. Clean up test key
    vault.delete_expense_mapping(test_client, "SWIGGY FOOD ORDER")
    
    print("\n✅ All AI Memory Vault Upgrades Verified Successfully!")

if __name__ == "__main__":
    test_ai_memory_upgrades()
