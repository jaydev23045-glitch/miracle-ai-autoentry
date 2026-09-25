---
name: miracle_accounting
description: Master manual for Miracle ERP AI Auto-Entry engine architecture, 6-stage intelligence pipeline, DBF database schemas, 3-tier routing, 7-check validators, 37 Smart Rules Protocol, and FastAPI endpoints.
---

# Miracle AI Auto-Entry Engine — Master Architecture & System Manual

> [!IMPORTANT]
> **MANDATORY SYSTEM DIRECTIVES FOR ALL AI AGENTS:**
> Before making ANY code changes or addressing any accounting issue in Miracle AI Auto-Entry, you **MUST** adhere to these foundational principles:
> 1. **Consult 37 Smart Rules Protocol**: Review `docs/AI_RULES.md` and `docs/AI_RULES_BOOK.md` before modifying ledger mapping, double-entry logic, or DBF writers.
> 2. **Never Hardcode Vendor Names to Ledgers**: Use the dynamic multi-stage pipeline (`ai_memory.py`, `ai_business_profiler.py`, `embedding_engine.py`).
> 3. **Enforce Directional & Nature Safeguards**: Never allow Payments to map to Credit-nature accounts or Receipts to Debit-nature accounts. Generic keywords (`CASH`, `COMPUTER`, `PETROL`, `RENT`) MUST NEVER map to trade Debtors or Creditors.

This document serves as the authoritative technical manual for the Miracle Accounting AI Auto-Entry system.

---

## 1. Core Architecture Overview

The system employs a high-performance decoupled architecture designed to run seamlessly on desktop environments and cloud platforms (e.g. Render 512 MB RAM ceiling):

```
[ Frontend: HTML5 / Vanilla JS / CSS3 ]
         │ (HTTP REST API with GZip compression)
         ▼
[ Backend: FastAPI Engine (Python) ]
   ├── routers/vouchers.py ──────► Document extraction, 3-tier routing & DBF push router
   ├── routers/settings.py ──────► Multi-client configuration & path management
   ├── gemini_service.py ────────► 6-Stage Intelligence Pipeline & AI Router
   ├── embedding_engine.py ──────► Zero-hardcode semantic vector matching (text-embedding-004)
   ├── validators.py ────────────► 7-Check Automated Accounting Quality Guard
   ├── ai_business_profiler.py ──► Auto-detects client industry & revenue drivers
   ├── party_extractor.py ───────► UPI/NEFT/IMPS/POS string cleaning & vendor extraction
   ├── ai_memory.py ─────────────► Historical RLHF memory bank with DR/CR directional keys & nature protection
   └── dbf_handler.py ───────────► FoxPro .DBF reader/writer (RKACCT41, RKACCT40, RKACCT01, RKACCGID)
```

---

## 2. Dynamic 6-Stage Mapping Pipeline

Every transaction narration passes through the **6-Stage Intelligence Pipeline** (`backend/modules/bank/parser.py` & `backend/transaction_classifier.py`):

```
Stage 1 : Memory Vault Hash Index Match O(1) ("DR:narration" or "CR:narration")
Stage 2 : 26-Category Heuristic Keyword Engine (Cash, Charges, Taxes, Loans, Expenses)
Stage 3 : Deterministic Bank Entity Subtraction NER (14-step narration cleaner)
Stage 4 : Token Intersection & Fuzzy Match against Master DBF (Jaccard score >= 0.85)
Stage 5 : Multimodal Gemini 2.5 AI Fallback (With Client Business Profile Context)
Stage 6 : Universal Suspense Routing & 80% Confidence Guard (Rule 32 -> G0000028 + Review Badge)
```

### 3-Tier Confidence Routing Rules
After stage processing, each voucher row is evaluated by `calculate_dynamic_accounting_confidence()` and assigned to a tier:

| Tier | Confidence Score | Status | Action |
|---|---|---|---|
| **Tier 1: Auto** | **Score ≥ 80%** | `"Auto"` | Approved for direct push to Miracle DBF books |
| **Tier 2: Review** | **Score 60–79%** | `"Review"` | Held in **Review Queue** for 1-click CA confirmation |
| **Tier 3: Suspense** | **Score < 60%** | `"Suspense"` | Reallocated to **Suspense Account** (`G0000028`), isolated from books |

---

## 3. Special Accounting Protocols (Smart Rules 34, 36, 37)

### Cash Sales & Cash Account Isolation Protocol (Rule 34)
All cash sales, cash purchases, or counter transactions (narrations/parties matching `CASH`, `COUNTER SALE`):
- Party code (`FIELD04` in `RKACCT41.DBF`) is set strictly to master `Cash Account` (`G0000005`).
- Vouchers set `FIELD16 = 'C'` (Cash transaction mode) and `T52F45 = 'S'` (Counter sale flag).
- Prohibits auto-creating fake parties named `Cash Sale` under Debtors/Creditors.

### Universal Inter-Bank Contra Identification Protocol (Rule 37)
Transfers between two internal Bank Accounts (`G0000004`):
- Header `FIELD98` / `FIELD99` set to `'BC'` (Bank Contra).
- Header `FIELD16` set to `'C'`.
- Both lines in `RKACCT01.DBF` set `FIELD21 = 'BK'` to update passbook reconciliation registers in Miracle UI.

### Master GUID Synchronization Across Financial Years (Rule 36)
When a new party ledger is created in `RKACCM01.DBF`:
- Registers a GUID record in `RKACCGID.DBF` with `FIELD04 = 'Y'` (25 characters padded).
- Syncs the ledger across all financial year directories (`YR27`, `YR26`, `YR25`), ensuring cross-year dropdown lookup visibility in Miracle Desktop UI.

### Cache Integrity Rules (Rules 38, 39, 40 — Added 2026-09-25)

**Rule 38 — Never Cache Empty Ledger Results (`dbf_handler.py`):**
- `_CROSS_YEAR_CACHE` in `MiracleDBFHandler.read_ledgers_all_years()` MUST NEVER store an empty `[]` result.
- Empty result = path was misconfigured. Caching it poisons all requests for 300 seconds.
- Fix: `if result: MiracleDBFHandler._CROSS_YEAR_CACHE[cache_key] = (now, result)`

**Rule 39 — Clear All Caches On Settings Change (`routers/settings.py`, `routers/vouchers.py`):**
- On every `POST /api/settings` that changes `miracle_base_path` OR `active_client_id`:
  - Call `_LEDGER_CACHE.clear()` (router-level 60s TTL cache)
  - Call `MiracleDBFHandler.clear_cross_year_cache()` (handler-level 300s TTL cache)
- A new `GET/POST /api/clear-cache` endpoint is available for manual flush from UI or tests.

**Rule 40 — Bank Ledger Filter Must Include G0000016 and All DBF-Classified Bank Ledgers (`frontend/app.js`):**
- The `NON_BANK_TERMS` exclusion list MUST use compound terms (`'BANK CHARGES'`, `'BANK INTEREST'`) NOT standalone terms (`'CHARGES'`, `'INTEREST'`) to avoid false-negative exclusions.
- The bank filter return condition MUST include `grp === 'G0000016'` (Bank Accounts alternate group) alongside `grp === 'G0000004'`.
- Any ledger with `classification === 'Bank'` from DBF group walk in `classify_group()` is authoritative and must be accepted.

---

## 4. The 7-Check Automated Accounting Validator (`validators.py`)

Prior to writing any voucher into Miracle DBF files, `AccountingValidator` executes 7 quality checks:

1. **Double-Entry Direction Check**:
   - `Payment` -> Must be Debit-nature (`EXPENSE`, `ASSET`, `CREDITOR`). Credit-nature maps fail.
   - `Receipt` -> Must be Credit-nature (`INCOME`, `LIABILITY`, `DEBTOR`). Debit-nature maps fail.
2. **Amount Anomaly Check**: Flags transactions > 5x historical average.
3. **Frequency Spike Check**: Flags batches with 20+ transactions mapped to single ledger.
4. **Statement Math Check**: Verifies `Opening + Receipts - Payments == Closing` (tolerance ₹1.00).
5. **GST Consistency Check**: Flags tax/GST narrations mapped to non-tax ledgers.
6. **Peer Consistency Check**: Cross-checks mappings against industry context.
7. **Extreme Amount Check**: Flags single vouchers > ₹10 Crore.

---

## 5. API Endpoints Reference

Backend runs on `http://localhost:8000`:

| Endpoint | Method | Description |
|---|---|---|
| `GET /health` | GET | Live RAM usage (MB) and server health metrics. |
| `POST /api/admin/gc` | POST | Forces Python garbage collection pass to free RAM. |
| `GET /api/settings` | GET | Returns active client ID (`CMPxxxx`), base directory, and model status. |
| `POST /api/settings` | POST | Updates and saves application settings to `settings.json`. |
| `GET /api/clients` | GET | Auto-discovers client directories (`CMP0001` - `CMP9999`). |
| `GET /api/ledgers` | GET | Reads active client DBF ledgers (`RKACCM01.DBF`) across multi-year paths. |
| `GET /api/groups` | GET | Reads group hierarchy from `RKACCM11.DBF`. |
| `POST /api/analyse-business` | POST | Runs AI Business Profiler on client DBF history. |
| `POST /api/upload-document` | POST | Ingests PDF/Excel, runs 6-stage mapping, 3-tier router, and 7-check validator. |
| `POST /api/export-audit-csv` | POST | Generates downloadable CSV audit trail for voucher batch. |
| `POST /api/resolve-suspense` | POST | Re-evaluates Suspense vouchers using user instructions. |
| `POST /api/push` | POST | Writes validated vouchers into Miracle DBF files (`RKACCT41.DBF`, `RKACCT40.DBF`, `RKACCT01.DBF`). |

---

## 6. Miracle DBF Database File Specifications

### Voucher Headers (`RKACCT41.DBF` & `RKACCT40.DBF`)
- **`FIELD01`**: 12-char unique Voucher ID (`SS` prefix + 10-char alphanumeric).
- **`FIELD02`**: Date (`Datetime` format).
- **`FIELD03`**: Voucher Type (`1` = Receipt, `2` = Payment, `5` = Sales, `6` = Purchase).
- **`FIELD04`**: Party Ledger Code (e.g. `AYECD7E8`).
- **`FIELD05`**: Account Code (Bank / Cash / Sales / Purchase).
- **`FIELD06`**: Total Voucher Amount.
- **`FIELD07`**: Taxable Amount.
- **`FIELD10`/`FIELD11`**: Supplier Bill No & Bill Date.
- **`FIELD12`**: Customer Sales Invoice No.
- **`FIELD16`**: Debit/Credit Indicator (`'D'` or `'C'`).
- **`FIELD82`**: Short 50-char narration string in `RKACCT41.DBF` (Smart Rule 8).
- **`T40F02`**: Unlimited memo narration string in `RKACCT40.DBF` (Smart Rule 8).

### Ledger Lines (`RKACCT01.DBF`)
Linked to `RKACCT41.DBF` via `FIELD01`:
1. **Party Line**: Counterparty ledger code.
2. **Account Line**: Revenue / Expense / Asset ledger code.
3. **Tax Lines**: GST ledgers (`AGST0005` - `AGST0010`).
4. **Round-Off Line**: Rounding ledger (`AVAUTO99`).
5. **Bank Contra Flag**: `FIELD21 = 'BK'` for internal bank transfers (Smart Rule 37).
