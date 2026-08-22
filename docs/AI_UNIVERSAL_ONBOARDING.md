<!--
╔══════════════════════════════════════════════════════════════════════════════════╗
║          MIRACLE AI AUTO-ENTRY — UNIVERSAL AI ONBOARDING FILE                  ║
║   READ THIS FILE ONCE COMPLETELY BEFORE TOUCHING ANY CODE IN THIS PROJECT      ║
║   This file works for: Claude, GPT-4, Gemini, Mistral, or any other AI API    ║
╚══════════════════════════════════════════════════════════════════════════════════╝
-->

# 🤖 MIRACLE AI AUTO-ENTRY — UNIVERSAL AI ONBOARDING FILE
### One-Time Reader | Works for ALL AI APIs

> **TO ANY AI READING THIS:**
> You are now the developer of the **Miracle AI Auto-Entry** platform.
> This is a web tool that reads bank statements, cash books, sales, and purchase
> invoices using Gemini AI, and pushes the extracted data directly into the
> **Miracle Accounting Software** DBF database files.
>
> Read this file from top to bottom — ONCE — and you will have 100% of the
> context needed to work on this project at the same quality as any previous AI.
> Do NOT start coding before finishing this file. Do NOT skip sections.

---

## SECTION 0 — YOUR IDENTITY IN THIS PROJECT

You are a **senior full-stack developer + accounting domain expert**.
You understand:
- Indian accounting practices (GST, bank reconciliation, debit/credit)
- Visual FoxPro DBF file format and the Miracle Accounting Software internal structure
- Python FastAPI backend + Vanilla JS frontend
- Google Gemini AI API integration

Your job: make the tool work correctly for **any client** (there are 100+ clients).
Every fix, rule, and feature you build must be **UNIVERSAL** — never specific to one client, one bank, or one month.

---

## SECTION 1 — PROJECT STRUCTURE

```
Project Root/
├── frontend/
│   ├── index.html       ← UI: modals, data grid, toolbar buttons, file upload
│   └── app.js           ← ALL JS logic: state management, grid rendering, API calls, push-to-Miracle
├── backend/
│   ├── main.py          ← FastAPI endpoints (the API surface — all routes here)
│   ├── dbf_handler.py   ← THE MOST CRITICAL FILE: all DBF read/write logic
│   ├── gemini_service.py← Gemini AI prompts, chunk logic, math validation, post-processing
│   ├── ai_memory.py     ← Per-client AI memory (expense mappings, business profile)
│   └── settings.json    ← Runtime config: API key, Miracle path, active client
├── AI_Memory_Vault/
│   └── {CLIENT_ID}_memory.json  ← Per-client memory file (auto-created)
├── docs/
│   ├── AI_RULES_BOOK.md         ← Detailed rules reference
│   ├── AI_UNIVERSAL_ONBOARDING.md ← THIS FILE
│   └── AI_HANDOFF.md            ← Original early bug history
└── CHANGELOG.md                 ← Human log of every fix ever made
```

**How to run the project:**
```bash
cd backend
source venv/bin/activate       # activate Python virtualenv
uvicorn main:app --reload      # start FastAPI backend on port 8000
# Open frontend/index.html in browser
```

---

## SECTION 2 — WHAT THIS TOOL DOES (End-to-End Flow)

```
USER uploads PDF/Excel file
        ↓
frontend/app.js → POST /api/extract
        ↓
backend/main.py → calls GeminiService.extract_data()
        ↓
gemini_service.py → splits file into chunks → calls Gemini API → validates math → returns JSON
        ↓
frontend shows data in editable grid (user can review/edit)
        ↓
USER clicks "Push to Miracle"
        ↓
frontend/app.js → POST /api/push-to-miracle
        ↓
backend/main.py → calls DBFHandler._inject_bank_statements() / _inject_sales() etc.
        ↓
DBFHandler writes directly to .DBF files in the client's Miracle folder
        ↓
User opens Miracle → sees the injected entries
```

**Supported modules:**
| Module | Extracts | Writes to |
|---|---|---|
| Bank Statements | Bank transactions (date, amount, party, narration, balance) | T41 (BR/BP/CV) + T01 + T40 |
| Cash Entries | Cash receipts/payments | T41 (CR/CP/CV) + T01 + T40 |
| Sales | Invoice line items with GST | T41 (SS) + T01 + T02 + T52 |
| Purchases | Purchase invoice line items with GST | T41 (PP) + T01 + T02 + T52 |

---

## SECTION 3 — MIRACLE DBF FILES (Know These by Heart)

| File | What It Stores | Key Fields |
|---|---|---|
| `RKACCM01.DBF` | Party Ledger master (every account's name & code) | `FIELD01`=code, `FIELD02`=name, `FIELD04`=group |
| `RKACCM11.DBF` | Account Groups (Expenses, Income, Bank, Debtors...) | `FIELD01`=group_code, `FIELD02`=group_name |
| `RKACCT41.DBF` | Voucher headers (one row per voucher) | `FIELD98`=type, `FIELD01`=ID, `FIELD02`=date, `FIELD04`=party, `FIELD05`=bank/cash, `FIELD06`=amount |
| `RKACCT01.DBF` | Double-entry line items (2+ rows per voucher) | `FIELD98`=type, `FIELD01`=voucher_id, `FIELD03`=ledger, `FIELD06`=Dr/Cr, `FIELD21`=classification |
| `RKACCT40.DBF` | Narration memo store (unlimited text) | `T40F01`=voucher_id, `T40F02`=full_text |
| `RKACCT02.DBF` | Sales/Purchase line items (qty, rate, HSN) | Per invoice line |
| `RKACCT52.DBF` | GST summary (links to GSTR) | `T52F30`=book_type |
| `RKACCGID.DBF` | GUID registry (Miracle's internal tracking) | Must register every new voucher ID |

---

## SECTION 4 — CRITICAL DBF FIELD VALUES (The Most Common Bug Source)

### 4A — Voucher Type Codes (`FIELD98` in T41 and T01)
| Code | Module | Meaning |
|---|---|---|
| `BR` | Bank | Bank Receipt — money coming INTO the bank |
| `BP` | Bank | Bank Payment — money going OUT of the bank |
| `CV` | Bank+Cash | Contra Voucher — cash ↔ bank transfer (ATM, deposit) |
| `CR` | Cash | Cash Receipt — cash coming in |
| `CP` | Cash | Cash Payment — cash going out |
| `SS` | Sales | Sales voucher |
| `PP` | Purchases | Purchase voucher |

### 4B — T41 `FIELD16` (Voucher Direction — CRITICAL BUG SOURCE)
```
FIELD16 tells Miracle which form to open when user double-clicks the entry.
WRONG value = entry does not open in Miracle.
```
| Voucher Type | FIELD16 | ❌ Common Mistake |
|---|---|---|
| BR | `'R'` | — |
| CR | `'R'` | — |
| BP | `'P'` | — |
| CP | `'P'` | — |
| **CV (any direction)** | **`'C'`** | ❌ Writing `'R'` or `'P'` for CV |

**UNIVERSAL RULE: CV always gets `FIELD16 = 'C'` regardless of money direction.**

### 4C — T01 `FIELD21` (Line Classification — CRITICAL BUG SOURCE)
```
FIELD21 tells Miracle what kind of account this line represents.
WRONG value = entry does not open, or wrong account type shown.
```
| Line Type | FIELD21 |
|---|---|
| Bank ledger line (in BR/BP entry) | `'BK'` |
| Cash ledger line (in CR/CP entry) | `'CS'` |
| CV entry — Bank side of the line | `'BK'` |
| CV entry — Cash side of the line | `'CS'` |
| Party / Debtor / Creditor line | `'PR'` |
| Expense / Income / Other ledger | `'PT'` |
| T41 voucher header FIELD21 | `'O'` |

**UNIVERSAL RULE: CV Cash party → `'CS'`. CV Bank party → `'BK'`. Never `'PT'` for bank/cash accounts.**

### 4D — T01 `FIELD20` and `T01F96` (Balance Flags — Bug #17)
```
WRONG flags cause Miracle to EXCLUDE entries from balance calculations → closing balance never changes.
```
| Field | CORRECT value | WRONG value (old bug) | Effect of wrong value |
|---|---|---|---|
| `FIELD20` | `'N'` (Normal) | `'C'` (Cleared) | Miracle skips in balance calc |
| `T01F96` | `'G'` (General) | `'N'` | Entry excluded from balance sheet |

**UNIVERSAL RULE: All bank/cash T01 lines must have `FIELD20='N'` and `T01F96='G'`.**

### 4E — T41 Narration Fields
```
ALWAYS write narration to BOTH fields. Never only one.
```
| Field | Location | Length | Content |
|---|---|---|---|
| `FIELD82` | RKACCT41 | First 50 chars | Short header (Miracle's search index) |
| `T40F02` | RKACCT40 | Unlimited | Full narration text |

### 4F — Sales/Purchase Flags (Rule 4.1)
When writing `RKACCT02.DBF`:
- `FIELD04`: `'N'` = Purchases, `'I'` = Sales
- `FIELD05`: `'C'` = Purchases, `'D'` = Sales

When writing `RKACCT52.DBF`:
- `T52F22`: `'C'` = Purchases, `'D'` = Sales
- `T52F30`: `'4'` = Purchase Book, `'3'` = Sales Book

### 4G — Year Number
```python
year_num = int(year_folder[-2:])  # "YR26" → 26, "YR27" → 27
```
Write to `T41F45` (T41) and `T01F45` (T01). Wrong value = data goes to wrong fiscal year.

---

## SECTION 5 — ACCOUNT GROUPS (Classification Rules)

### NEVER hardcode group codes
Each client's Miracle has different group codes for the same logical group.
Always query `RKACCM11.DBF` dynamically using `find_group_by_name()` in `create_party_ledger()`.

### Search Patterns by Group Name
| Logical Group | Search Keywords in RKACCM11 | Fallback |
|---|---|---|
| Indirect Expenses | `EXPENSE ACCOUNT`, `INDIRECT EXPENSE`, `EXPENSE` | G0000017 |
| Direct Expenses | `EXPENSES (DIRECT)`, `DIRECT EXPENSE` | G0000014 |
| Indirect Income | `INCOME (OTHER THEN SALES)`, `INDIRECT INCOME` | G0000016 |
| Sundry Debtors | `SUNDRY DEBTORS`, `DEBTOR`, `CUSTOMER` | G0000009 |
| Sundry Creditors | `SUNDRY CREDITORS`, `CREDITOR`, `SUPPLIER` | G0000013 |
| Bank Accounts | `BANK ACCOUNTS (BANKS)`, `BANK ACCOUNTS`, `BANKS` | G0000004 |
| Loans & Advances (Asset) | `LOANS & ADVANCES (ASSET)`, `LOANS & ADVANCES` | G0000007 |
| Unsecured Loans (Liability) | `UNSECURED LOANS`, `UNSECURED` | G0000019 |
| Capital Account | `CAPITAL ACCOUNT`, `CAPITAL` | G0000001 |
| Fixed Assets | `FIXED ASSETS`, `FIXED ASSET` | G0000006 |
| Suspense Account | `SUSPENSE ACCOUNT`, `SUSPENSE` | G0000028 |

### Personal vs Business Accounting Decision
The `business_profile` field in the client's memory JSON distinguishes:

| Party type | Money OUT → | Money IN → |
|---|---|---|
| Individual person (no business keywords in name) | `Loans & Advances (Asset)` | `Unsecured Loans` |
| Business / Company / Vendor | `Sundry Creditors` | `Sundry Debtors` |
| Any party with expense keyword in UPI suffix | `Indirect Expenses` | `Indirect Expenses` |
| Name contains BANK / HDFC / SBI / ICICI | `Bank Accounts` | `Bank Accounts` |
| Name contains SUSPENSE | `Suspense Account` | `Suspense Account` |
| CASH in name | `CV` Contra Voucher | `CV` Contra Voucher |

**Person is NEVER an Expense or Income. Person is always a Loan.**

---

## SECTION 6 — GEMINI AI EXTRACTION RULES (gemini_service.py)

These rules are in the system prompt sent to Gemini. They are UNIVERSAL.

### Rule A — Complete Row Extraction
```
CRITICAL: Extract EVERY SINGLE transaction row on every page, line-by-line.
DO NOT skip any rows, pages, or periods (months/weeks).
DO NOT output Opening Balance or Closing Balance rows as transactions.
```

### Rule B — Universal Date-Gap Rule (Anti-Skip Rule)
```
CRITICAL — NO DATE GAPS ALLOWED:
If in your output two consecutive transactions are more than 25 days apart,
that is a FAILURE. It means you silently skipped transactions between them.
Re-scan the pages and find all missing rows.
This rule applies to ANY months and ANY clients — not specific to any month.
```
> This rule is enforced in code too: `verify_chunk_math()` checks date gaps > 28 days
> and triggers recursive split if found.

### Rule C — Indian Date Format (Universal for All Indian Banks)
```
ALL dates in Indian bank statements use DD/MM/YY or DD/MM/YYYY format.
NEVER interpret as American MM/DD/YY format.
Examples:
  26/06/25 = 26th June 2025 → output 2025-06-26
  01/07/25 = 1st July 2025  → output 2025-07-01
  07/01/25 = 7th Jan 2025   → output 2025-01-07
Always output dates in ISO YYYY-MM-DD format.
```

### Rule D — UPI Description Parsing
```
UPI transactions follow 3-part format: UPI-[PARTY NAME]-[PURPOSE]@[BANK]
  - If PURPOSE is an expense keyword (milk, food, petrol, salary, rent,
    electricity, medicine, recharge, insurance, repair, water, gas,
    school, fees) → mapped_ledger = expense type, NOT person name
  - Otherwise → mapped_ledger = clean party name (strip UPI- prefix and @bank suffix)
```

### Rule E — Bank Name Extraction
```
Extract ONLY the short brand name from bank headers.
HDFC Bank Ltd. → "HDFC Bank"
State Bank of India → "SBI"
```

---

## SECTION 7 — PDF/EXCEL CHUNK EXTRACTION ALGORITHM

### Dynamic Chunk Sizing (Strategy B — all clients)
```python
if total_pages <= 20:  chunk_size = 3   # maximum accuracy
elif total_pages <= 50: chunk_size = 5  # balanced
else:                   chunk_size = 10 # speed for dense files
```

### Sequential Processing (NEVER concurrent)
Chunks processed one by one. After each chunk:
- Extract closing balance
- Inject as context into next chunk's prompt: `"PREVIOUS BALANCE CONTEXT: ₹X"`

### Recursive Split-on-Failure Algorithm
```
extract_pdf_pages_recursive(start_page, end_page, opening_balance):
    1. Extract chunk via Gemini API
    2. Run verify_chunk_math(extracted_rows, opening_balance, pages_count):
         Check 1: row-by-row balance: abs(abs(delta) - amount) > 5.0 → FAIL
         Check 2: date-gap: consecutive rows > 28 days apart AND pages > 1 → FAIL
    3. If FAIL and pages > 1:
         mid = (start + end) / 2
         left_result  = extract_pdf_pages_recursive(start, mid, opening_balance)
         right_result = extract_pdf_pages_recursive(mid+1, end, left_result.closing_balance)
         return combine(left_result, right_result)
    4. If FAIL and pages == 1:
         retry up to 3 times
    5. If PASS: return extracted_rows
```
Same algorithm exists for Excel: `extract_excel_rows_recursive(start_row, end_row, ...)`

### Rate Limiting (API key type)
```python
if is_paid_api_key:
    time.sleep(0.2)   # Paid tier: no RPM limit → 10x faster
else:
    time.sleep(4.5)   # Free tier: 15 RPM limit → must wait
```
Setting stored in `settings.json` as `is_paid_api_key`.

---

## SECTION 8 — POST-EXTRACTION VALIDATIONS (All Automatic)

After Gemini returns results, these run in order:

| Step | What Runs | Purpose |
|---|---|---|
| 1 | `verify_chunk_math()` (per chunk) | Balance math + date-gap → triggers recursive split |
| 2 | Date normalization pass (all rows) | Force all dates to `YYYY-MM-DD` using `["%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y", "%Y/%m/%d"]` |
| 3 | Global date-gap audit (final output) | Log any remaining gaps > 28 days as `⚠️ [GLOBAL DATE-GAP AUDIT]` |
| 4 | `validate_and_fix_transaction_types()` | Sort by date → fix Receipt/Payment swaps using balance direction |

### validate_and_fix_transaction_types() logic:
```python
for each row (sorted by date):
    delta = current_balance - previous_balance
    if delta > 0 and type == "Payment":  → fix to "Receipt"
    if delta < 0 and type == "Receipt":  → fix to "Payment"
    if abs(amount - abs(delta)) > 5.0:   → also fix amount to abs(delta)
```

---

## SECTION 9 — YEAR FOLDER SELECTION

### Smart Folder Detection (never just pick alphabetically last)
```python
def get_latest_year_folder():
    # Miracle creates empty new year folders without DBF files → DO NOT use them
    # Priority:
    # 1. Latest folder with BOTH rkacct41.dbf AND rkacct01.dbf → return this
    # 2. Latest folder with rkacct41.dbf only → return this
    # 3. Alphabetically last → last resort fallback
```

### If DBF files are missing:
The push silently fails — no error, no data appears in Miracle.
**Fix:** User must open Miracle, switch to that year, create ONE manual entry.
This forces Miracle to generate the missing DBF files.

---

## SECTION 10 — DUPLICATE PREVENTION SYSTEM

The system prevents writing the same entry twice using 4-pass matching:

```
Pass 1: Exact Match (date + amount + party + bank + type + ref + narration)
Pass 2: Cheque/Reference Number Match (date + amount + bank + type + ref_no)
Pass 3: Party Match (date + amount + bank + type + party)
Pass 4: Amount Match (date + amount + bank + type)
```

Each match uses a `'used': True` flag to prevent one Miracle entry from
blocking multiple new entries with the same amount on the same date.

Also: **Intra-batch deduplication** — if the same row appears twice in the
same push call (from AI extracting duplicates), only the first is written.

---

## SECTION 11 — COMPLETE BUG HISTORY (All 24 Known Bugs)

This is the full list of every bug ever found and fixed. Understanding these
prevents you from re-introducing them.

| # | Bug Description | Root Cause | Fix |
|---|---|---|---|
| 1 | Purchases show red in Miracle | Used Sales flags for Purchases (RKACCT02/52) | FIELD04='N',FIELD05='C' for Purchases |
| 2 | Party ledger crash | Non-existent party code | create_party_ledger() safety |
| 3 | Balance math breaks on user edit | Browser drops `input` events on fast typing | Listen to input+change+keyup simultaneously |
| 4 | No manual recalculate | Missing button | Added Recalculate button in UI |
| 5 | Number input blue spinners | `<input type="number">` | Changed to `type="text"` + parseCurrency() |
| 6 | Narration truncated at 50 chars | Global `[:50]` slice applied before DBF write | Write FIELD82 (first 50) AND T40F02 (full) |
| 7 | Person names grouped as Expenses | Prompt bias toward Expense for personal accounting | Added PERSON exception rule in Gemini prompt |
| 8 | Recalculate button shown on Sales/Purchase modules | No visibility toggle by module | Added hidden class + module switch in app.js |
| 9 | Gemini skips pages in large PDFs | 25-page chunks exceed Gemini output token limit | Reduced to dynamic chunk sizes (3/5/10 pages) |
| 10 | Loans & Advances on both sides of Balance Sheet | All persons put in same Loans group regardless of direction | Receipt person → Unsecured Loans, Payment person → Loans & Advances |
| 11 | Withdrawal ↔ Deposit swapped | Gemini misreads column positions | validate_and_fix_transaction_types() post-processor |
| 12 | Page-boundary swap (same amount on both sides) | Concurrent chunks had no balance context between them | Sequential chunk processing + balance carryover prompt context |
| 13 | UPI expense purpose ignored | Only person name extracted, purpose (milk/petrol) lost | 3-part UPI parsing rule: `UPI-[WHO]-[WHAT]@[BANK]` |
| 14 | YR26 data not visible in Miracle | Missing rkacct41.dbf + wrong year selected by alphabetic sort | Smart `get_latest_year_folder()` with DBF existence check |
| 15 | Cross-year duplicate ledger creation | RKACCM01.DBF not synced — party created in YR25 missing in YR26 | `read_ledgers_all_years()` + `_sync_party_to_other_years()` |
| 16 | Bank brand duplicate ledger | "HDFC Bank Ltd." ≠ "HDFC BANK A/C" for substring match | 4-level matching: exact → substring → KNOWN_BANK_BRANDS keyword → fuzzy |
| 17 | Miracle closing balance never changes | `FIELD20='C'` (Cleared) + `T01F96='N'` → excluded from balance calc | `FIELD20='N'`, `T01F96='G'` for all bank/cash T01 lines |
| 18 | Wrong date parsing (2-digit year) | `%d/%m/%y` missing from format list; Indian DD/MM/YY misread as MM/DD/YY | Added `%d/%m/%y` and `%d-%m-%y` formats; added universal date normalization pass |
| 19 | Silent month/page skipping by Gemini | Gemini omits months; math check passes because coincidental balance match | Date-gap check (>28 days → recursive split) + Gemini prompt rule + global audit |
| 20 | HTTP timeout on long extractions | Single HTTP POST kept open during Gemini processing | `/api/upload-status` polling + `extraction_status.json` for real-time progress |
| 21 | Recursive split-on-failure missing | Fixed chunk sizes couldn't handle high-density pages | `extract_pdf_pages_recursive()` + `extract_excel_rows_recursive()` |
| 22 | Wrong date format (Indian standard) | No explicit prompt instruction for Indian banks | Added Indian date format rule to all Gemini prompts |
| 23 | Month skipping universal fix | Single-point fix | 3-layer fix: prompt + verify_chunk_math + global audit |
| 24 | CV Contra Voucher entries not openable | (a) FIELD16='R'/'P' for CV (must be 'C'); (b) FIELD21='PT' for cash/bank party (must be 'CS'/'BK') | `FIELD16='C'` for all CV; `FIELD21='CS'` for cash party; `FIELD21='BK'` for bank party |

---

## SECTION 12 — DEBUGGING CHECKLIST (When Miracle Doesn't Show Data)

Work through these steps IN ORDER when pushed data doesn't appear in Miracle:

```
Step 1 — Year folder
  ✓ Is the right YRxx selected?
  ✓ Does the folder have BOTH rkacct41.dbf AND rkacct01.dbf?
  → If not: user must open Miracle → switch year → create one manual entry

Step 2 — Year number in DBF
  ✓ T41F45 = int(year_folder[-2:])  e.g. "YR26" → 26
  → If wrong: entries go to wrong fiscal year and are invisible

Step 3 — Compare against a manual Miracle entry
  ✓ Create a manual entry of the same type in Miracle UI
  ✓ Read RKACCT41 + RKACCT01 with Python debug script
  ✓ Compare EVERY field against our injected entry
  → The discrepancy is the bug

Step 4 — Check RKACCGID.DBF
  ✓ Every new voucher and ledger must be registered in RKACCGID.DBF
  → Missing = Miracle silently ignores the entry

Step 5 — Sales/Purchase specific
  ✓ T52F30: '4' = Purchase Book, '3' = Sales Book
  ✓ T52F22: 'C' = Purchases, 'D' = Sales
  → Wrong value = entry appears in wrong book or shows as red text

Step 6 — Bank/Cash specific
  ✓ FIELD20 = 'N' (not 'C')
  ✓ T01F96 = 'G' (not 'N')
  ✓ FIELD16 = 'C' for CV, 'R' for Receipt, 'P' for Payment
  ✓ FIELD21 = 'BK' for bank line, 'CS' for cash line, 'PR' for party, 'PT' for expense
```

---

## SECTION 13 — HOW TO ADD NEW FEATURES (Universal Rules)

1. **Read SKILL.md, AI_RULES_BOOK.md, and this file FIRST.** Never code blind.
2. **Never hardcode group codes.** Always query RKACCM11.DBF dynamically.
3. **Never hardcode year numbers.** Always `int(year_folder[-2:])`.
4. **Never hardcode month names, client names, or bank names in ANY rule or prompt.**
   All rules must be universal and mathematical. If a rule says "October" → it is WRONG.
5. **When adding a Gemini prompt rule:** It must apply to ALL clients, ALL banks, ALL months.
6. **When fixing a DBF write bug:** Create a manual entry in Miracle first, compare field by field.
7. **When adding a new module:** Check if Recalculate button visibility needs updating in `app.js`.
8. **When changing PDF processing:** Always keep chunks SEQUENTIAL, never concurrent for Bank Statements.
9. **When adding a new group classification:** Add to BOTH `create_party_ledger()` AND the Gemini prompt.
10. **Always write narration to TWO fields:** `FIELD82` (50 chars) and `T40F02` (full).
11. **Date parsing format order** (always DD/MM before MM/DD — Indian standard):
    ```python
    ["%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y", "%Y/%m/%d"]
    ```
12. **When adding new settings:** Add to (a) SystemSettings Pydantic model, (b) default_settings,
    (c) saveSettings() in app.js, (d) loadSettingsFromServer() in app.js, (e) settings modal in index.html.
    Pass to all GeminiService() constructor calls.
13. **After any fix:** Update CHANGELOG.md (human log) AND AI_RULES_BOOK.md (AI memory).
14. **Universal philosophy:** Every change you make must prevent the bug class universally.
    Don't patch one case — patch the root cause so it never happens for any client.

---

## SECTION 14 — VALIDATION CHECKLIST (Run Before Every Push)

| # | Check | Code location |
|---|---|---|
| 1 | Row-by-row balance math per chunk | `verify_chunk_math()` in gemini_service.py |
| 2 | Date-gap continuity per chunk (>28 days = skip detected) | `verify_chunk_math()` in gemini_service.py |
| 3 | Single-page/row retry on failure (up to 3x) | `extract_pdf_pages_recursive()` |
| 4 | Post-extraction universal date normalization | After all chunks merged in gemini_service.py |
| 5 | Global date-gap audit of combined output | After normalization in gemini_service.py |
| 6 | Receipt/Payment type auto-correction | `validate_and_fix_transaction_types()` |

---

## SECTION 15 — CLIENT-SPECIFIC NOTES

> ⚠️ THIS SECTION IS THE ONLY PLACE WHERE CLIENT-SPECIFIC DATA IS ALLOWED.
> All code, prompts, functions, and rules MUST remain universal.

### Active Client: CMP0002
- Type: Personal accounting (NOT a business)
- All human names → `Loans & Advances` or `Unsecured Loans` (never Expenses)
- Active year: YR26 (2025-2026)
- Salary employees in narration (`neel`, `dhruv`, `dhure`) → always mapped to `SALARY`

### Gemini API Key Note
- Free tier: 15 RPM → 4.5 second sleep between chunks
- Paid tier (`is_paid_api_key=True` in settings): 0.2 second sleep → 10x faster

---

## SECTION 16 — QUICK REFERENCE: FIELD VALUES CHEAT SHEET

```
╔══════════════════════════════════════════════════════════════╗
║  T41 FIELD16 (Voucher direction — MOST COMMON BUG SOURCE)   ║
╠══════════════════════════════════════════════════════════════╣
║  BR/CR (Receipt)  →  'R'                                    ║
║  BP/CP (Payment)  →  'P'                                    ║
║  CV (Contra)      →  'C'  ← ALWAYS 'C', never 'R' or 'P'   ║
╠══════════════════════════════════════════════════════════════╣
║  T01 FIELD21 (Line classification)                          ║
╠══════════════════════════════════════════════════════════════╣
║  Bank ledger line (BR/BP/CV-bank side)  →  'BK'             ║
║  Cash ledger line (CR/CP/CV-cash side)  →  'CS'             ║
║  Party/Debtor/Creditor line             →  'PR'             ║
║  Expense/Income/Other ledger            →  'PT'             ║
║  T41 voucher header FIELD21             →  'O'              ║
╠══════════════════════════════════════════════════════════════╣
║  T01 FIELD20  →  'N' (Normal, always)                       ║
║  T01 T01F96   →  'G' (General, always for bank/cash)        ║
╠══════════════════════════════════════════════════════════════╣
║  T41 FIELD74  →  'CB' (Cash/Bank identifier, always)        ║
║  T41 FIELD21  →  'O' (always for voucher header)            ║
╠══════════════════════════════════════════════════════════════╣
║  RKACCT02 FIELD04: 'N'=Purchases, 'I'=Sales                 ║
║  RKACCT52 T52F30:  '4'=PurchaseBook, '3'=SalesBook          ║
║  RKACCT52 T52F22:  'C'=Purchases,  'D'=Sales                ║
╚══════════════════════════════════════════════════════════════╝
```

---

## SECTION 17 — HOW TO REPORT AND DOCUMENT BUGS

When you find and fix a bug, document it in BOTH files:

**In `CHANGELOG.md`:**
```markdown
### [Bug Number]. [Short Title]
**The Bug:** [What the user saw that was wrong]
**The Root Cause:** [The technical cause — specific field, line, function]
**The Fix:** [What was changed and why]
**Works for:** All clients, all banks, all [dates/months/amounts]
```

**In `AI_RULES_BOOK.md`:**
- Add a row to the Known Bugs table in Part 6
- Add or update the relevant universal rule in Parts 3/4/5

**Universal Philosophy to document:**
- State the ROOT CAUSE mathematically, not as a specific example
- State the fix as a universal rule, not a one-off patch
- Confirm: does this fix work for ALL clients? If not → fix is incomplete

---

*This file was last updated: 2026-07-17*
*Project: Miracle AI Auto-Entry Platform*
*Author: Antigravity AI (Claude Sonnet)*
*Read by: Any AI API assigned to work on this project*
