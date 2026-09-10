import os
import difflib
from typing import List, Dict, Any

def validate_vouchers_pre_push(
    module: str,
    vouchers: List[Dict[str, Any]],
    client_path: str,
    year_folder: str,
    ledgers: List[Dict[str, Any]],
    pre_computed_bounds: dict = None
) -> List[str]:
    """
    Validates vouchers before pushing to DBF using empirical Financial Year bounds.
    Returns a list of error message strings. If empty, validation passed.
    """
    from core.config import resolve_year_folder_for_date, resolve_year_folder_for_date_fast

    errors = []
    
    # Build ledger lookups (pre-computed ONCE for entire batch - BN-8)
    ledger_names = {l['name'].strip().upper() for l in ledgers if isinstance(l, dict) and l.get('name')}
    ledger_codes = {l['code'].strip().upper() for l in ledgers if isinstance(l, dict) and l.get('code')}
    real_ledger_names_list = [l['name'].strip() for l in ledgers if isinstance(l, dict) and l.get('name')]
    
    for idx, v in enumerate(vouchers):
        row_label = f"Row #{idx + 1}"
        
        # 1. Date & Empirical FY Bounds Check
        v_date = v.get('date') or v.get('Date') or v.get('voucher_date') or v.get('BillDate') or v.get('txn_date')
        if not v_date:
            errors.append(f"{row_label}: Missing date.")
        else:
            v_date_str = str(v_date).strip()[:10]
            is_valid_iso = (
                len(v_date_str) == 10 and 
                v_date_str.count("-") == 2 and 
                v_date_str[:4].isdigit() and 
                int(v_date_str[:4]) >= 1900
            )
            if not is_valid_iso:
                try:
                    from dateutil import parser as _dparser
                    dt_parsed = _dparser.parse(str(v_date), dayfirst=True)
                    v_date_str = dt_parsed.strftime("%Y-%m-%d")
                    v['date'] = v_date_str
                    for d_key in ('Date', 'voucher_date', 'BillDate', 'txn_date'):
                        if d_key in v:
                            v[d_key] = v_date_str
                except Exception:
                    errors.append(f"{row_label}: Invalid date format '{v_date_str}' (expected YYYY-MM-DD).")
                    continue
            else:
                v['date'] = v_date_str
                
            if pre_computed_bounds is not None:
                res = resolve_year_folder_for_date_fast(pre_computed_bounds, v_date_str, client_path)
            else:
                res = resolve_year_folder_for_date(client_path, v_date_str)
                
            resolved_folder = res["resolved_folder"]
            folder_exists = res["folder_exists"]
            fy_start = res["fy_start"]
            fy_end = res["fy_end"]
            
            if not folder_exists:
                errors.append(
                    f"{row_label}: Date '{v_date_str}' belongs to Financial Year folder '{resolved_folder}' "
                    f"({fy_start} to {fy_end}), but directory '{resolved_folder}' does not exist in client folder "
                    f"'{os.path.basename(client_path)}'. Please open Miracle Accounting Software and create year {resolved_folder} first."
                )
            elif not (fy_start <= v_date_str <= fy_end):
                errors.append(
                    f"{row_label}: Date '{v_date_str}' is outside Financial Year bounds ({fy_start} to {fy_end} for {resolved_folder})."
                )
                    
        # 2. Amount & Math check
        if module in ["Sales", "Purchases"]:
            bill_no = v.get('billNo') or v.get('bill_no')
            if not bill_no or str(bill_no).strip().upper() in ["NONE", "NAN", ""]:
                errors.append(f"{row_label}: Missing invoice number.")
                
            party_name = (v.get('party') or v.get('party_name') or "").strip()
            if not party_name or party_name.upper().startswith("UNKNOWN_PARTY:"):
                errors.append(f"{row_label}: Unmapped/Unknown party name '{party_name}'.")
            elif party_name.upper() not in ledger_names and party_name.upper() not in ledger_codes:
                is_auto_b2c = v.get('isB2C')
                is_auto_b2b = v.get('autoCreateB2B')
                if not (is_auto_b2c or is_auto_b2b):
                    # Auto-heal missing ledgers
                    gstin = v.get('gstin', '')
                    if gstin and len(str(gstin)) >= 10:
                        v['autoCreateB2B'] = True
                    else:
                        v['isB2C'] = True

            # Math check
            def to_float(val):
                if val is None:
                    return 0.0
                try:
                    s = str(val).replace("₹", "").replace(",", "").strip()
                    return float(s) if s else 0.0
                except Exception:
                    return 0.0
            
            taxable = to_float(v.get('taxable'))
            cgst = to_float(v.get('cgst'))
            sgst = to_float(v.get('sgst'))
            igst = to_float(v.get('igst'))
            gst = to_float(v.get('gst'))
            discount = to_float(v.get('discount'))
            freight = to_float(v.get('freight'))
            tcs = to_float(v.get('tcs'))
            tds = to_float(v.get('tds'))
            total = to_float(v.get('total'))
            
            expected_gst = cgst + sgst + igst
            if expected_gst > 0 and gst > 0 and abs(expected_gst - gst) > 1.0:
                # Auto-heal: trust the sum of components
                v['gst'] = expected_gst
                gst = expected_gst
                
            actual_gst_for_math = max(expected_gst, gst)
            expected_total = round(taxable + actual_gst_for_math + freight + tcs - discount - tds, 2)
            
            if abs(expected_total - total) > 5.0:
                diff = round(total - expected_total, 2)
                # Auto-heal logic
                if actual_gst_for_math == 0.0 and diff > 0 and abs((taxable + diff) - total) <= 2.0:
                    # Missing GST case
                    v['gst'] = diff
                elif diff < 0 and discount == 0.0:
                    # Overcharged expected, maybe there's a discount
                    v['discount'] = abs(diff)
                elif diff > 0 and freight == 0.0:
                    discount_proximity = abs(diff - discount)
                    if discount > 0 and discount_proximity < (discount * 0.05 + 1.0):
                        print(f"  ⚠️ [Ghost Freight Guard] Diff {diff:.2f} matches discount {discount:.2f}. Discount likely already in taxable. Skipping auto-freight.")
                    elif diff > 5.0:
                        v['freight'] = diff
                else:
                    errors.append(f"{row_label} (Bill {bill_no}): Mathematically unbalanced invoice. Expected Total: {expected_total:.2f}, Provided Total: {total:.2f} (diff: {abs(expected_total - total):.2f}).")

        elif module in ["Bank Statements", "Cash Entries"]:
            party_name = (v.get('party_name') or v.get('mapped_ledger') or v.get('party') or "").strip()
            
            # Hard fail: completely empty or unknown string
            if not party_name or party_name.upper().startswith("UNKNOWN_PARTY:"):
                errors.append(f"{row_label}: Transaction has an empty party or ledger name.")
            
            elif party_name.upper() not in ledger_names and party_name.upper() not in ledger_codes:
                # If explicit Suspense Account, auto-map to Suspense ledger in Miracle
                if party_name.upper() in ("SUSPENSE ACCOUNT", "SUSPENSE A/C"):
                    suspense_match = next((l['name'] for l in ledgers if 'SUSPENSE' in l['name'].upper()), 'Suspense Account')
                    v['mapped_ledger'] = suspense_match
                    v['party_name']    = suspense_match
                    v['party']         = suspense_match
                    v['group_hint']    = 'Suspense Account'
                    print(f"  ⚖️ [Accounting Foundation Rule] Suspense entry retained as '{suspense_match}'")
                else:
                    # Strategy 1: Fuzzy match against existing Miracle ledgers
                    close = difflib.get_close_matches(party_name, real_ledger_names_list, n=1, cutoff=0.70)
                    if close:
                        healed = close[0]
                        print(f"  🔗 [Accounting Heal] '{party_name}' → '{healed}' (fuzzy ledger match)")
                        v['mapped_ledger'] = healed
                        v['party_name']    = healed
                        v['party']         = healed
                    else:
                        # Strategy 2: Determine appropriate accounting group hint
                        tx_type = str(v.get('transaction_type', 'Payment')).strip().capitalize()
                        is_receipt = (tx_type == 'Receipt')
                        
                        GENERIC_EXPENSES = {
                            'TELEPHONE EXP', 'TELEPHONE EXPENSE', 'MOBILE EXP', 'ELECTRICITY EXP', 'ELECTRICITY EXPENSE',
                            'WATER EXPENSE', 'WATER EXP', 'GAS EXP', 'GAS EXPENSE', 'CUTTING EQUIPMENTS', 'CUTTING TOOLS EXP',
                            'REPAIR & MAINTENANCE', 'REPAIRS EXP', 'PRINTING & STATIONERY', 'STATIONERY EXP',
                            'ADVERTISEMENT EXP', 'ADVERTISING EXP', 'STAFF WELFARE', 'FOOD EXP', 'ENTERTAINMENT EXP',
                            'GST PAYABLE', 'TDS PAYABLE', 'INSURANCE EXP', 'INSURANCE EXPENSE', 'FUEL EXPENSE', 'PETROL-DIESEL EXPENSE',
                            'BANK CHARGES', 'BANK CHARGE', 'BANK FEE', 'BANK FEES', 'BANK COMM', 'BANK COMMISSION',
                            'BANK INTEREST', 'SMS CHARGES', 'SMS CHGS', 'SERVICE CHARGES', 'PROCESSING FEE',
                            'PROCESSING FEES', 'MDR CHARGES', 'MDR RECOVERY', 'RUPAY MDR', 'CARD CHARGES',
                            'POS CHARGES', 'MIN BAL', 'MINIMUM BALANCE', 'CHQ RET', 'CHEQUE RETURN', 'CHQ DEP RET',
                            'DEBIT CARD FEE', 'ANNUAL FEE', 'FOREX CHARGES', 'GST ON BANK', 'PENALTY', 'INTEREST PAID'
                        }
                        
                        GENERIC_PARTY_DESCRIPTORS = {
                            'SUNDRY DEBTORS', 'SUNDRY CREDITORS', 'INDIRECT EXPENSES', 'DIRECT EXPENSES',
                            'INDIRECT INCOME', 'DIRECT INCOME', 'SALES ACCOUNTS', 'PURCHASE ACCOUNTS',
                            'CHEQUE DEPOSIT', 'CHQ DEP', 'CHQ DEPOSIT', 'CHEQUE CLEARING', 'CLEARING DEPOSIT',
                            'CLEARING', 'CLG DEPOSIT', 'CHQ RETURN', 'CHEQUE RETURN', 'CHQ RET', 'CHEQUE BOUNCE',
                            'INWARD CHEQUE', 'OUTWARD CHEQUE', 'NEFT DEPOSIT', 'RTGS DEPOSIT', 'IMPS DEPOSIT'
                        }
                        p_up = party_name.upper().strip()
                        is_generic_descriptor = p_up in GENERIC_PARTY_DESCRIPTORS or any(p_up.startswith(g) for g in ['CHEQUE DEPOSIT', 'CHQ DEP', 'CLEARING', 'CHQ RET', 'CHEQUE RET'])

                        COMMERCIAL_ENTITY_KWS = {
                            'INDUSTRIES', 'TRADERS', 'ENTERPRISES', 'ENTERPRISE', 'PVT', 'PRIVATE',
                            'LIMITED', 'LTD', 'LLP', 'DISTRIBUTORS', 'DISTRIBUTOR', 'PRODUCTS', 'PRODUCT',
                            'AGENCIES', 'AGENCY', 'SUPPLIERS', 'SUPPLIER', 'MART', 'MANUFACTURING',
                            'PHARMA', 'MILLS', 'CORP', 'CORPORATION', 'SOLUTIONS', 'TECHNOLOGIES',
                            'SERVICES', 'INFRA', 'EXPORTS', 'IMPORTS', 'HARDWARE', 'MOTORS', 'AUTO',
                            'STEEL', 'CHEMICALS', 'TEXTILES', 'TRADING', 'COMMERCE', 'LOGISTICS'
                        }
                        is_commercial_entity = any(w in p_up.split() for w in COMMERCIAL_ENTITY_KWS)

                        is_expense_keyword = not is_commercial_entity and ((p_up in GENERIC_EXPENSES) or any(
                            kw in p_up for kw in [
                                'EXPENSE', 'EXP', 'CHARGES', 'CHGS', 'FEE', 'FEES', 'RENT', 'SALARY',
                                'MAINTENANCE', 'REPAIR', 'TAX', 'INTEREST', 'COMMISSION', 'INSURANCE',
                                'PETROL', 'DIESEL', 'FUEL', 'STATIONERY', 'WELFARE', 'ADVERTISEMENT'
                            ]
                        ))

                        if is_expense_keyword:
                            v['group_hint'] = 'Indirect Expenses'
                            v['mapped_ledger'] = party_name if party_name else 'Bank Charges'
                            v['party_name']    = party_name if party_name else 'Bank Charges'
                            v['party']         = party_name if party_name else 'Bank Charges'
                            print(f"  ⚖️ [Accounting Foundation Rule] Expense '{party_name}' classified under Indirect Expenses")
                        elif is_generic_descriptor or not party_name or p_up in ('SUSPENSE ACCOUNT', 'SUSPENSE A/C'):
                            v['group_hint']       = 'Suspense Account'
                            v['mapped_ledger']    = 'Suspense Account'
                            v['party_name']       = 'Suspense Account'
                            v['party']            = 'Suspense Account'
                            v['confidence_score'] = 40
                            print(f"  ⚖️ [Accounting Foundation Rule] Generic Descriptor/Group '{party_name}' routed to Suspense Account")
                        else:
                            group = 'Sundry Debtors' if is_receipt else 'Sundry Creditors'
                            v['group_hint'] = group
                            v['mapped_ledger'] = party_name
                            v['party_name']    = party_name
                            v['party']         = party_name
                            print(f"  ⚖️ [Accounting Foundation Rule] Party '{party_name}' classified under {group}")

            # ── CRITICAL DOUBLE-ENTRY ACCOUNTING NATURE GUARD ────────────────────────
            tx_type = str(v.get('transaction_type', 'Payment')).strip().capitalize()
            gh = str(v.get('group_hint') or '').upper()
            has_party = bool(party_name and party_name.upper() not in ('BANK CHARGES', 'CASH', 'CASH ACCOUNT', 'UNKNOWN'))

            if tx_type == 'Payment' and any(bad in gh for bad in ['SALES ACCOUNTS', 'DIRECT INCOME', 'INDIRECT INCOME', 'TRADING ACCOUNT', 'SUNDRY DEBTORS']):
                healed_group = 'Sundry Creditors' if has_party else ('Indirect Expenses' if 'INDIRECT' in gh else 'Direct Expenses')
                print(f"  ⚖️ [Auto-Heal Accounting Nature] {row_label}: Converted Payment from '{v.get('group_hint')}' to '{healed_group}'")
                v['group_hint'] = healed_group
            elif tx_type == 'Receipt' and any(bad in gh for bad in ['PURCHASE ACCOUNTS', 'DIRECT EXPENSES', 'INDIRECT EXPENSES', 'SUNDRY CREDITORS']):
                healed_group = 'Sundry Debtors' if has_party else ('Indirect Income' if 'INDIRECT' in gh else 'Direct Income')
                print(f"  ⚖️ [Auto-Heal Accounting Nature] {row_label}: Converted Receipt from '{v.get('group_hint')}' to '{healed_group}'")
                v['group_hint'] = healed_group

            amount = v.get('amount')
            try:
                s = str(amount).replace("₹", "").replace(",", "").strip()
                amt_val = float(s) if s else 0.0
                if amt_val <= 0:
                    errors.append(f"{row_label}: Transaction amount must be positive (got {amount}).")
            except Exception:
                errors.append(f"{row_label}: Invalid amount value '{amount}'.")

    return errors
