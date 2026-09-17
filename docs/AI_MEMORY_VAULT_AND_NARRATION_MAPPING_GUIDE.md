# 🧠 Deep-Dive Guide: AI Memory Vault & AI Narration Mapping Engine

> **Target Audience**: Core System Engineers, AI Developers, Accounting Integrators.  
> **Purpose**: Provide a step-by-step, line-by-line explanation of how the **AI Memory Vault** functions and how **AI Narration Mapping** classifies bank transactions into Miracle Accounting ledgers with 100% precision.

---

## 📋 Table of Contents
1. [Part I: AI Memory Vault (`AI_Memory_Vault/`) — Complete Architecture](#1-part-i-ai-memory-vault-ai_memory_vault--complete-architecture)
   - 1.1 [Purpose & Multi-Tenant Isolation](#11-purpose--multi-tenant-isolation)
   - 1.2 [File Path Fingerprinting (`_get_file_path`)](#12-file-path-fingerprinting-_get_file_path)
   - 1.3 [4-Tier Resilient Memory Loader (`load_memory`)](#13-4-tier-resilient-memory-loader-load_memory)
   - 1.4 [Thread-Safe Locking & 60-Second Monotonic Cache](#14-thread-safe-locking--60-second-monotonic-cache)
   - 1.5 [Mapping Key Purification (`clean_mapping_key`)](#15-mapping-key-purification-clean_mapping_key)
   - 1.6 [Indian Accounting Nature Classification & Illegal Mapping Guard](#16-indian-accounting-nature-classification--illegal-mapping-guard)
   - 1.7 [Vault Purification & Redundancy Pruning (`prune_mappings`, `rebuild_memory_keys`)](#17-vault-purification--redundancy-pruning-prune_mappings-rebuild_memory_keys)
   - 1.8 [Full Function API Reference (`ai_memory.py`)](#18-full-function-api-reference-ai_memorypy)
2. [Part II: AI Narration Mapping & Transaction Classification Engine](#2-part-ii-ai-narration-mapping--transaction-classification-engine)
   - 2.1 [Overview of the 6-Stage Ledger Mapping Pipeline](#21-overview-of-the-6-stage-ledger-mapping-pipeline)
   - 2.2 [Stage 1: Memory Vault Hash Index Match $O(1)$](#22-stage-1-memory-vault-hash-index-match-o1)
   - 2.3 [Stage 2: 26-Category Heuristic Keyword Engine](#23-stage-2-26-category-heuristic-keyword-engine)
   - 2.4 [Stage 3: Deterministic Bank Entity Subtraction NER](#24-stage-3-deterministic-bank-entity-subtraction-ner)
   - 2.5 [Stage 4: Token Intersection & Fuzzy Match against Master DBF](#25-stage-4-token-intersection--fuzzy-match-against-master-dbf)
   - 2.6 [Stage 5: Multimodal Gemini 2.5 AI Fallback](#26-stage-5-multimodal-gemini-25-ai-fallback)
   - 2.7 [Stage 6: Universal Suspense Routing & 80% Confidence Guard](#27-stage-6-universal-suspense-routing--80-confidence-guard)
3. [Part III: Special Accounting Protocols](#3-part-iii-special-accounting-protocols)
   - 3.1 [Cash Sales & Cash Account Isolation Protocol](#31-cash-sales--cash-account-isolation-protocol)
   - 3.2 [Universal Inter-Bank Contra Identification Protocol](#32-universal-inter-bank-contra-identification-protocol)
   - 3.3 [Master GUID Synchronization Across Financial Years](#33-master-guid-synchronization-across-financial-years)
   - 3.4 [1-Click UI Suspense Resolution & Memory Sync](#34-1-click-ui-suspense-resolution--memory-sync)

---

## 1. Part I: AI Memory Vault (`AI_Memory_Vault/`) — Complete Architecture

Located in [`backend/ai_memory.py`](file:///Users/jaydevnakum/Work%20Place/WORK/APP%20DETAILS/Mirracle%20Auto%20Entre%20Sale%20or%20Purchase%20or%20Bank/backend/ai_memory.py).

### 1.1 Purpose & Multi-Tenant Isolation
The **AI Memory Vault** is a persistent JSON-based learning store that isolates intelligence per client company (`CMPxxxx`). 

In multi-client accounting firms, Client A (`Jayesh Traders - CMP0005`) and Client B (`Raju Manufacturing - CMP0005`) might share the same folder code (`CMP0005`) under different company paths. The Memory Vault guarantees **100% collision-proof isolation** so that learned vendor mappings, tax preferences, and ledger rules never spill over between clients.

---

### 1.2 File Path Fingerprinting (`_get_file_path`)

```python
def _get_file_path(self, client_id: str, tenant_id: str = None, miracle_base_path: str = "", company_name: str = "") -> str:
```

To prevent data pollution across clients, the file path generator creates a fingerprint combining:
1. `tenant_id` (Sanitized alphanumeric string)
2. `company_name` (First 20 sanitized characters, e.g. `jayeshtraders`)
3. `client_id` (Folder code, e.g. `CMP0005`)
4. `miracle_base_path` MD5 Hash (First 8 characters of path hash)

**Generated File Pattern**:
`AI_Memory_Vault/tenant1_jayeshtraders_cmp0005_a8f3e2b1_memory.json`

---

### 1.3 4-Tier Resilient Memory Loader (`load_memory`)

When a client selects or opens a company, `load_memory()` attempts to load memory through 4 resilient fallback tiers:

```
                  ┌─────────────────────────────────────────────────────────┐
                  │ 1. Tier 1: Exact Match (Tenant + Company + CMP + Hash)  │
                  └────────────────────────────┬────────────────────────────┘
                                               │ Not Found?
                                               ▼
                  ┌─────────────────────────────────────────────────────────┐
                  │ 2. Tier 2: Tenant + CMP + Path Hash                     │
                  └────────────────────────────┬────────────────────────────┘
                                               │ Not Found?
                                               ▼
                  ┌─────────────────────────────────────────────────────────┐
                  │ 3. Tier 3: Path Migration Protection (Finds previous    │
                  │            memory if Miracle path changed on disk)      │
                  └────────────────────────────┬────────────────────────────┘
                                               │ Not Found?
                                               ▼
                  ┌─────────────────────────────────────────────────────────┐
                  │ 4. Tier 4: Standard CMP ID Fallback (CMP0005_memory.json│
                  └─────────────────────────────────────────────────────────┘
```

---

### 1.4 Thread-Safe Locking & 60-Second Monotonic Cache

To prevent file corruption during high-concurrency REST API calls over network shares (SMB/LAN):
- **Per-Client Thread Lock (`_get_client_lock`)**: Every file read and write operation is wrapped in a dedicated `threading.Lock()` keyed by `client_id`.
- **In-Process Cache (`_memory_cache`)**: Loaded JSON structures are cached in RAM with a **60-second TTL** (`time.monotonic()`). Subsequent reads within 60 seconds return instant in-memory copies without touching the disk.
- **Atomic File Writes (`save_memory`)**: Memory updates are written to a `.tmp` scratch file first and then atomically swapped using `os.replace(temp_path, file_path)`.

---

### 1.5 Mapping Key Purification (`clean_mapping_key`)

Raw bank narrations contain noise (UTRs, IFSC codes, UPI handles, dates, cities, transaction prefixes). `clean_mapping_key(narration)` cleans raw narrations into stable core keywords using a 14-step filter:

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

### 1.6 Indian Accounting Nature Classification & Illegal Mapping Guard

To prevent illegal accounting entries (e.g., mapping personal expenses to trade vendors), `AIMemoryVault` enforces statutory nature rules under ICAI, Ind AS, and Section 37(1) of the Income Tax Act:

#### Nature Categories (`classify_indian_accounting_nature`)
* **`PERSONAL_DRAWINGS`**: (`MOM`, `WIFE`, `LIC`, `SCHOOL FEES`, `GROCERY`) $\rightarrow$ Mapped to `Capital Account / Drawings`.
* **`FIXED_ASSETS`**: (`COMPUTER`, `LAPTOP`, `AC`, `MACHINERY`, `VEHICLE`) $\rightarrow$ Mapped to `Fixed Assets` (AS-10 / Ind AS 16).
* **`DUTIES_AND_TAXES`**: (`GST`, `TDS`, `INCOME TAX`, `CHALLAN`, `PTAX`) $\rightarrow$ Mapped to `Duties & Taxes`.
* **`INDIRECT_EXPENSES`**: (`RENT`, `SALARY`, `PETROL`, `TEA`, `PARKING`, `REPAIR`) $\rightarrow$ Mapped to `Indirect Expenses`.
* **`BANK_CHARGES`**: (`SMS CHARGES`, `SERVICE CHARGE`, `MDR RECOVERY`) $\rightarrow$ Mapped to `Indirect Expenses`.

#### Nature Enforcement Guard (`is_illegal_nature_mapping`)
If a user tries to map a key illegally (e.g. key = `COMPUTER` mapped to party `MITESHBHAI` or key = `CASH` mapped to `RADHE KRISHNA TRADERS`), `is_illegal_nature_mapping()` returns `True` and blocks/purges the entry from memory!

---

### 1.7 Vault Purification & Redundancy Pruning (`prune_mappings`, `rebuild_memory_keys`)

* **Redundancy Pruner (`prune_mappings`)**: If memory contains both `CRED` $\rightarrow$ `Cred Club Expense` and `CRED CLUB PAYMENTS` $\rightarrow$ `Cred Club Expense`, the pruner automatically deletes the redundant longer key because the shorter core key covers it.
* **Vault Purifier (`rebuild_memory_keys` / `purify_all_client_memories`)**: Retroactively re-scrubs existing client memory JSON files to purge stale numeric keys or illegal nature mappings.

---

### 1.8 Full Function API Reference (`ai_memory.py`)

| Function Name | Description | Key Parameters | Return Value |
|---|---|---|---|
| `load_memory()` | Loads client memory JSON using 4-tier fallback lookup. | `client_id`, `tenant_id`, `miracle_base_path` | `dict` |
| `save_memory()` | Prunes and saves memory atomically to disk with multi-tenant lock. | `client_id`, `memory_data` | `None` |
| `clean_mapping_key()` | 14-step filter to clean raw bank narrations into core search keys. | `narration: str` | `str` |
| `clean_mapping_value()` | Sanitizes mapped ledger names into Title-Cased human names. | `val: str` | `str` |
| `find_fast_keyword_expense_mapping()` | $O(1)$ hash table lookup for fast narration-to-ledger matching. | `client_id`, `raw_narration` | `(ledger_name, matched_key)` |
| `add_expense_mapping()` | Teaches AI a new single narration-to-ledger mapping rule. | `client_id`, `narration_keyword`, `ledger_name` | `None` |
| `batch_add_expense_mappings()` | Batch-writes multiple narration mappings in a single atomic disk operation. | `client_id`, `mappings: dict` | `None` |
| `delete_expense_mapping()` | Deletes a learned mapping key from memory. | `client_id`, `key: str` | `bool` |
| `classify_indian_accounting_nature()` | Categorizes narration keys by ICAI / Income Tax nature rules. | `clean_key: str` | `dict` |
| `is_illegal_nature_mapping()` | Blocks accounting rule violations (e.g. Personal $\rightarrow$ Trade Vendor). | `clean_key`, `ledger_val` | `bool` |
| `prune_mappings()` | Removes longer redundant keys if a shorter substring key exists. | `memory_data: dict` | `dict` |
| `rebuild_memory_keys()` | Retroactively cleans dirty/numeric/illegal keys in a client's memory. | `client_id: str` | `int` (changed count) |

---

## 2. Part II: AI Narration Mapping & Transaction Classification Engine

Located in [`backend/modules/bank/parser.py`](file:///Users/jaydevnakum/Work%20Place/WORK/APP%20DETAILS/Mirracle%20Auto%20Entre%20Sale%20or%20Purchase%20or%20Bank/backend/modules/bank/parser.py) and [`backend/transaction_classifier.py`](file:///Users/jaydevnakum/Work%20Place/WORK/APP%20DETAILS/Mirracle%20Auto%20Entre%20Sale%20or%20Purchase%20or%20Bank/backend/transaction_classifier.py).

### 2.1 Overview of the 6-Stage Ledger Mapping Pipeline

When a bank transaction line is processed, the system passes the narration through **6 Sequential Stages**:

```
[Raw Bank Narration]
        │
        ▼
 Stage 1: Memory Vault Hash Index Match ──(Match Found?)──> [100% Mapped]
        │ No
        ▼
 Stage 2: 26-Category Heuristic Engine ───(Rule Triggered?)─> [Category Group Assigned]
        │ No
        ▼
 Stage 3: Bank Entity Subtraction NER ────(Party Isolated?)─> [Clean Party Name]
        │
        ▼
 Stage 4: Token Intersection & Fuzzy Match (Master DBF) ───> [Ledger Code Assigned]
        │ Match < 80%?
        ▼
 Stage 5: Multimodal Gemini 2.5 AI Fallback ───────────────> [AI Recommendation]
        │ Confidence < 80%?
        ▼
 Stage 6: Suspense Account Routing Guard ──────────────────> [G0000028 + Review Badge]
```

---

### 2.2 Stage 1: Memory Vault Hash Index Match $O(1)$

1. Converts raw narration into `clean_k` using `clean_mapping_key()`.
2. Performs an $O(1)$ hash map lookup against `expense_mappings` in `CMPxxxx_memory.json`.
3. If matched, instantly assigns target ledger with **`confidence_score = 100`** and status **`Mapped`**.

---

### 2.3 Stage 2: 26-Category Heuristic Keyword Engine

Evaluates deterministic rules in [`backend/transaction_classifier.py`](file:///Users/jaydevnakum/Work%20Place/WORK/APP%20DETAILS/Mirracle%20Auto%20Entre%20Sale%20or%20Purchase%20or%20Bank/backend/transaction_classifier.py):

* **Cash Movement**: (`CASH DEPOSIT`, `ATM WDL`, `CASH WITHDRAWAL`) $\rightarrow$ `Cash in Hand` (`G0000005`).
* **Bank Charges**: (`MDR RCVRY`, `SMS CHG`, `ALERTCHG`, `PROCESSING FEE`, `CHQ BOUNCE`) $\rightarrow$ `Indirect Expenses` (`G0000024`).
* **Statutory Taxes**: (`GSTPMT`, `TDS`, `INCOME TAX`, `ADVANCE TAX`, `PROFESSIONAL TAX`) $\rightarrow$ `Duties & Taxes` (`G0000014`).
* **Secured / Unsecured Loans**: (`EMI`, `HOME LOAN`, `AUTO LOAN`, `DISBURS`) $\rightarrow$ `Secured Loans` (`G0000017`).
* **Investments**: (`MUTUAL FUND`, `GROWW`, `ZERODHA`, `SIP`, `FD`) $\rightarrow$ `Investments` (`G0000007`).
* **Direct Expenses**: (`FREIGHT`, `BHADA`, `LOADING`, `CUSTOMS`, `TRANSPORT`, `TPT`) $\rightarrow$ `Direct Expenses` (`G0000023`).
* **Indirect Expenses**: (`RENT`, `SALARY`, `TEA`, `PETROL`, `PARKING`, `REPAIR`, `PRINTING`) $\rightarrow$ `Indirect Expenses` (`G0000024`).

---

### 2.4 Stage 3: Deterministic Bank Entity Subtraction NER

Invokes `BankEntityRecognizer.extract_vendor_entity(narration)` in [`backend/modules/bank/parser.py`](file:///Users/jaydevnakum/Work%20Place/WORK/APP%20DETAILS/Mirracle%20Auto%20Entre%20Sale%20or%20Purchase%20or%20Bank/backend/modules/bank/parser.py):
- Uses regular expressions to subtract technical transaction mode, IFSC code, UTR numbers, VPA handles, dates, and city names.
- Isolates pure human/business party entities (e.g. `UPI/3049102/PATEL TRADERS/UTIB000012` $\rightarrow$ `Patel Traders`).

---

### 2.5 Stage 4: Token Intersection & Fuzzy Match against Master DBF

Compares the extracted party name against active client master ledgers in `RKACCM01.DBF`:
1. Calculates Jaccard token intersection score:
   $$\text{Score} = \frac{|\text{Tokens}_{\text{Narration}} \cap \text{Tokens}_{\text{Master Ledger}}|}{|\text{Tokens}_{\text{Master Ledger}}|}$$
2. If $\text{Score} \ge 0.85$, assigns the master ledger code with **`confidence_score = 90`**.

---

### 2.6 Stage 5: Multimodal Gemini 2.5 AI Fallback

For complex or ambiguous transactions, the system queries Google Gemini 2.5 API with strict JSON Schema constraints:
- Inputs: Transaction narration, payment direction, amount, and client master ledger tree.
- Output: Standard JSON response containing `recommended_ledger`, `account_group`, and `confidence_score`.

---

### 2.7 Stage 6: Universal Suspense Routing & 80% Confidence Guard

Obeys **Rule 32** of the 25 Smart Rules Protocol:
- If the final mapping confidence score is **$<80\%$**, or if the entity is generic (`CHEQUE DEPOSIT`, `CLEARING`, `NEFT`):
  1. Sets `party_code = 'G0000028'` (**Suspense Account**).
  2. Sets `confidence_score = 40`.
  3. Sets UI status badge to **`Review`** (Amber badge).
- **Zero Hallucination Guarantee**: AI never forces guesses for uncertain entries.

---

## 3. Part III: Special Accounting Protocols

### 3.1 Cash Sales & Cash Account Isolation Protocol (Rule 34)
All cash sales, cash purchases, or counter transactions (narrations/parties matching `CASH`, `COUNTER SALE`):
- Party code (`FIELD04` in `RKACCT41.DBF`) is set strictly to master `Cash Account` (`G0000005`).
- Vouchers set `FIELD16 = 'C'` (Cash transaction mode).
- Prohibits auto-creating fake parties named `Cash Sale` under Debtors/Creditors.

### 3.2 Universal Inter-Bank Contra Identification Protocol (Rule 37)
Transfers between two internal Bank Accounts (`G0000004`):
- Header `FIELD98` / `FIELD99` set to `'BC'` (Bank Contra).
- Header `FIELD16` set to `'C'`.
- Both lines in `RKACCT01.DBF` set `FIELD21 = 'BK'` to update passbook reconciliation registers in Miracle UI.

### 3.3 Master GUID Synchronization Across Financial Years (Rule 36)
When a new party ledger is created in `RKACCM01.DBF`:
- Registers a GUID record in `RKACCGID.DBF` with `FIELD04 = 'Y'` (25 characters padded).
- Syncs the ledger across all financial year directories (`YR27`, `YR26`, `YR25`), ensuring cross-year dropdown lookup visibility in Miracle Desktop UI.

### 3.4 1-Click UI Suspense Resolution & Memory Sync
In the frontend interface (`app.js`):
1. When an accountant clicks **Resolve Suspense** and picks/creates a ledger for an amber `Review` row:
2. The UI instantly updates `confidence_score = 100` and changes the badge to **`Mapped`** (Green badge).
3. Sends a REST API call to `/api/learn-mapping` which invokes `AIMemoryVault.add_expense_mapping()`.
4. The rule is permanently remembered for all future statement uploads!

---

*Document compiled & verified for the Miracle AI Auto-Entry Platform.*
