#!/usr/bin/env python3
"""
Test script to verify case-insensitive deletion of product_catalog and supplier_catalog entries.
"""
import sys
import os

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from routers.vouchers import delete_memory_vault_entry, bulk_delete_memory_vault_entries
from ai_memory import AIMemoryVault

def main():
    print("=" * 70)
    print("🚀 TESTING MEMORY VAULT CATALOG DELETION BUG FIX")
    print("=" * 70)

    client_id = "CMP0006"
    vault = AIMemoryVault()
    mem_data = vault.load_memory(client_id)

    # Add a test product entry with uppercase key
    test_prod_key = "TEST_PRODUCT_DELETE"
    if "product_catalog" not in mem_data:
        mem_data["product_catalog"] = {}
    mem_data["product_catalog"][test_prod_key] = {"display_name": "Test Item", "hsn": "1234", "gst_pct": 5}
    vault.save_memory(client_id, mem_data)

    # Test deleting with original case "TEST_PRODUCT_DELETE"
    res1 = delete_memory_vault_entry(category="product_catalog", key="TEST_PRODUCT_DELETE")
    print(f"Delete test 1 (exact case): {res1}")

    # Add another test product entry
    mem_data = vault.load_memory(client_id)
    mem_data["product_catalog"]["UPPER_PROD_KEY"] = {"display_name": "Upper Prod"}
    vault.save_memory(client_id, mem_data)

    # Test deleting with lowercase "upper_prod_key"
    res2 = delete_memory_vault_entry(category="product_catalog", key="upper_prod_key")
    print(f"Delete test 2 (lowercase key): {res2}")

    # Test bulk delete
    mem_data = vault.load_memory(client_id)
    mem_data["product_catalog"]["BULK_KEY_1"] = {"display_name": "Bulk 1"}
    if "supplier_catalog" not in mem_data:
        mem_data["supplier_catalog"] = {}
    mem_data["supplier_catalog"]["BULK_SUPP_1"] = {"display_name": "Bulk Supplier 1"}
    vault.save_memory(client_id, mem_data)

    res3 = bulk_delete_memory_vault_entries({
        "client_id": client_id,
        "items": [
            {"category": "product_catalog", "key": "bulk_key_1"},
            {"category": "supplier_catalog", "key": "BULK_SUPP_1"}
        ]
    })
    print(f"Bulk Delete test 3: {res3}")

    # Verify everything deleted
    final_mem = vault.load_memory(client_id)
    p_cat = final_mem.get("product_catalog", {})
    s_cat = final_mem.get("supplier_catalog", {})

    assert "TEST_PRODUCT_DELETE" not in p_cat
    assert "UPPER_PROD_KEY" not in p_cat
    assert "BULK_KEY_1" not in p_cat
    assert "BULK_SUPP_1" not in s_cat

    print("\n✅ SUCCESS: All catalog items deleted cleanly without case-sensitivity failure!")

if __name__ == "__main__":
    main()
