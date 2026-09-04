import os, sys

def test_grid_filter_resolution():
    print("==================================================")
    print("  TESTING GRID FILTER & DROPDOWN ACCURACY        ")
    print("==================================================")

    sample_rows = [
        {"mapped_ledger": "PAYTM", "group_hint": "Indirect Expenses", "transaction_type": "Payment", "amount": 1200},
        {"mapped_ledger": "", "party_name": "JIGNESH KHUNT", "group_hint": "Suspense Account", "transaction_type": "Receipt", "amount": 5000},
        {"mapped_ledger": "SUSPENSE ACCOUNT", "party_name": "BHARAT KHUT", "transaction_type": "Payment", "amount": 9000},
        {"mapped_ledger": "ICICI LOMBARD", "group_hint": "Direct Expenses (Freight / Addons)", "transaction_type": "Payment", "amount": 6930.26},
    ]

    def get_row_info(r):
        m_ledger = (r.get("mapped_ledger") or "").strip()
        is_suspense = not m_ledger or m_ledger.upper() in ("SUSPENSE ACCOUNT", "SUSPENSE")
        
        acc = "Suspense Account" if is_suspense else m_ledger
        grp = (r.get("group_hint") or ("Suspense Account" if is_suspense else "Indirect Expenses")).strip()
        return grp, acc

    groups = {}
    accounts = {}
    for row in sample_rows:
        g, a = get_row_info(row)
        groups[g] = groups.get(g, 0) + 1
        accounts[a] = accounts.get(a, 0) + 1

    print("Calculated Group Counts:", groups)
    print("Calculated Account Counts:", accounts)

    assert groups.get("Indirect Expenses") == 1
    assert groups.get("Suspense Account") == 2
    assert groups.get("Direct Expenses (Freight / Addons)") == 1
    assert accounts.get("Suspense Account") == 2
    assert accounts.get("PAYTM") == 1
    assert accounts.get("ICICI LOMBARD") == 1

    print("--> ✅ PASS: All group and account counts resolved 100% accurately!")

if __name__ == "__main__":
    test_grid_filter_resolution()
