# Sales injection handlers and compliance rules

def validate_sales_voucher(voucher: dict) -> list:
    """
    Performs Sales-specific pre-injection validations.
    Returns a list of warning/error strings.
    """
    warnings = []
    # Verify GST totals
    cgst = float(voucher.get("cgst", 0.0))
    sgst = float(voucher.get("sgst", 0.0))
    igst = float(voucher.get("igst", 0.0))
    taxable = float(voucher.get("taxable_amount", 0.0))
    
    if cgst > 0.0 and sgst > 0.0 and igst > 0.0:
        warnings.append("Sales bill cannot have both local tax (CGST/SGST) and interstate tax (IGST).")
        
    return warnings
