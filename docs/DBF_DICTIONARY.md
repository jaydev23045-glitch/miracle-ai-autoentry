# Miracle DBF Dictionary & Rosetta Stone

This document serves as the absolute truth for interpreting Miracle's obscure FoxPro column names. Since Miracle is undocumented, this dictionary is our only way to safely manipulate records.

## Voucher Types (`FIELD98`)
| Value | Meaning |
|-------|---------|
| `SS`  | Sales |
| `PP`  | Purchases |
| `SR`  | Sales Return |
| `PR`  | Purchase Return |
| `BR`  | Bank Receipt |
| `BP`  | Bank Payment |

---

## 1. RKACCT02.DBF (Transaction Detail Lines)
This table breaks down each line item in a voucher (e.g. Products bought/sold).
- `FIELD01`: The 12-character Voucher ID (e.g. `SSWGOPG8X0KX`). Used to link to `RKACCT41` and `RKACCT52`.
- `FIELD03`: Product Code (Links to `RKACCM21`).
- `FIELD04`: **Voucher Type Flag**. MUST BE `'I'` for Sales, and `'N'` for Purchases.
- `FIELD05`: **Voucher Sub-type Flag**. MUST BE `'D'` for Sales, and `'C'` for Purchases.
- `FIELD06`: Quantity.
- `FIELD07`: Rate per unit.
- `FIELD08`: Gross Amount (Qty * Rate).
- `FIELD09`: Discount Amount.
- `FIELD12`: Net Amount.

## 2. RKACCT52.DBF (GST & Tax Breakdown)
This is the most dangerous table. If you write the wrong flags here, the entry turns **red** in Miracle and vanishes from the GST returns book.
- `T52F01`: The 12-character Voucher ID.
- `T52F04`: Entry status. `'N'` (Normal).
- `T52F05`: **Tax Linkage Flag**. MUST BE `'T'` for Sales (Tax Invoice), and `'C'` for Purchases.
- `T52F17`: Taxable Value (Amount).
- `T52F18`: IGST Amount.
- `T52F19`: CGST Amount.
- `T52F20`: SGST Amount.
- `T52F22`: **Debit/Credit Flag**. MUST BE `'D'` for Sales, and `'C'` for Purchases.
- `T52F28`: **Tax Book Flag**. MUST BE `'T'` for Sales, and `'C'` for Purchases.
- `T52F29`: Flow Direction. Always `'O'`.
- `T52F30`: **GST Register Link**. `'3'` = Sales Register (GSTR-1), `'4'` = Purchase Register (GSTR-2).

## 3. RKACCM01.DBF & RKACCM02.DBF (Party Ledgers)
- `FIELD01`: Ledger Code (e.g. `AYECD7E8`).
- `FIELD02`: Ledger Name.
- `FIELD03`: Group Code (e.g. `G0000013` for Sundry Creditors).
- `FIELD43`: GSTIN.
- `M01F14`: Tax Class (e.g. `'B2B'` or `'B2C'`).

## 4. RKACCT41.DBF (Voucher Header)
- `FIELD01`: Voucher ID.
- `FIELD04`: Party Ledger Code.
- `FIELD05`: Sales/Purchase Account Ledger Code.
- `FIELD06`: Total Bill Amount.
- `FIELD10`: External Reference Number (e.g. Supplier Bill No).
- `FIELD21`: `'T'` (Tax Invoice).

---
*If you find a new undocumented quirk, add it to this file immediately!*
