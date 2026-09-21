---
name: accounting_safety_guards
description: Authoritative guidelines and instructions for enforcing accounting double-entry rules, 3-tier confidence routing, 7-check automated validators, 37 Smart Rules compliance, and RLHF memory learning in Miracle AI Auto-Entry.
---

# Accounting Safety Guards & Quality Protocols

> [!IMPORTANT]
> **CRITICAL ACCOUNTING SAFETY DIRECTIVE:**
> Accounting mistakes directly corrupt client financial ledgers and GST returns. Ambiguous or mathematically invalid vouchers **MUST NEVER** touch Miracle DBF files directly. When confidence is uncertain (`< 80%`) or double-entry validation fails, transactions **MUST** be routed to the **Review Queue** (`60-79%`) or **Suspense Account** (`< 60%`).

---

## 1. Universal Smart Rules Enforcement (37 Smart Rules Protocol)

All accounting guards and validation functions MUST enforce key directives from `docs/AI_RULES.md`:

- **Rule 26 — Generic Group Header Rejection**: NEVER map generic banking descriptors (`CHEQUE DEPOSIT`, `CHQ DEP`, `CLEARING`, `NEFT`) or parent group headers (`Sundry Debtors`, `Sundry Creditors`) as party ledger accounts. All unmapped or generic narrations MUST route to `Suspense Account` (`G0000028`).
- **Rule 32 — Universal Suspense Routing & 80% Confidence Guard**: Any transaction extraction, AI suspense mapping, or heuristic fallback with confidence score `< 80%` MUST automatically route to `Suspense Account` (`G0000028`) with `confidence_score = 40` and flag `Human Review Required` (amber `Review` badge).
- **Rule 34 — Cash Sales & Cash Purchases Isolation Protocol**: All cash transactions matching `CASH`, `COUNTER SALE`, `CASH PURCHASES` MUST map party_code (`FIELD04` in `RKACCT41.DBF`) strictly to master `Cash Account` (`G0000005`). Never create fake party ledgers under Debtors or Creditors for cash sales.
- **Rule 37 — Universal Inter-Bank Contra Identification Protocol**: Transfers between two internal Bank Accounts (`G0000004`) MUST be identified as genuine Contra vouchers with `f98 = 'BC'` and `FIELD16 = 'C'` in header (`RKACCT41.DBF`). Both lines in `RKACCT01.DBF` MUST set `FIELD21 = 'BK'`.

---

## 2. Three-Tier Confidence Routing Architecture

Every transaction processed by `gemini_service.py` is assigned a dynamic confidence score (`0-100%`) based on memory match, master ledger alignment, embedding similarity, and party extraction clarity.

```
Score >= 80%  ──► Auto-Mapped (Direct DBF Write Candidate ✅)
Score 60-79%  ──► Review Queue (Requires 1-Click Confirmation ⚠️)
Score < 60%   ──► Suspense Account (Forced to G0000028, Isolated 🔴)
```

### Detailed Tier Behaviors

1. **Tier 1: Auto-Mapped (`score >= 80%`)**
   - Triggered when exact directional memory (`DR:narration` / `CR:narration`), exact master ledger token match, or high cosine similarity (> 0.85) in `embedding_engine.py` is established.
   - Status flag set to `"Auto"`. Eligible for direct entry into `RKACCT41.DBF` & `RKACCT01.DBF`.

2. **Tier 2: Review Queue (`60% <= score < 80%`)**
   - Triggered when fuzzy word boundary match or generalized AI classification suggests a ledger but lacks high confidence.
   - Status flag set to `"Review"`. AI mapping suggestion preserved in `suggested_ledger` for client/CA 1-click approval.

3. **Tier 3: Suspense Account (`score < 60%` or Generic Narration)**
   - Triggered for unidentifiable narrations (e.g. `"CHQ CLEARING"`, `"TRANSFER"`, `"MISC"`).
   - Status flag set to `"Suspense"`. Ledger automatically reassigned to **Suspense Account** (`G0000028` / `SUSPENSE A/C`). Never written into live DBF books without user override.

---

## 3. Nature-Based Mapping & Illegal Account Protection Rules

As specified in `docs/SMART_ACCOUNTING_NATURE_RULES.md`, generic system or asset keywords MUST NEVER map to specific trade debtors or creditors (e.g. `CASH` mapped to `RADHE KRISHNA`, or `COMPUTER` mapped to `MITESHBHAI`):

```python
PROTECTED_NATURE_KEYWORDS = {
    # System Transaction Modes
    "CASH", "CHEQUE", "CHQ", "ATM", "TRANSFER", "ONLINE", "PAYMENT", "RECEIPT", 
    "DEPOSIT", "NEFT", "RTGS", "UPI", "IMPS", "EFT", "POS", "CARD",
    
    # Generic Assets & Equipment
    "COMPUTER", "LAPTOP", "PRINTER", "MOBILE", "CAR", "VEHICLE", "MACHINE", "FURNITURE",
    
    # Generic Operational Expenses
    "SALARY", "RENT", "TEA", "PETROL", "FUEL", "ELECTRICITY", "INTEREST", "BANK CHARGES"
}
```

- If key is in `PROTECTED_NATURE_KEYWORDS`, mapping to `Sundry Debtors` (`G0000009`) or `Sundry Creditors` (`G0000013`) is **ILLEGAL** and gets purged automatically by `AIMemoryVault.is_illegal_nature_mapping()`.

---

## 4. The 7-Check Automated Accounting Validator (`backend/validators.py`)

Prior to saving or exporting any voucher batch, `AccountingValidator` executes 7 mandatory quality checks:

### Check 1: Double-Entry Direction Safeguard
- **Payment Vouchers**: Target account **MUST** be Debit-nature (`EXPENSE`, `ASSET`, `CREDITOR`, `DIRECT EXPENSES`, `INDIRECT EXPENSES`). Payment to Credit-nature account (`SALES`, `INCOME`, `DIRECT INCOMES`, `DEBTOR`) **FAILS** and forces row to Suspense.
- **Receipt Vouchers**: Target account **MUST** be Credit-nature (`INCOME`, `LIABILITY`, `DEBTOR`, `DIRECT INCOMES`, `INDIRECT INCOMES`). Receipt to Debit-nature account (`PURCHASE`, `EXPENSE`, `CREDITOR`) **FAILS** and forces row to Suspense.
- *Exemptions*: Bank (`G0000004`), Cash (`G0000005`), Loan, and Capital ledgers are valid in both directions.

### Check 2: Amount Anomaly Guard
- Compares transaction amount against historical average amount stored in `ai_memory.py` (`ledger_stats`).
- Flags transactions exceeding **5x historical average** (when average > ₹1,000) with `"Amount Anomaly"`.

### Check 3: Frequency Spike Guard
- Analyzes single-statement batch for excessive repetition.
- Flags batches where **20+ transactions** map to the exact same ledger with `"High Frequency Spike"`.

### Check 4: Statement Balance Math Check
- Enforces strict equation: `Opening Balance + Total Receipts - Total Payments == Closing Balance` (tolerance ₹1.00).

### Check 5: GST & Tax Consistency Guard
- Scans narrations containing keywords like `GST`, `IGST`, `CGST`, `SGST`, `TAX`.
- Ensures target ledger is categorized under Tax/Duties or Purchase/Sales, flagging non-GST mappings with `"GST Review"`.

### Check 6: Peer & Business Profile Alignment
- Cross-references mapping against client industry context from `ai_business_profiler.py`.
- Flags anomalous ledgers foreign to client's primary business activities.

### Check 6b: Section 194Q TDS Threshold Alert (₹50 Lakhs)
- Tracks cumulative YTD purchases per vendor.
- When cumulative purchases cross **₹50 Lakhs** (`₹5,000,000`), triggers a mandatory **0.1% TDS Alert** flag (`194Q TDS Alert`) to ensure tax compliance.

### Check 7: Extreme Amount Sanity Guard
- Enforces a hard single-transaction sanity limit of **₹10 Crore** (`100,000,000`). Exceeding transactions raise `"Extreme Amount Warning"`.

---

## 5. RLHF Memory Feedback & Learning Protocol

When a user approves or corrects a mapped ledger in the UI:
1. `ai_memory.py` receives an update entry with direction prefix:
   - Debit side: `"DR:" + narration.upper()`
   - Credit side: `"CR:" + narration.upper()`
2. `ledger_stats` updates `usage_count` and recalculates running `avg_amount`.
3. UI selection instantly sets `confidence_score = 100`, updates status to `Ready` / `Mapped`, and persists rule permanently to client memory.
