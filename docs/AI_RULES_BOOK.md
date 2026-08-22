# 🧠 MIRACLE AI AUTO-ENTRY — MASTER AI RULES BOOK
> **MANDATORY READ FOR EVERY NEW AI SESSION.**
> Before touching ANY code in this project, read this file top-to-bottom.
> It contains EVERY rule, bug, and decision made across all past sessions.
> Ignoring this file will cause repeating the same mistakes.
>
> ⚠️ CRITICAL PHILOSOPHY: Every rule in this file must be **UNIVERSAL**.
> Rules must work for ALL clients, ALL banks, ALL months, ALL statement formats.
> NEVER write a rule that is specific to one client, one month, or one bank name.
> If a rule mentions "CMP0002" or "October" or "HDFC" — it is WRONG and must be generalized.

*Last updated: 2026-07-27 by Antigravity AI*

---

## PART 0 — THE 100+ CLIENT UNIVERSAL DEVELOPMENT PROTOCOL

> 🛡️ **THE 100-CLIENT MANDATE**: The Miracle AI Platform serves **100+ diverse businesses across India** (Retail, Wholesale, Footwear, Medical Manufacturing, Services, Personal Accounting, FMCG, Textiles, etc.). 
> **NEVER** write single-file or single-client hardcoded patches. Every bug fix, AI prompt adjustment, and DBF writer rule MUST be designed to work universally across all 100+ clients without breaking existing behavior.

### The 4-Step Mandatory AI Execution Workflow:

1. **Understand & Explain the Root Cause First (100-Client Mindset):**
   - Thoroughly analyze the bug. Explain *why* it occurred and *how* it affects all 100+ clients across different industries.
   - Evaluate edge cases: Ask *"Will this fix break for a retail client? A footwear client? A bank statement client?"*

2. **Design a Universal, Self-Healing Solution:**
   - Build algorithms that dynamically adapt based on structure, math, and database metadata rather than hardcoded string matching.
   - Protect client-isolated rules in `AI_Memory_Vault/{CLIENT_ID}_memory.json` if a rule is truly unique to one client, keeping core backend engines universal.

3. **Document Universal Rules Immediately:**
   - Update this `AI_RULES_BOOK.md` file with the new universal rule to preserve AI memory across sessions.
   - Log the fix in human-readable detail in `docs/CHANGELOG.md`.

4. **Empirical Automated Verification:**
   - Create multi-scenario unit test scripts in `scratch/` testing both standard cases and diverse edge cases across multiple client types before declaring success.

---

## PART 1 — PROJECT ARCHITECTURE (What is What)

```
Project Root/
├── frontend/
│   ├── index.html          ← UI layout, modals, grid, toolbar buttons
│   └── app.js              ← All JS logic: state, grid rendering, API calls, push
├── backend/
│   ├── main.py             ← FastAPI endpoints (the API surface)
│   ├── dbf_handler.py      ← ALL DBF read/write logic (the most critical file)
│   ├── gemini_service.py   ← Gemini AI extraction prompts and post-processing
│   ├── ai_memory.py        ← Client-isolated AI memory (expense mappings, specs)
│   └── settings.json       ← Runtime config (api key, paths, active client)
├── AI_Memory_Vault/
│   └── {CLIENT_ID}_memory.json ← Per-client memory (business profile, expense_mappings, specs)
├── docs/
│   ├── AI_HANDOFF.md       ← Original bug history (read too)
│   ├── AI_RULES_BOOK.md    ← THIS FILE (universal rules — read first)
│   └── ROADMAP_FUTURE_TASKS.md ← Completed & planned features
└── CHANGELOG.md            ← Human-readable log of every fix
```

### Miracle DBF Table Reference
| Table | Purpose |
|---|---|
| `RKACCM01.DBF` | Party Ledger master (names, codes, groups) |
| `RKACCM02.DBF` | Party extended info (address, GSTIN, state) |
| `RKACCM11.DBF` | Account Groups hierarchy (G0000001...G0000028) |
| `RKACCM12.DBF` | Bank account masters |
| `RKACCM14.DBF` | HSN / Commodity masters |
| `RKACCM21.DBF` | Product masters |
| `RKACCT01.DBF` | Ledger line items (double-entry debit/credit lines) |
| `RKACCT40.DBF` + `.fpt` | Long narration memo store |
| `RKACCT41.DBF` | Voucher headers (one per voucher) |
| `RKACCT02.DBF` | Invoice line items (qty, rate, HSN per product) |
| `RKACCT52.DBF` | GST/Tax summary (GSTR linking) |
| `RKACCGID.DBF` | GUID registry for new ledgers |

---

## PART 2 — ACCOUNT GROUPS CLASSIFICATION RULES

### Golden Rule: NEVER hardcode group codes
Always query `RKACCM11.DBF` dynamically. Each client's Miracle installation assigns different codes to the same group names. The `find_group_by_name()` helper in `create_party_ledger()` does this correctly.

### Standard Group Search Patterns (in `dbf_handler.py`)
| Logical Group | Search Patterns in RKACCM11 | Fallback Code |
|---|---|---|
| Indirect Expenses | `"EXPENSE ACCOUNT"`, `"INDIRECT EXPENSE"`, `"EXPENSE"` | `G0000017` |
| Direct Expenses | `"EXPENSES (DIRECT)"`, `"DIRECT EXPENSE"` | `G0000014` |
| Indirect Income | `"INCOME (OTHER THEN SALES)"`, `"INDIRECT INCOME"`, `"INCOME"` | `G0000016` |
| Sundry Debtors | `"SUNDRY DEBTORS"`, `"DEBTOR"`, `"CUSTOMER"` | `G0000009` |
| Sundry Creditors | `"SUNDRY CREDITORS"`, `"CREDITOR"`, `"SUPPLIER"` | `G0000013` |
| Bank Accounts | `"BANK ACCOUNTS (BANKS)"`, `"BANK ACCOUNTS"`, `"BANKS"` | `G0000004` |
| Loans & Advances (Asset) | `"LOANS & ADVANCES (ASSET)"`, `"LOANS & ADVANCES"` | `G0000007` |
| Unsecured Loans (Liability) | `"UNSECURED LOANS"`, `"UNSECURED"` | `G0000019` |
| Capital Account | `"CAPITAL ACCOUNT"`, `"CAPITAL"` | `G0000001` |
| Fixed Assets | `"FIXED ASSETS"`, `"FIXED ASSET"` | `G0000006` |
| Suspense Account | `"SUSPENSE ACCOUNT"`, `"SUSPENSE"` | `G0000028` |

### Personal Accounting vs Business Accounting (CRITICAL DISTINCTION)
The `business_profile` field in the client's memory JSON tells us which mode:

| Scenario | Who is the Party? | Money Sent → | Money Received → |
|---|---|---|---|
| **Personal Accounting** | Individual human name (no business keywords) | `Loans & Advances (Asset)` | `Unsecured Loans` |
| **Business Accounting** | Registered business / vendor | `Sundry Creditors` | `Sundry Debtors` |
| **Either** | Has expense PURPOSE in UPI suffix (milk, petrol, food) | `Indirect Expenses` ledger | `Indirect Expenses` ledger |
| **Either** | Has `BANK`, `HDFC`, `ICICI`, `SBI` in name | `Bank Accounts` | `Bank Accounts` |
| **Either** | Has `SUSPENSE` in name | `Suspense Account` | `Suspense Account` |

---

## PART 3 — GEMINI AI EXTRACTION RULES (`gemini_service.py`)

### Rule 3.1 — Bank Statement Extraction Prompt (Universal Rules)
The Gemini prompt enforces ALL of the following in ORDER:

**STEP 1 — Complete Row Extraction (No Skipping):**
- Extract EVERY SINGLE transaction row on every page, line-by-line
- DO NOT skip any rows, pages, or periods (months/weeks)
- DO NOT output a "Closing Balance" or "Opening Balance" row as a transaction

**STEP 2 — Universal Date-Gap Rule (Client-Agnostic):**
> ⚠️ This rule is UNIVERSAL — applies to ALL banks, ALL clients, ALL months.
- If in the output two consecutive transactions are more than 25 days apart → this is a FAILURE
- It means transactions on the pages in between were silently skipped
- The system enforces this with a mathematical date-gap check that triggers a recursive split
- The prompt explicitly tells Gemini: *"Any date gap > 25 days between consecutive rows = failure. Re-scan and find missing rows."*
- This is NOT specific to any month or client — it detects gaps for January, February... December equally

**STEP 3 — Universal Date Format Rule (Indian Standard):**
> ⚠️ This rule applies to ALL Indian bank statements universally.
- Indian banks always use DD/MM/YY or DD/MM/YYYY (Day first, Month second, Year last)
- NEVER interpret any date as MM/DD/YY (American format)
- `26/06/25` = 26th June 2025 = output `2025-06-26`
- `01/07/25` = 1st July 2025 = output `2025-07-01`
- `07/01/25` = 7th January 2025 = output `2025-01-07`
- If year is 2 digits (e.g., `25`), always assume `20xx` (e.g., `2025`)
- Always output in ISO format: `YYYY-MM-DD`

**STEP 4 — UPI/NEFT Description Parsing (3-part format):**
```
UPI-[PARTY NAME]-[PURPOSE]@[BANK]
     ↑ who          ↑ what
```
- If PURPOSE = expense keyword (milk, food, petrol, salary, rent, electricity, medicine, dinner, recharge, mobile, insurance, repair, water, gas, school, fees) → `mapped_ledger` = expense type, NOT person name
- If PURPOSE = empty / generic UPI ID / reference number → `mapped_ledger` = clean party name

**STEP 5 — Person vs Business Decision:**
- Person name + no expense keyword + WITHDRAWAL → `group_hint` = `"Loans & Advances (Asset)"`
- Person name + no expense keyword + DEPOSIT → `group_hint` = `"Unsecured Loans"`
- Person is NEVER classified as an Expense or Income

**STEP 6 — Narration field:**
- ALWAYS copy the FULL original text. Never truncate. Never clean.

**STEP 7 — Mathematical Verification (ALWAYS REQUIRED):**
- Always extract `running_balance` for EVERY row
- If balance went UP → must be Receipt. If Gemini said Payment → ERROR
- If balance went DOWN → must be Payment. If Gemini said Receipt → ERROR

---

### Rule 3.2 — Universal Chunk Validation (`verify_chunk_math`)
The `verify_chunk_math()` function runs TWO independent checks universally:

**Check 1 — Running Balance Math (Row-by-Row):**
```
delta = current_running_balance - previous_running_balance
if abs(abs(delta) - transaction_amount) > 5.0 → FAIL → trigger split
```

**Check 2 — Date-Gap Continuity (Universal Skip Detection):**
```
if consecutive rows have a date gap > 28 days AND chunk has > 1 page → FAIL → trigger split
```
> This Check 2 is what catches **silent month skipping** — where Gemini returns mathematically-matching balances but omits entire months of transactions. It does NOT care which month was skipped. It fires for any gap > 28 days for any client, any bank, any year.

---

### Rule 3.3 — Recursive Split-on-Failure (PDF & Excel)
When `verify_chunk_math()` returns `False` for any reason:
1. If chunk has > 1 page/row → split range in half, process both halves sequentially, carry balance
2. If chunk has only 1 page/row → retry up to 3 times
3. If both halves pass → combine and continue

This is implemented in:
- `extract_pdf_pages_recursive()` for PDFs
- `extract_excel_rows_recursive()` for Excel files

---

### Rule 3.4 — Universal Post-Extraction Date Normalization
After ALL Gemini chunks are merged, a normalization pass runs on EVERY extracted row:
```python
# Try formats in this order (DD/MM always before YYYY/MM for Indian banks)
formats = ["%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y", "%Y/%m/%d"]
```
This fixes any date Gemini returned in wrong format before the final result is returned.

---

### Rule 3.5 — Global Date-Gap Audit (Final Pass)
After all chunks are combined, a final audit scans EVERY consecutive row pair:
- If any gap > 28 days remains → logs: `⚠️ [GLOBAL DATE-GAP AUDIT] Row X→Y: date1 to date2 = N days gap`
- This is a MONITORING/WARNING pass — does not throw errors, but flags potential residual skips

---

### Rule 3.6 — PDF Chunk Processing
- PDFs are split using **Dynamic Chunk Sizing** (Strategy B):
  - `≤ 20 pages` → 3-page chunks (maximum accuracy)
  - `21–50 pages` → 5-page chunks (balanced)
  - `> 50 pages` → 10-page chunks (speed for dense files)
- Chunks are processed **SEQUENTIALLY**, one by one
- After each chunk: extract closing balance → inject into NEXT chunk prompt
- Format: `"PREVIOUS BALANCE CONTEXT: The running bank balance right before this chunk starts was ₹X."`

---

### Rule 3.7 — Post-Extraction Mathematical Validator
After Gemini returns all results, `validate_and_fix_transaction_types()` runs:
1. Sort rows by date
2. Compute delta = `current_balance - previous_balance`
3. If delta > 0 but type = "Payment" → auto-fix to "Receipt"
4. If delta < 0 but type = "Receipt" → auto-fix to "Payment"
5. If amount doesn't match delta by > ₹1 → also fix the amount

---

### Rule 3.8 — Paid API Speed Mode (`is_paid_api_key`)
The system has a setting `is_paid_api_key` (saved in `settings.json`, toggleable in Settings UI):
- **Free API key (default):** 4.5-second sleep between every sequential chunk (respects 15 RPM limit)
- **Paid API key (enabled):** 0.2-second sleep between chunks (no RPM bottleneck → ~10x faster)
- This setting is passed to `GeminiService(is_paid_api_key=...)` from ALL endpoints in `main.py`
- `GeminiService.__init__` stores it as `self.is_paid_api_key`
- The delay is applied in: `extract_pdf_pages_recursive`, `extract_excel_rows_recursive`, chunk walk loops

---

## PART 4 — DBF WRITE RULES (`dbf_handler.py`)

### Rule 4.1 — Sales vs Purchases Flags (CRITICAL — Bug #1 history)
When writing `RKACCT41.DBF` (voucher header):
- `FIELD16`: `'C'` (Credit) for Purchases, `'D'` (Debit) for Sales

When writing `RKACCT02.DBF` (line items):
- `FIELD04`: `'N'` for Purchases, `'I'` for Sales
- `FIELD05`: `'D'` (Debit) for BOTH Purchases (Debit Purchase/Goods A/c) and Sales (Debit Debtor A/c) — setting `'C'` causes Red Text!

When writing `RKACCT52.DBF` (GST summary):
- `T52F05`: `'C'` for Purchases, `'T'` for Sales
- `T52F22`: `'C'` (Credit) for Purchases, `'D'` (Debit) for Sales
- `T52F28`: `'C'` for Purchases, `'T'` for Sales
- `T52F29`: `'O'` for both
- `T52F30`: `'4'` (Purchase Book) for Purchases, `'3'` (Sales Book) for Sales

When writing `RKACCT01.DBF` (General Ledger Double Entry):
- `PR` (Party Line): `FIELD06 = 'C'` (Credit Supplier) for Purchases, `FIELD06 = 'D'` (Debit Customer) for Sales
- `TP`/`TS` (Purchase/Sales Line): `FIELD06 = 'D'` (Debit Purchase) for Purchases, `FIELD06 = 'C'` (Credit Sales) for Sales
- `TX` (Tax Lines): `FIELD06 = 'D'` (Debit Input Tax) for Purchases, `FIELD06 = 'C'` (Credit Output Tax) for Sales

### Rule 4.2 — Bank Statement Voucher Types
- `BR` = Bank Receipt (money comes IN to bank from outside)
- `BP` = Bank Payment (money goes OUT of bank to outside)
- `CV` = Contra Voucher (cash↔bank movement, e.g. ATM withdrawal, bank deposit from cash)
  - Triggered when party name contains `CASH` (bank push) or `BANK` (cash push)

**CRITICAL — T41 `FIELD16` values (voucher direction flag):**
| Voucher Type | `FIELD16` | Meaning |
|---|---|---|
| `BR` (Bank Receipt) | `'R'` | Receipt |
| `BP` (Bank Payment) | `'P'` | Payment |
| `CR` (Cash Receipt) | `'R'` | Receipt |
| `CP` (Cash Payment) | `'P'` | Payment |
| `CV` (Contra — ANY direction) | `'C'` | Contra |

> ⚠️ UNIVERSAL RULE: **CV entries ALWAYS get `FIELD16 = 'C'`** regardless of whether money is going in or out. Using `'R'` or `'P'` for a CV entry causes Miracle to fail opening the voucher (the "entry not opening" bug).

**CRITICAL — T01 `FIELD21` values (line classification flag):**
| What is this T01 line? | `FIELD21` |
|---|---|
| Bank ledger line (in any BR/BP entry) | `'BK'` |
| Cash ledger line (in any CR/CP entry) | `'CS'` |
| CV entry — Bank side line | `'BK'` |
| CV entry — Cash side line | `'CS'` |
| Party/Debtor/Creditor line | `'PR'` |
| Expense/Income/Other ledger line | `'PT'` |

> ⚠️ UNIVERSAL RULE: For a **CV from Bank push** (party is Cash Account), the party T01 line MUST be `'CS'` (Cash). For a **CV from Cash push** (party is Bank account), the party T01 line MUST be `'BK'` (Bank). **Never use `'PT'` for Cash or Bank party lines in CV entries** — this causes the Cash Account debit/credit entry to not open in Miracle.

When writing `RKACCT41.DBF` (bank/cash voucher header):
- `FIELD16`: `'R'` for BR/CR Receipt, `'P'` for BP/CP Payment, `'C'` for any CV Contra
- `FIELD21`: `'O'` (matches native Miracle's CB type)
- `FIELD74`: `'CB'` (Cash/Bank identifier)

When writing `RKACCT01.DBF` (double-entry lines for BR/BP — Bank push):
- Bank line: Debit for Receipt (`FIELD04='D'`), Credit for Payment (`FIELD04='C'`), `FIELD21='BK'`
- Party line: Credit for Receipt (`FIELD04='C'`), Debit for Payment (`FIELD04='D'`), `FIELD21` = dynamic ('PR'/'PT'/'CS' depending on party type)

When writing `RKACCT01.DBF` (double-entry lines for CV — Contra Voucher):
- For CV from Bank push (cash withdrawal/deposit): Bank line `FIELD21='BK'`, Cash party line `FIELD21='CS'`
- For CV from Cash push (bank deposit/withdrawal): Cash line `FIELD21='CS'`, Bank party line `FIELD21='BK'`

### Rule 4.3 — Narration Storage (2 fields)
- `FIELD82` in T41: First **50 characters** only (short header field)
- `T40F02` in T40 (memo): **Full unlimited narration** — ALWAYS write both

### Rule 4.4 — Year Number (`T41F45`, `T01F45`)
```python
year_num = int(year_folder[-2:])  # "YR26" → 26, "YR27" → 27
```
This must match the Miracle year. Getting this wrong puts data in the wrong FY.
### Rule 4.5 — New Party Ledger Creation (`create_party_ledger`)
When a party name is not found in Miracle:
1. Check both lowercase and uppercase file paths for DBF
2. Query `RKACCM11.DBF` dynamically for group codes (never hardcode)
3. Detect if it's a person name using `business_keywords` list
4. Register in `RKACCGID.DBF` as well

### Rule 4.6 — Client-Specific Write Locks (Concurrency Rule)
To prevent race conditions, database lock contentions, or browser timeouts during zipping operations over SMB shares, database write paths must be thread-safe.
Instead of a global write lock, use client-specific write locks dynamically fetched via:
```python
get_client_lock(client_id: str)
```
This blocks concurrent requests for the same client while permitting simultaneous writes across different clients, maximizing server throughput.

### Rule 4.7 — DBF & Memo File Compaction (Pointer Recycling Rule)
Miracle uses Visual FoxPro DBF files with companion `.FPT` files for narrations/memos. Standard deletion or edits mark records as deleted but do not reclaim physical space or recycle memo block pointers in `.FPT` files, leading to file bloat.
To recycle block pointers and reclaim space:
1. Re-index and Compact modified tables (e.g. `RKACCT41`, `RKACCT01`, `RKACCT02`, `RKACCT52`, `RKACCT40`) at the end of each injection push.
2. Read the active records from the open table, call `table.new(...)` to initialize a temporary compact schema copy, append the active records using `dbf.scatter(record)`, close both tables, and replace original files on disk.
3. This physically eliminates deleted records and sequentializes memo fields, reclaiming up to 40% of disk space per batch transaction.

---

## PART 5 — YEAR FOLDER SELECTION RULES

### Rule 5.1 — `get_latest_year_folder()` Smart Logic
**DO NOT just return the alphabetically last folder.** Miracle creates empty new year folders (e.g. YR27) that don't have the critical DBF files yet.

Priority:
1. Latest folder that has BOTH `rkacct41.dbf` AND `rkacct01.dbf` → return this
2. Latest folder that has `rkacct41.dbf` only → return this  
3. Alphabetically last folder → fallback only

### Rule 5.2 — Missing DBF Files
If a year folder is missing `rkacct41.dbf` or `rkacct01.dbf`:
- **The push will silently fail** — no error, no data in Miracle
- **Fix:** User must open Miracle → switch to that year → manually create ONE entry → this forces Miracle to create the missing files

---

## PART 6 — KNOWN BUGS & THEIR FIXES (Complete History)

| # | Bug | Root Cause | Fix Location |
|---|---|---|---|
| 1 | Purchases show red text in Miracle | Wrong Sales flags used for Purchases | `dbf_handler.py` RKACCT02/RKACCT52 write flags |
| 2 | Party ledger crash | Non-existent party code | `dbf_handler.py` `create_party_ledger()` |
| 3 | Balance math breaks on edit | Browser drops `input` events | `app.js` event listeners (input+change+keyup) |
| 4 | No manual recalculate | Missing button | `index.html` + `app.js` Recalculate button |
| 5 | Number input spinners | `<input type="number">` | `index.html` converted to `type="text"` |
| 6 | Narration truncated to 50 chars | Global `[:50]` slice | `dbf_handler.py` write both FIELD82 (50) + T40F02 (full) |
| 7 | Person names grouped as Expenses | Prompt bias toward Expense for personal accounting | `gemini_service.py` PERSON exception rule |
| 8 | Recalculate button on all modules | No visibility toggle | `index.html` hidden class + `app.js` module switch |
| 9 | Gemini skips pages in large PDFs | 25-page chunks exceed output token limit | `gemini_service.py` reduced to 5-page chunks, then dynamic sizing |
| 10 | Loans & Advances on both sides of Balance Sheet | All persons put in same group (Asset) regardless of direction | Gemini prompt + `dbf_handler.py` person detection |
| 11 | Withdrawal ↔ Deposit swap | Gemini misreads column positions | `gemini_service.py` `validate_and_fix_transaction_types()` |
| 12 | Page-boundary swap (same amount) | Concurrent chunk processing had no balance context | `gemini_service.py` sequential processing + balance carryover |
| 13 | UPI purpose suffix ignored | Only person name extracted, purpose (milk/petrol) lost | `gemini_service.py` 3-part UPI parsing rule |
| 14 | YR26 data not visible in Miracle | Missing `rkacct41.dbf` + wrong year selected | `dbf_handler.py` `get_latest_year_folder()` smart detection |
| 15 | Cross-year duplicate ledger creation | Ledger master `RKACCM01.DBF` not synced across years | `dbf_handler.py` `read_ledgers_all_years()`, `_sync_party_to_other_years()` |
| 16 | Smart Bank Brand duplicate ledger creation | Substring match failure for legal suffixes in bank names | `dbf_handler.py` `KNOWN_BANK_BRANDS` and Gemini prompt suffix rule |
| 17 | Miracle closing balances not calculating | Bank/Cash entries written with wrong flags | `dbf_handler.py` fixed flags, added repair endpoint & button |
| 18 | **WRONG DATE parsing (2-digit year)** | `%d/%m/%y` format missing from parser; Indian DD/MM/YY format misread as MM/DD/YY | `gemini_service.py`: (a) Added DD/MM/YY rule to Gemini prompt universally for all Indian banks; (b) Added `%d/%m/%y`, `%d-%m-%y` to all 4 date parsing format tuples; (c) Added post-extraction universal date normalization pass |
| 19 | **Silent month/page skipping** | Gemini omits entire months between pages while making balances appear valid | `gemini_service.py`: (a) Added date-gap check (> 28 days between consecutive rows triggers recursive split); (b) Added universal "no date gap > 25 days" rule to Gemini prompt; (c) Added global date-gap audit pass at end |
| 20 | Real-time status polling timeout | Standard HTTP POST times out for long extractions | `main.py` + `app.js` status polling via `/api/upload-status` |
| 21 | Recursive split-on-failure for PDF & Excel | Fixed chunk sizes couldn't adapt to dense transaction pages | `gemini_service.py` `extract_pdf_pages_recursive`, `extract_excel_rows_recursive` |
| 24 | **CV Contra Voucher entries not openable** | (a) `FIELD16` must be `'C'`; (b) Party `FIELD21` must be `'CS'` or `'BK'` | `dbf_handler.py` logic; see Rule 4.2 for field values |
| 25 | **Active year dropdown & Client name display confusion** | (a) Dropdown showed folder codes instead of company names; (b) "Auto-Detect" year option led to YR25/YR26 mismatch issues | (a) `main.py` extracts client names from `rkcmpmei.dbf` / `rkcmpmm.dbf`; (b) Removed `-- Auto-Detect (AI) --` option in year select, auto-switching in `app.js` based on detected dates / owner in upload response |
| 26 | **Contra Voucher (BC) blank columns and opening failure** | Contra entries written with prefix `'CV'` instead of native `'BC'`, header `'FIELD16'` set to `'C'`, and missing numeric initializations caused ledger columns to show up blank and fail to open. | `dbf_handler.py`: (a) Renamed Contra type from `'CV'` to `'BC'`; (b) Set header `'FIELD16'` to `'R'` or `'P'` dynamically; (c) Excluded Contra lines (`T01F96 = 'N'`); (d) Set `FIELD16 = None` and `FIELD22 = None` on secondary lines; (e) Initialized numeric fields `FIELD08`/`FIELD26`/`FIELD29` to `0.0`; (f) Upgraded `repair_bank_entry_flags()` to self-heal existing client database files. |
| 27 | **Crash on formatted amount strings (commas/currency symbols)** | Directly calling `float()` on parsed OCR or user edited values with commas (e.g. `1,250.00`) or currency symbols (e.g. `₹500`) raised ValueError and crashed pushes. | `dbf_handler.py`: (a) Added `_parse_float()` method to strip formatting characters (commas, spaces, `₹`, `$`); (b) Replaced all standard `float()` calls in amount columns with `self._parse_float()`. |
| 28 | **Blank account names in Miracle UI (Cross-year sync bug)** | Matching a party ledger code from another year (e.g. YR25) but not copying the ledger record to the active year's `RKACCM01.DBF` table caused ledger names to show up blank. | `dbf_handler.py`: (a) Upgraded `_inject_bank_statements()` and `_inject_cash_entries()` to verify physical existence of the ledger code in the active year's `RKACCM01.DBF`; (b) Auto-syncs ledger master records from the source year if missing; (c) Ran self-healing sync script to restore 23 missing ledger records in `CMP0002/YR26`. |
| 31 | **Narration not showing in Miracle UI** | (a) `inject_vouchers` (Sales/Purchases) did not write `FIELD82` in `RKACCT41.DBF` or append records to `RKACCT40.DBF` (memo table); (b) 99 legacy vouchers in database were missing `RKACCT40.DBF` memo records. | `dbf_handler.py`: (a) Added `RKACCT40.DBF` writing and `FIELD82` short narration string formatting to `inject_vouchers`; (b) Added `repair_all_voucher_narrations()` self-healing engine and `/api/repair-narrations` endpoint; (c) Successfully repaired 317 voucher headers and restored 99 missing memo records in active database. |

---

## PART 7 — DEBUGGING CHECKLIST (When Miracle doesn't show pushed data)

```
Step 1: Check year folder
  → Is the correct YRxx selected? Run get_latest_year_folder() logic manually.
  → Does the folder have rkacct41.dbf AND rkacct01.dbf? If not → user must create a manual entry in Miracle first.

Step 2: Check T41F45 year_num
  → year_num = int(year_folder[-2:])
  → If year_num is wrong, data goes to wrong fiscal year.

Step 3: Create a manual entry in Miracle UI
  → Read that entry from DBF using Python debug script
  → Compare EVERY field against our injected entry
  → Find the discrepancy (flag mismatch, wrong code, missing field)

Step 4: Check RKACCGID.DBF
  → New party ledgers must be registered here too
  → If missing → Miracle may not recognise the party code

Step 5: Check RKACCT52.DBF (for Sales/Purchase)
  → If T52F30 is wrong (4 vs 3), entry won't appear in GST books
  → If T52F22 is wrong (C vs D), entry shows as red text
```

---

## PART 8 — RULES FOR ADDING NEW FEATURES

1. **Always read SKILL.md + AI_HANDOFF.md + this file first.**
2. **Never hardcode group codes** — always query `RKACCM11.DBF`.
3. **Never hardcode year numbers** — always use `int(year_folder[-2:])`.
4. **Never hardcode month names, client names, or bank names in any rule or prompt** — all rules must be UNIVERSAL and mathematical.
5. **When adding a new Gemini prompt rule** — the rule must apply to ALL clients, ALL banks, ALL months. If the rule mentions a specific name → it is WRONG.
6. **When fixing a DBF write bug** — create a manual Miracle entry first, compare field-by-field.
7. **When adding a new module** — check if the Recalculate button visibility needs updating in `app.js`.
8. **When changing PDF processing** — always keep chunks sequential (not concurrent) for Bank Statements. Implement recursive self-correcting split-on-failure: date-gap OR balance mismatch triggers split.
9. **When adding a new group classification** — add to BOTH `create_party_ledger()` AND the Gemini prompt rules.
10. **Always write narration to TWO fields**: `FIELD82` (50 chars) and `T40F02` (full).
11. **When parsing Excel statement files** — always process row ranges sequentially using `extract_excel_rows_recursive`. Date-gap check and math check both trigger recursive splits.
12. **In the mathematical validator** — never force a balance delta amount correction if discrepancy > 5.0. Instead, trigger a recursive split to find the missing rows.
13. **When adding new settings** — add the field to: (a) `SystemSettings` Pydantic model in `main.py`, (b) `default_settings` dict in `load_settings()`, (c) `saveSettings()` payload in `app.js`, (d) `loadSettingsFromServer()` in `app.js`, (e) settings modal in `index.html`. Pass the value to all relevant `GeminiService()` instantiation calls.
14. **Date parsing must always prioritize DD/MM (day-first) before MM/DD** — Indian standard. Use format order: `["%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y", "%Y/%m/%d"]`.
15. **After adding any feature** — update CHANGELOG.md (human log) AND this RULES BOOK (AI memory).
16. **Dynamic Surcharges & Miracle 9.070+ Database Compatibility**: Miracle 9.070+ replaces legacy hardcoded columns (like `EDVAS00095` for discounts, `EDVAS00097` for freight) with dynamic array-like slots (`ED00000001` - `ED00000008` in headers, `ID00000001` - `ID00000007` in item details). The slot assignment mapping is defined dynamically in the active year's `RKYRM45.DBF` table. Always query `RKYRM45.DBF` to resolve these slots before executing DBF writes, falling back to legacy hardcoded columns if dynamic fields are absent. Also check and write transporter details to native fields (`UTRANS`, `ULRNO`, `ULRDATE`) when present, falling back to older custom user columns (`U0000006`, `U0000005`).
17. **Explicit GST Rate Name Resolution & Commodity Protection**: If a product's name explicitly indicates a GST rate (e.g. `footwear Gst 0`, `FOOTWEAR GST 5%`, `Footwear Gst 18%`), this rate acts as the highest-priority override. During `get_product_master_gst_rate` and product creation/update, always parse and enforce this rate. In `get_or_create_product`, if the product has an explicit rate in its name, heal/align the database record (`M21F27` commodity code) to match the parsed rate. Otherwise, if no explicit rate exists in the name, protect existing configurations: only set the commodity if blank (`""`), and never overwrite `CNGT` or any other user-configured commodity code.
18. **Auto-Backup Optimization & Thread-Safe DB Writes**: To prevent race conditions, database lock contentions, or browser timeout retries during slow network zipping operations over SMB shares, the database write paths (`/api/push` and `/api/opening-balances/push`) must be thread-safe. Use a global threading lock (`db_write_lock`) to block concurrent requests from executing simultaneously. Furthermore, optimize directory zipping by passing `active_year_folder` to `backup_full_client_folder` and `zip_dir_resilient` to selectively prune the walked directory list in-place (`dirs[:]`) at the company root folder, zipping only company root configuration files and the active year directory, and skipping all other historical years completely.
19. **Line-Item Taxable/Discount Inversion Guard**: In invoice extraction (`gemini_service.py`), if Gemini returns inverted `taxable` and `discount` values for a line item (e.g. `discount > taxable` where `taxable + discount == qty * rate`), the system automatically detects the inversion and swaps `taxable` and `discount` back to their correct values before database insertion.
20. **Line-Item 0% GST Tax Field Clearing**: In DBF item voucher creation (`dbf_handler.py`), if a line item has `item_gst_pct == 0` or `item_gst == 0` (e.g. Footwear 0% GST or Exempt items), all line-item DBF tax fields (`IDGAS00001/2/3`, `IPGAS...`, `IAGAS...`) must be explicitly cleared to `0.0` and `''`, and `T02F97` set to `'02'` (Exempt) or `''`, ensuring Miracle Accounting respects the product master's 0% tax rate.
21. **Excel Multi-Item Header Forward-Filling & 100% Extraction Retention**: In tabular Excel extraction (`_clean_flat_data` in `gemini_service.py`), invoice header fields (`date`, `bill_no`, `party_name`, `party_gstin`) MUST be forward-filled (`ffill()`) prior to filtering or grouping. In standard accounting Excel exports (Tally/Miracle/Custom), multi-item vouchers only write header details on item row 1, leaving cells blank for rows 2+. Forward-filling prevents subsequent item rows from having `NaN` dates and getting dropped, ensuring 100% of rows (100+ entry files) are retained and grouped correctly into multi-item vouchers.
22. **Multi-Sheet Extraction & Subtotal Summary Row Filtering**: In Excel processing (`_clean_flat_data` in `gemini_service.py`), all valid tabular sheets (e.g. `B2B`, `B2C`, `CASH`, `Sale Report`) MUST be concatenated together into `df_flat` rather than selectively filtering for sheets with `'item'` in their tab name. Furthermore, embedded subtotal/summary rows (such as `Total for GST 0%`, `Subtotal`, `Grand Total`) must be explicitly filtered out (`is_summary_row`) to prevent summary rows from being misparsed as fake vouchers.
23. **User Guideline Sheet Targeting**: If the user inputs a specific sheet restriction in `Extra AI parsing guidelines (optional)...` (e.g. *"Read ONLY B2C sheet"* or *"Only process B2B"*), both the fast table engine (`parse_excel_to_json`) and the Gemini AI prompt MUST honor it. The fast table engine inspects `instruction` and filters `flat_sheets_data` to extract strictly the user's specified tab(s), skipping all unrequested tabs.
24. **Retention of Customer-Named Custom Line Items**: In custom manufacturing businesses (e.g. medical orthotics, footwear, custom apparel, jewelers, personal services), line items are frequently named directly after the patient/customer (e.g. Party = `'Somnath Yadav'`, Item = `'Somnath Yadav'`). The item extraction engine (`gemini_service.py`) MUST NOT drop items simply because `item_name == party_name`. Only drop items if `item_name` matches generic transaction keywords (`"sale"`, `"purchase"`, `"voucher"`, `"journal"`).
26. **Excel Numeric Serial Date Support**: In Excel parsing (`gemini_service.py`), numeric Excel serial dates (e.g. `45414.0`) MUST be converted using `pd.to_datetime(val, unit='D', origin='1899-12-30')` to prevent raw numeric strings from failing date parsing.
27. **Line-Item Penny Tax Reconciliation**: In DBF invoice creation (`dbf_handler.py`), line-item CGST, SGST, and IGST totals must be tracked across item rows and adjusted on the final line item (`round(header_tax - accumulated_line_tax, 2)`) to ensure `sum(line_item_taxes) == header_tax` to the exact 0.01 paise, preventing Miracle warning dialogs.
28. **Strict DBF String Field Width Truncation**: When assigning text fields in DBF files (`dbf_handler.py`), all string values must pass through `fit_dbf_str(val, max_len)` to safely limit string length to DBF schema byte bounds, preventing `DBFValueError` exceptions on long invoice numbers or party names.
29. **Financial Year Date Boundary Flagging**: In confidence scoring (`main.py`), voucher dates MUST be checked against the active financial year bounds (e.g. `YR26` = FY April 1, 2025 to March 31, 2026). Dates outside the FY range MUST be flagged as `"Date Outside FY ({year_folder})"` to warn users prior to DBF push.
30. **Dynamic Company State Code Auto-Detection**: Core engines (`gemini_service.py`, `main.py`) MUST auto-detect `company_state_code` dynamically from Miracle company setup tables (`handler.get_company_state_code()`), avoiding static `'24'` state code fallbacks.
31. **Universal Empirical Financial Year Bounds & Multi-Year Routing Engine**: Year folder date ranges must never be assumed from folder string math (`2000 + int(folder[2:])`). Instead, core engines (`dbf_handler.py`, `config.py`, `vouchers.py`) MUST empirically discover date bounds by scanning DBF tables (`RKACCT41.DBF`) in each year folder. Incoming vouchers are dynamically resolved to their target physical year folder on disk (`YR25`, `YR26`, `YR27`), multi-year voucher batches are automatically partitioned and injected into their respective year DBFs, and missing year folders are reported with clear actionable error messages.

---

## PART 9 — UNIVERSAL EXTRACTION VALIDATION CHECKLIST

After every extraction, these validations run automatically:

| # | Check | Triggers |
|---|---|---|
| 1 | Row-by-row balance math: `abs(abs(delta) - amount) > 5.0` | Recursive split of chunk |
| 2 | Date-gap continuity: consecutive rows > 28 days apart | Recursive split of chunk |
| 3 | Single page/row retry on failure | Up to 3 retries |
| 4 | Post-extraction date normalization | Every row, every client |
| 5 | Global date-gap audit | Warning log for any remaining gaps |
| 6 | Transaction type validator (`validate_and_fix_transaction_types`) | Auto-fix Receipt/Payment swaps |

---

## PART 10 — CLIENT-SPECIFIC NOTES

> ⚠️ This section is the ONLY place where client-specific information is allowed.
> All code, prompts, and rules MUST remain universal.

### General (All Clients)
- `neel`, `dhruv`, `dhure` in narration → always `SALARY` (configured salary employees for specific client — this is a client memory mapping, not a universal rule)
- Salary employees are NEVER a Loan or Expense

### CMP0002 (Personal Accounting Client)
- **Type:** Personal Accounting (NOT a business)
- **Active Year Folder:** YR26 (2025-2026)
- **Key Rule:** All human names → Loans & Advances or Unsecured Loans (NEVER Expenses)

---

*This document must be updated every time a new bug is found or a new rule is established.*
*Every rule added here must be UNIVERSAL — valid for all 100+ clients, all banks, all months.*
*When in doubt: CREATE A MANUAL ENTRY IN MIRACLE and compare the DBF fields.*
