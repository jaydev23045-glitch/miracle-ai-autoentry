"""
Tax Compliance & Advanced Accounting Engine (Points 31-55)
Implements statutory GSTR-2B matching, Section 194Q TDS, Landed Cost Allocation, E-Invoicing IRN QR decoding, and 3-Way PO verification for Miracle Auto-Entry Platform.
"""

import re
import datetime
from typing import List, Dict, Any, Optional

# Section 194Q Threshold: ₹50,000,000 (50 Lakhs)
SECTION_194Q_THRESHOLD = 5000000.0
DEFAULT_TDS_RATE = 0.001  # 0.1%
PAN_MISSING_TDS_RATE = 0.05  # 5%

def calculate_section_194q_tds(
    vendor_ytd_purchases: float,
    current_invoice_taxable: float,
    vendor_pan: str = "",
    is_206ab_nonfiler: bool = False
) -> Dict[str, Any]:
    """
    Calculates Section 194Q TDS for purchase of goods exceeding ₹50 Lakhs in a financial year.
    TDS is deducted @ 0.1% on amount exceeding ₹50 Lakhs (or 5% if PAN is missing / non-filer).
    """
    previous_ytd = max(0.0, float(vendor_ytd_purchases))
    current_taxable = max(0.0, float(current_invoice_taxable))
    new_ytd = previous_ytd + current_taxable

    if new_ytd <= SECTION_194Q_THRESHOLD:
        return {
            "applicable": False,
            "threshold_exceeded": False,
            "taxable_subject_to_tds": 0.0,
            "tds_rate_pct": 0.0,
            "tds_amount": 0.0,
            "reason": f"YTD purchases (₹{new_ytd:,.2f}) are within ₹50 Lakh threshold."
        }

    # Determine eligible portion subject to TDS
    if previous_ytd >= SECTION_194Q_THRESHOLD:
        taxable_subject_to_tds = current_taxable
    else:
        taxable_subject_to_tds = new_ytd - SECTION_194Q_THRESHOLD

    # Rate determination (0.1% standard, 5.0% if PAN missing or 206AB non-filer)
    has_valid_pan = bool(vendor_pan and len(vendor_pan.strip()) == 10 and vendor_pan[3].upper() in "CPFHTA")
    if not has_valid_pan or is_206ab_nonfiler:
        rate = PAN_MISSING_TDS_RATE
        rate_str = "5.0% (Higher rate: Missing PAN or 206AB non-filer)"
    else:
        rate = DEFAULT_TDS_RATE
        rate_str = "0.1% (Standard Sec 194Q rate)"

    tds_amount = round(taxable_subject_to_tds * rate, 2)

    return {
        "applicable": True,
        "threshold_exceeded": True,
        "previous_ytd": previous_ytd,
        "new_ytd": new_ytd,
        "taxable_subject_to_tds": round(taxable_subject_to_tds, 2),
        "tds_rate_pct": rate * 100.0,
        "tds_rate_description": rate_str,
        "tds_amount": tds_amount,
        "reason": f"Sec 194Q TDS deducted on ₹{taxable_subject_to_tds:,.2f} @ {rate*100:.1f}%."
    }

def classify_gstr2b_match(extracted_voucher: Dict[str, Any], gstr2b_entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Reconciles an extracted purchase voucher against monthly GSTR-2B entries downloaded from GSTN portal.
    """
    v_gstin = str(extracted_voucher.get("party_gstin", "")).strip().upper()
    v_bill_no = str(extracted_voucher.get("bill_no", "")).strip().upper()
    v_total = float(extracted_voucher.get("total", 0.0))
    v_gst = float(extracted_voucher.get("cgst", 0.0)) + float(extracted_voucher.get("sgst", 0.0)) + float(extracted_voucher.get("igst", 0.0))

    if not v_gstin:
        return {
            "status": "Unregistered / Cash Purchase",
            "matched": False,
            "itc_eligible": True,
            "flag": "Unregistered Supplier"
        }

    # Search for matching invoice in GSTR-2B entries
    matched_entry = None
    for entry in gstr2b_entries:
        b_gstin = str(entry.get("supplier_gstin", "")).strip().upper()
        b_inv = str(entry.get("invoice_no", "")).strip().upper()
        
        if b_gstin == v_gstin and (b_inv == v_bill_no or v_bill_no in b_inv or b_inv in v_bill_no):
            matched_entry = entry
            break

    if not matched_entry:
        return {
            "status": "Missing in GSTR-2B",
            "matched": False,
            "itc_eligible": False,
            "flag": "ITC Deferred: Bill not uploaded by supplier in GSTR-1"
        }

    b_gst = float(entry.get("cgst", 0.0)) + float(entry.get("sgst", 0.0)) + float(entry.get("igst", 0.0))
    gst_diff = abs(v_gst - b_gst)

    if gst_diff <= 1.0:
        return {
            "status": "2B Matched",
            "matched": True,
            "itc_eligible": True,
            "flag": "Matched with GSTR-2B",
            "gstr2b_entry": matched_entry
        }
    else:
        return {
            "status": "Tax Mismatch",
            "matched": True,
            "itc_eligible": False,
            "flag": f"Tax difference of ₹{gst_diff:.2f} compared to GSTR-2B",
            "gstr2b_entry": matched_entry
        }

def allocate_landed_costs(items: List[Dict[str, Any]], freight_charges: float = 0.0, handling_charges: float = 0.0) -> List[Dict[str, Any]]:
    """
    Proportionately allocates freight and handling charges into line item cost basis (Landed Cost).
    """
    total_taxable = sum(float(i.get("taxable", 0.0)) for i in items)
    total_addon = max(0.0, float(freight_charges)) + max(0.0, float(handling_charges))

    if total_taxable <= 0.0 or total_addon <= 0.0:
        return items

    updated_items = []
    allocated_sum = 0.0

    for idx, item in enumerate(items):
        item_copy = dict(item)
        item_taxable = float(item_copy.get("taxable", 0.0))
        
        if idx == len(items) - 1:
            item_addon = round(total_addon - allocated_sum, 2)
        else:
            item_addon = round((item_taxable / total_taxable) * total_addon, 2)
            allocated_sum += item_addon

        qty = max(1.0, float(item_copy.get("qty", 1.0)))
        base_rate = float(item_copy.get("rate", 0.0))
        landed_rate = round(base_rate + (item_addon / qty), 2)

        item_copy["allocated_freight"] = item_addon
        item_copy["landed_unit_rate"] = landed_rate
        item_copy["landed_cost_total"] = round(item_taxable + item_addon, 2)
        updated_items.append(item_copy)

    return updated_items

def parse_e_invoicing_irn_qr(qr_text: str) -> Dict[str, Any]:
    """
    Decodes B2B E-Invoicing QR codes or IRN text strings to extract statutory details.
    """
    irn_match = re.search(r'\b([A-Fa-f0-9]{64})\b', str(qr_text))
    gstin_match = re.search(r'\b(\d{2}[A-Z]{5}\d{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})\b', str(qr_text))
    
    return {
        "valid_irn": bool(irn_match),
        "irn_code": irn_match.group(1) if irn_match else "",
        "detected_gstin": gstin_match.group(1) if gstin_match else "",
        "e_invoicing_verified": bool(irn_match and gstin_match)
    }

def verify_3way_po_match(invoice_data: Dict[str, Any], po_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Verifies 3-Way Match between Purchase Order (PO) and Purchase Invoice.
    Checks quantity inflation and price inflation.
    """
    po_no = po_data.get("po_no", "")
    inv_no = invoice_data.get("bill_no", "")
    
    inv_items = invoice_data.get("items", [])
    po_items = po_data.get("items", [])

    mismatches = []
    for inv_item in inv_items:
        i_name = str(inv_item.get("name", "")).strip().lower()
        i_qty = float(inv_item.get("qty", 0.0))
        i_rate = float(inv_item.get("rate", 0.0))

        # Search in PO items
        po_match = None
        for p in po_items:
            p_name = str(p.get("name", "")).strip().lower()
            if p_name == i_name or i_name in p_name or p_name in i_name:
                po_match = p
                break

        if not po_match:
            mismatches.append(f"Item '{inv_item.get('name')}' is missing from Purchase Order {po_no}")
        else:
            p_qty = float(po_match.get("qty", 0.0))
            p_rate = float(po_match.get("rate", 0.0))

            if i_qty > p_qty:
                mismatches.append(f"Qty Inflation for '{inv_item.get('name')}': Invoiced {i_qty} > PO Qty {p_qty}")
            if i_rate > p_rate:
                mismatches.append(f"Price Inflation for '{inv_item.get('name')}': Invoiced ₹{i_rate} > PO Price ₹{p_rate}")

    return {
        "matched": len(mismatches) == 0,
        "po_no": po_no,
        "inv_no": inv_no,
        "mismatch_count": len(mismatches),
        "discrepancies": mismatches
    }
