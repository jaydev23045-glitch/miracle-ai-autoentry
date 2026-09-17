---
name: gst_tds_tax_engine
description: Technical instructions and calculation engine rules for GST tax splits (CGST, SGST, IGST), TDS 194Q/194C deductions, RCM, single discount header posting, and round-off auto-balancing in Miracle ERP.
---

# GST Tax & TDS Calculation Engine Protocol

> [!IMPORTANT]
> **FINANCIAL PRECISION DIRECTIVE:**
> Tax calculations in Miracle AI Auto-Entry **MUST NEVER** use standard binary floating-point floats (`float`). Always use Python's `decimal.Decimal` module with explicit `ROUND_HALF_UP` rounding to prevent fraction-of-a-paisa discrepancies in GST returns.

---

## 1. Relevant Smart Rules (Rules 7, 19, 35)

- **Rule 7 — Double-Entry Math Balance**: Every voucher push MUST mathematically balance total Debits and total Credits to exact 0.00.
- **Rule 19 — Single Discount Header Posting**: Sales invoice discounts post strictly to header `EDVAS00095` (`DISCOUNT A/C`) while item discounts are set to `0.0`, preventing double-counting.
- **Rule 35 — Tax-Aware Product Assignment & True GST Rate Mismatch Protocol**: Product GST validation MUST compare true numerical tax rates (`mappedProduct.gst_pct`) against `row.gst_pct`. It MUST NEVER flag `GST DBF Mismatch` if tax rates match. Default product overrides MUST be tax-aware and ONLY apply to invoice items sharing the default product's exact GST percentage.

---

## 2. GST Tax Architecture & Intra vs Inter-State Logic

GST tax split depends on comparing the Client's State Code against the Counterparty's GSTIN State Code (first 2 digits of GSTIN):

$$\text{State Code} = \text{GSTIN}[0:2]$$

### Tax Split Rules:
1. **Intra-State (`Client State Code == Counterparty State Code`)**:
   - Tax is split equally into **CGST** (50%) and **SGST** (50%).
   - Example: 18% GST on ₹10,000 -> CGST 9% (₹900) + SGST 9% (₹900). Total Invoice: ₹11,800.
2. **Inter-State (`Client State Code != Counterparty State Code`)**:
   - Total tax is assigned to **IGST** (100%).
   - Example: 18% GST on ₹10,000 -> IGST 18% (₹1,800). Total Invoice: ₹11,800.

---

## 3. Standard GST Rates & Tax Ledger Mapping in Miracle DBF

Miracle ERP uses fixed internal codes for auto-generated tax lines in `RKACCT01.DBF`:

| Tax Type | Rate | Miracle DBF Tax Ledger Code | Account Name |
|---|---|---|---|
| **CGST 2.5%** | 2.5% | `AGST0005` | Input / Output CGST 2.5% |
| **SGST 2.5%** | 2.5% | `AGST0006` | Input / Output SGST 2.5% |
| **CGST 6.0%** | 6.0% | `AGST0007` | Input / Output CGST 6.0% |
| **SGST 6.0%** | 6.0% | `AGST0008` | Input / Output SGST 6.0% |
| **CGST 9.0%** | 9.0% | `AGST0009` | Input / Output CGST 9.0% |
| **SGST 9.0%** | 9.0% | `AGST0010` | Input / Output SGST 9.0% |
| **IGST 18.0%**| 18.0% | `AGST0018` | Input / Output IGST 18.0% |
| **Round-Off** | Variable | `AVAUTO99` | Auto Round-Off Account |

---

## 4. TDS 194Q & 194C Calculation Protocol

### TDS Section 194Q (Deduction on Payment for Purchase of Goods)
- **Applicability**: Buyer's turnover > ₹10 Crore in preceding FY AND cumulative seller purchase > **₹50 Lakhs** in current FY.
- **Deduction Rate**: **0.1%** on amount exceeding ₹50 Lakhs (or 5% if PAN is un-furnished).
- **Voucher Entry**: Debit Party Ledger / Credit TDS Payable Account (`TDS 194Q Payable`).

### TDS Section 194C (Contractors / Sub-contractors)
- **Applicability**: Single payment > ₹30,000 or aggregate annual payments > ₹1,000,000.
- **Deduction Rate**: **1%** for Individuals/HUF, **2%** for Companies/Firms.

---

## 5. Invoice Round-Off Auto-Balancing Algorithm

To ensure `Sum(Debit Lines) == Sum(Credit Lines)` exact double-entry parity:

```python
from decimal import Decimal, ROUND_HALF_UP

def calculate_voucher_roundoff(taxable: Decimal, cgst: Decimal, sgst: Decimal, igst: Decimal) -> tuple[Decimal, Decimal]:
    """Calculates rounded invoice total and roundoff differential."""
    raw_total = taxable + cgst + sgst + igst
    rounded_total = raw_total.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    roundoff_diff = rounded_total - raw_total
    return rounded_total, roundoff_diff
```

- If `roundoff_diff != Decimal("0.00")`, create an extra detail line in `RKACCT01.DBF` mapped to `AVAUTO99`.
