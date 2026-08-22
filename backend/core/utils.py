import re

def parse_currency(val) -> float:
    """
    Unified math-safe currency parsing engine.
    Sanitizes commas, currency symbols, and parenthesized negative numbers,
    and returns a clean float. Default fallback is 0.0.
    """
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
        
    val_str = str(val).strip()
    if not val_str:
        return 0.0
        
    # Check for parenthesized negative number like (500.00)
    is_negative = False
    if val_str.startswith('(') and val_str.endswith(')'):
        is_negative = True
        val_str = val_str[1:-1].strip()
        
    # Remove currency signs and commas
    val_str = val_str.replace(',', '').replace('₹', '').replace('$', '').strip()
    
    try:
        res = float(val_str)
        return -res if is_negative else res
    except ValueError:
        # Fallback to regex extraction of the first float/int found in the string
        match = re.search(r'[-+]?\d*\.\d+|\d+', val_str)
        if match:
            try:
                res = float(match.group())
                return -res if is_negative else res
            except ValueError:
                pass
        return 0.0
