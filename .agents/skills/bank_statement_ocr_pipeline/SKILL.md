---
name: bank_statement_ocr_pipeline
description: Technical instructions and normalization protocols for bank statement PDF, Excel, and Image OCR extraction, multi-bank format parsing, narration cleaning, and party extraction.
---

# Bank Statement OCR & Extraction Pipeline Manual

> **Purpose**: Standardize tabular data extraction across Indian bank statements (PDF, Excel, Images), clean complex narration strings using 14-step purification rules, extract counterparty names, and enforce Smart Rules 16–18 for date continuity and sequential balance carryover.

---

## 1. Document Extraction Rules (Smart Rules 16 – 18)

- **Rule 16 — Sequential Balance Carryover**: Process bank PDF chunks sequentially, injecting closing balances into subsequent prompts to preserve transaction continuity across multi-page statements.
- **Rule 17 — Universal Date-Gap Continuity Check**: Trigger recursive sub-page splitting if consecutive transaction rows exhibit a date gap $> 28$ days.
- **Rule 18 — Indian Standard Date Parsing**: Always prioritize Day-First date parsing formats (`%d/%m/%Y`, `%d-%m-%Y`) over Month-First American formats (`%m/%d/%Y`).

---

## 2. Document Ingestion Workflow

```
[ Uploaded Document: PDF / XLSX / PNG ]
           │
           ▼
[ File Type Classifier ]
   ├── Excel (.xlsx / .xls) ──► Pandas / OpenPyXL tabular extraction
   ├── Native Text PDF ────────► PyPDF / pdfplumber tabular parser
   └── Scanned PDF / Image ────► Gemini 2.5 Flash Multimodal Vision OCR
           │
           ▼
[ 14-Step Narration Key Purification & Party NER (ai_memory.py) ]
           │
           ▼
[ Math Verification (Opening + Deposits - Withdrawals == Closing) ]
           │
           ▼
[ 6-Stage Intelligence Pipeline Mapping ]
```

---

## 3. 14-Step Narration Key Purification Protocol (`ai_memory.py`)

Raw bank narrations contain noise (UTRs, IFSC codes, UPI handles, dates, cities, transaction prefixes). `clean_mapping_key(narration)` cleans narrations into core search keys using a 14-step filter:

1. **Named Entity Subtraction**: Invokes `BankEntityRecognizer.extract_vendor_entity(narration)`.
2. **Strip Account/Ref Numbers**: Removes leading sequence IDs (`01631000019173-TPT-PARKING` $\rightarrow$ `TPT-PARKING`).
3. **Strip Transaction Prefixes**: Strips `UPI/`, `NEFT DR-`, `RTGS CR-`, `IMPS/`, `ACH DR-`, `ATM WDL`.
4. **Strip UPI Handles**: Removes `@okicici`, `@ybl`, `@paytm`, `@sbi`, `@hdfc`.
5. **Strip Bank IFSC Codes**: Scrub 11-char IFSC patterns (`UTIB0000215`, `SBIN0001234`).
6. **Strip Long UTR References**: Scrub `N103250239`, `R90215820`.
7. **Strip Date/Month Tokens**: Scrub `JAN`, `FEB`, `2025`, `2026`, `31/03/2026`.
8. **Strip City/State Names**: Scrub `RAJKOT`, `AHMEDABAD`, `MUMBAI`, `SURAT`, `DELHI`.
9. **Strip Banking Filler Words**: Scrub `PAID`, `SENT`, `RECEIVED`, `TRANSFER`, `REMARK`, `BRANCH`.
10. **Strip Non-Alphanumeric**: Convert punctuation to spaces.
11. **Filter Token Length**: Keep only tokens $\ge 3$ characters that are non-numeric.
12. **Word Deduplication**: Merge broken syllables (`CRED CRED CLUB` $\rightarrow$ `CRED CLUB`).
13. **Pure Numeric Rejection**: Pure digit keys (`7432`, `757`) are rejected ($""$).
14. **Single Short Word Guard**: Single words $< 5$ chars (e.g. `RAM`, `ROY`) are rejected unless registered in valid accounting exceptions (`CRED`, `PGCL`).

---

## 4. Supported Bank Formats & Data Layouts

| Bank | Date Format | Narration Identifiers | Amount Column Layout |
|---|---|---|---|
| **ICICI Bank** | `DD-MM-YYYY` | `UPI/`, `NEFT-`, `INF/`, `POS/` | Separate Debit & Credit columns |
| **HDFC Bank** | `DD/MM/YY` | `NFS-`, `UPI-`, `ACH-`, `IMPS-` | Debit / Credit + Balance |
| **State Bank of India (SBI)**| `D MMM YYYY` | `TRANSFER TO`, `BY TRANSFER`, `UPI/` | Withdrawal / Deposit |
| **Axis Bank** | `DD-MM-YYYY` | `BY CLEARING`, `TO CLEARING`, `UPI/` | DR Amount / CR Amount |
| **Bank of Baroda (BOB)** | `DD/MM/YYYY` | `BARB`, `NEFT`, `IMPS` | Debit / Credit |

---

## 5. Statement Math Balance Verification

Before passing extracted rows to the mapping router, `validators.py` verifies statement arithmetic:

$$\text{Calculated Closing Balance} = \text{Opening Balance} + \sum \text{Deposits (Receipts)} - \sum \text{Withdrawals (Payments)}$$

- **Tolerance**: Maximum allowable deviation is **₹1.00** (to account for rounding differences).
- **Error Flag**: If $\Delta > 1.00$, flag statement with `"Statement Math Mismatch"` and alert user to missing or corrupted transaction rows.
