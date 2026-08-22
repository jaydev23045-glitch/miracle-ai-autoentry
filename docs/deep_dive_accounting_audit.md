# 🔬 Deep Dive Accounting Audit Report
## Miracle Auto Entry — All Modules Analysis

---

## How I Analyzed This

I compared **actual native records from your Miracle database** (`RKACCT41.DBF` + `RKACCT01.DBF`) against what our code writes — field by field, for every voucher type.

---

## Native Miracle Record Structure (Ground Truth)

### T41 Header — Native Values

| Field | SS (Sale) | PP (Purchase) | BR (Bank Rcpt) | BP (Bank Pay) | CR (Cash Rcpt) | CP (Cash Pay) |
|-------|-----------|---------------|----------------|---------------|----------------|---------------|
| FIELD98/99 | `SS` | `PP` | `BR` | `BP` | `CR` | `CP` |
| FIELD03 | `6` | `5` | `2` | `2` | `2` | `2` |
| FIELD14 | `N` | `A` | `N` | `N` | `N` | `N` |
| FIELD16 | `D` | `D` | `R` | `P` | `R` | `P` |
| FIELD20 | `3` (lines) | `2` (lines) | blank | blank | blank | blank |
| FIELD21 | `T` | `T` | `O` | `O` | `O` | `O` |
| FIELD74 | `SP` | `SP` | `CB` | `CB` | `CB` | `CB` |
| T41F96 | `G` | `G` | `N` | `N` | `N` | `N` |
| FIELD10 | **blank** | `M06AI26...` | `IMPS` | blank | blank | blank |

### T01 Line Items — Native Values

| Type | Line | FIELD03 | FIELD21 | FIELD20 | FIELD06 |
|------|------|---------|---------|---------|---------|
| SS | 1 Party (CS=Cash) | `ACASHACT` | `CS` | `N` | `D` |
| SS | 2 Sales A/c | `AGST0001` | `TS` | `N` | `C` |
| SS | 3 Service/Product | `ABMCYDTF` | `TS` | `N` | `C` |
| SS | 4 Round-off | `AVAUTO99` | `PT` | `N` | `D` |
| SS | 5 CGST | `AGST0008` | `TX` | `N` | `C` |
| SS | 6 SGST | `AGST0009` | `TX` | `N` | `C` |
| PP | 1 Party | `ABN44ADC` | `PR` | `N` | `C` |
| PP | 2 Purchase A/c | `AGST0004` | `TP` | `N` | `D` |
| BR | 1 Bank A/c | `AB14D625` | `BK` | `N` | `D` |
| BR | 2 Party | `ABHMUOXP` | **`PR`** | `N` | `C` |
| BP | 1 Bank A/c | `AB14D625` | `BK` | `N` | `C` |
| BP | 2 Party | `ABN44ADC` | **`PR`** | `N` | `D` |
| CR | 1 Cash A/c | `ACASHACT` | `CS` | `N` | `D` |
| CR | 2 Party | `ABQIP5V3` | **`PR`** | `N` | `C` |
| CP | 1 Cash A/c | `ACASHACT` | `CS` | `N` | `C` |
| CP | 2 Party | `ABG6P7KZ` | **`PR`** | `N` | `D` |

---

## 🐛 Bugs Found & Fixed

### BUG 1 — Sales FIELD10 Had Supplier Invoice Number ✅ FIXED
> **Native:** Sales T41 FIELD10 = **blank**
> **Our Code:** Was writing `bill_no` to FIELD10 for Sales too
> **Impact:** Sales vouchers showed a spurious "Supplier Invoice No" field
> **Fix:** FIELD10 is now **only written for Purchases**

---

### BUG 2 — T41 FIELD20 Was Always Hardcoded `1` ✅ FIXED
> **Native:** Purchase PP FIELD20 = `2` (actual number of T01 lines), Sales SS FIELD20 = `3`, `5`, etc.
> **Our Code:** Was always writing `1` regardless of how many lines existed
> **Impact:** Miracle's internal line-count index was wrong, could cause reconciliation mismatch
> **Fix:** FIELD20 is now computed by counting all actual T01 lines (party + ledger + taxes + freight + round-off)

---

### BUG 3 — Bank Party Line (T01 Line 2) Used Wrong FIELD21 ✅ FIXED
> **Native:** Bank Receipt/Payment T01 Line 2 (Party) uses `FIELD21 = 'PR'` (Party Receivable/Payable)
> **Our Code:** Was writing `'PT'` (Pass-through — only for Freight, TCS, etc.)
> **Impact:** Party balances showed in wrong sub-ledger category in Miracle reports
> **Fix:** Bank T01 Party line now correctly uses `FIELD21 = 'PR'`

---

### BUG 4 — Cash Party Line (T01 Line 2) Used Wrong FIELD21 ✅ FIXED
> **Native:** Cash Receipt/Payment T01 Line 2 (Party) uses `FIELD21 = 'PR'`
> **Our Code:** Was writing `'PT'`
> **Impact:** Same as Bank — party outstanding reports were broken
> **Fix:** Cash T01 Party line now correctly uses `FIELD21 = 'PR'`

---

### BUG 5 — Bank T01 Party Line FIELD20 Was `'C'` (Cleared) ✅ FIXED
> **Native:** Bank T01 Party line FIELD20 = `'N'` (Not-cleared / pending)
> **Our Code:** Was writing `'C'` (Cleared), only the Bank ledger line should use `'C'` where applicable
> **Fix:** Changed to `'N'` for consistency with native records

---

### BUG 6 — Cash T41 Header FIELD03 Was String `'1'`, Not `'2'` ✅ FIXED (previous session)
> **Native:** Cash Header FIELD03 = `2` (Setup ID for Cash/Bank Book)
> **Fix:** Changed to `2`

---

### BUG 7 — Cash T01 Cash Line FIELD21 Was `'BK'` ✅ FIXED (previous session)
> **Native:** Cash Receipt/Payment Line 1 (Cash A/c) = `'CS'` (Cash), NOT `'BK'` (Bank)
> **Fix:** Changed to `'CS'`

---

## ✅ Things That Were Already Correct

| Module | Check | Status |
|--------|-------|--------|
| Sales T41 `FIELD21` | `'T'` (Tax Invoice) ✅ matches native | CORRECT |
| Sales T41 `FIELD74` | `'SP'` (Sales/Purchase) ✅ | CORRECT |
| Sales T41 `T41F96` | `'G'` ✅ | CORRECT |
| Bank T41 `FIELD74` | `'CB'` (Cash/Bank) ✅ | CORRECT |
| Bank T41 `T41F96` | `'N'` ✅ | CORRECT |
| Bank T01 Bank Line `FIELD21` | `'BK'` ✅ | CORRECT |
| Sales CGST/SGST ledger codes | `AGST0008`/`AGST0009` ✅ | CORRECT |
| Purchase CGST/SGST ledger codes | `AGST0005`/`AGST0006` ✅ | CORRECT |
| Round-off ledger | `AVAUTO99` ✅ | CORRECT |
| Sales Party line (T01 Line 1) `FIELD21` | `'PR'` ✅ | CORRECT |
| GST Summary (T52) structure | Matches Miracle format ✅ | CORRECT |
| Voucher duplicate detection | 7-tuple key is robust ✅ | CORRECT |
| Year folder routing | FY mapping fixed ✅ | CORRECT |

---

## Opening Balance Analysis

**What we write to `RKACAMB1.DBF`:**

| Field | Value | Native Expected |
|-------|-------|-----------------|
| `MB1F01` | Ledger code | ✅ Correct |
| `MB1F02` | OB date (March 31 of FY start) | ✅ Correct |
| `MB1F90` | Balance (+Dr / -Cr) | ✅ Correct |
| `MB1F99` | Net balance (same as MB1F90) | ✅ Correct |
| `MB1F97` | `0.0` | ✅ Correct |
| `MB1F98` | `0.0` | ✅ Correct |

**One potential issue:** If you open a year for the first time and AMB1 is empty, `max(dates)` returns nothing and we fall back to calculating `date(2000 + yr_val - 1, 3, 31)`. For YR25 = `2024-03-31` ✅, For YR26 = `2025-03-31` ✅.

---

## Module Field Reference Card

### Sales (SS) — Complete T01 Entry Structure
```
Line 1: FIELD03=CashOrParty, FIELD21='CS'(cash)/'PR'(debtor), DR
Line 2: FIELD03=SalesAccount, FIELD21='TS', CR, Amount=net_taxable
Line 3: FIELD03=CGST_Ledger, FIELD21='TX', CR
Line 4: FIELD03=SGST_Ledger, FIELD21='TX', CR
Line 5: FIELD03=FreightLedger, FIELD21='PT', CR (if any)
Line 6: FIELD03=AVAUTO99, FIELD21='PT', DR/CR (if round-off)
```

### Purchase (PP) — Complete T01 Entry Structure
```
Line 1: FIELD03=SupplierCode, FIELD21='PR', CR
Line 2: FIELD03=PurchaseAccount, FIELD21='TP', DR, Amount=net_taxable
Line 3: FIELD03=CGST_Ledger, FIELD21='TX', DR
Line 4: FIELD03=SGST_Ledger, FIELD21='TX', DR
Line 5: FIELD03=FreightLedger, FIELD21='PT', DR (if any)
Line 6: FIELD03=AVAUTO99, FIELD21='PT', DR/CR (if round-off)
```

### Bank Receipt (BR) / Bank Payment (BP)
```
Line 1: FIELD03=BankAccount, FIELD21='BK', DR(receipt)/CR(payment)
Line 2: FIELD03=PartyAccount, FIELD21='PR', CR(receipt)/DR(payment)
```

### Cash Receipt (CR) / Cash Payment (CP)
```
Line 1: FIELD03=CashAccount, FIELD21='CS', DR(receipt)/CR(payment)
Line 2: FIELD03=PartyAccount, FIELD21='PR', CR(receipt)/DR(payment)
```

---

> [!IMPORTANT]
> After pushing new entries, always **Reindex** in Miracle: `Utility → Reindex` to rebuild index files.
