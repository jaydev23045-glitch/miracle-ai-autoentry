# Bank Statement injection handlers and contra brand safety checks

def is_contra_brand_swap(narration: str, own_bank_ledger: str) -> bool:
    """
    Checks if a transaction narration contains the statement's own bank ledger
    or bank brands that should be excluded from turning a payment/receipt into a Contra entry.
    """
    own_bank_upper = own_bank_ledger.upper().strip()
    narr_upper = narration.upper().strip()
    
    # Strip common brand name from the target bank statement ledger name to get core brand
    own_brand = own_bank_upper
    for suffix in ["BANK", "MUMBAI", "DELHI", "AHMEDABAD", "PUNE", "BRANCH"]:
        own_brand = own_brand.replace(suffix, "").strip()
        
    # Exclude matches if they are part of UPI handles (like @okhdfcbank or @icici)
    if own_brand and own_brand in narr_upper:
        # Check if own brand appears strictly as a UPI handle VPA prefix
        import re
        vpa_handles = re.findall(r'@[A-Z0-9\-\.]+', narr_upper)
        for handle in vpa_handles:
            if own_brand in handle:
                # The bank brand is inside a UPI handle, so this is NOT a contra entry to our own bank account!
                return True
                
    return False
