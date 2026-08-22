---
name: miracle_accounting_automation
description: Instructions, architecture, and database schema for building and modifying the Miracle Accounting AI Auto-Entry web tool. Triggers when working on the Miracle integration project or DBF files.
---

# Miracle AI Auto-Entry Tool - System & Database Manual

> [!IMPORTANT]
> **CRITICAL INSTRUCTION FOR ALL AI AGENTS:** Before you make ANY code changes or solve ANY bug, you **MUST** read these files IN ORDER:
> 1. **`/Users/jaydevnakum/Work Place/WORK/APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/docs/AI_RULES.md`** — The 25 Smart Rules Protocol for AI Bug Resolution & Code Operations. **READ THIS FIRST.**
> 2. **`/Users/jaydevnakum/Work Place/WORK/APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/docs/AI_RULES_BOOK.md`** — The complete master rules book covering account group rules, Gemini prompt rules, DBF write flags, and feature-addition checklist.
> 3. **`/Users/jaydevnakum/Work Place/WORK/APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/docs/AI_HANDOFF.md`** — Original architecture and bug history for additional context.

This document serves as the absolute source of truth for the Miracle AI Auto-Entry application architecture, file schemas, backend APIs, and integration details.

---

## 1. Project Architecture

The system is a fully decoupled local desktop-style web application:
1. **Frontend**: HTML5/Vanilla JS/Tailwind CSS dashboard located in `/frontend/`.
   - `index.html`: Layout, settings modal, editable grid, and split-screen document viewer.
   - `app.js`: Connects to backend, manages state, renders grid, groups ledgers, and handles pushing staged entries.
2. **Backend**: FastAPI (Python) located in `/backend/main.py`.
   - `dbf_handler.py`: Reads and writes to legacy FoxPro `.DBF` database files using `dbfread` and `dbf` libraries.
   - `ai_memory.py`: Isolates client-specific AI memory (bank narration mappings, custom fields).
   - `gemini_service.py`: Uses Google Gemini API for multi-modal structured data extraction.
3. **Database Layer**: Directly reads and writes FoxPro `.DBF` files in the active client folder (e.g. `CMP0003/YR27`).

---

## 2. API Endpoints Reference

The FastAPI server runs by default on **`http://localhost:8000`**.

| Endpoint | Method | Description |
|---|---|---|
| `GET /api/settings` | GET | Returns system settings (`gemini_api_key`, `miracle_base_path`, `active_client_id`, `memory_path`) and auto-discovered clients. |
| `POST /api/settings` | POST | Saves new settings to `backend/settings.json` and updates the active client context. |
| `GET /api/clients` | GET | Lists all folders starting with `CMP` in the `miracle_base_path`. |
| `GET /api/ledgers` | GET | Reads the active client DBFs, automatically traces group hierarchy, and returns classified ledgers. |
| `GET /api/groups` | GET | Reads `RKACCM11.DBF` and returns all account groups with parent-child tree hierarchy and nature categories. |
| `POST /api/refresh-ledgers` | POST | Forces the backend to re-read and return fresh ledgers from DBFs. |
| `POST /api/push` | POST | Scrapes staged grid vouchers and writes them to the DBF files as double-entries. |

---

## 3. Account Group Hierarchy & Classification

To distinguish ledger roles, the system reads `RKACCM11.DBF` (group table) and recursively traces parent codes (`FIELD04`):

### Master Catalog of Miracle Standard Account Groups
* **Assets**:
  * `G0000003`: Current Assets (Parent of Bank `G0000004`, Cash `G0000005`, Debtors `G0000009`, Loans/Advances `G0000011`, Stock `G0000012`, Deposits `G0000018`)
  * `G0000006`: Fixed Assets (Computers, Machinery, Vehicles, Furniture)
  * `G0000007`: Investments (FD, Shares, Mutual Funds)
* **Liabilities & Capital**:
  * `G0000010`: Current Liabilities (Parent of Creditors `G0000013`, Duties & Taxes `G0000014`, Provisions `G0000015`)
  * `G0000001`: Capital Account (Partner/Proprietor Capital, Drawings)
  * `G0000002`: Loans (Liability) (Parent of Bank OD/CC `G0000016`, Secured Loans `G0000017`, Unsecured Loans `G0000020`)
* **Incomes & Expenses**:
  * `G0000021`: Sales Accounts (Direct Income)
  * `G0000022`: Indirect Incomes (Interest, Discounts, Commission)
  * `G0000023`: Purchase Accounts / Direct Expenses (Freight, Customs, Labour, Raw Materials)
  * `G0000024`: Indirect Expenses (Rent, Salaries, Tea, Printing, Telephone, Bank Charges, Repairing)
* **Special Groups**:
  * `G0000028`: Suspense Account (Unidentified incoming/outgoing transactions)

### Default System Account Codes
* `AGST0001`: Sales Account (Local GST)
* `AGST0002`: Sales Account (Inter-State IGST)
* `AGST0003`: Purchase Account (Local GST)
* `AGST0004`: Purchase Account (Inter-State IGST)
* `AGST0005`: CGST Input Account
* `AGST0006`: SGST Input Account
* `AGST0007`: IGST Input Account
* `AGST0008`: CGST Output Account
* `AGST0009`: SGST Output Account
* `AGST0010`: IGST Output Account
* `AVAUTO99`: Round-off Account

---

## 4. Miracle DBF Write Schema

Vouchers are written into two tables in the active year directory (e.g. `CMP0003/YR27`):

### A. Voucher Headers (`RKACCT41.DBF`)
* **`FIELD98` & `FIELD99`**: Alphanumeric prefix (`SS` = Sales, `PP` = Purchases).
* **`FIELD01`**: Unique 12-char ID (e.g. `SS` + 10-char random alphanumeric).
* **`FIELD02`**: Date (Datetime object).
* **`FIELD03`**: Voucher index (`5` for Sales, `6` for Purchases).
* **`FIELD04`**: Party Ledger Code (e.g. `AYECD7E8`).
* **`FIELD05`**: Purchase/Sales Account Code (e.g. `AGST0001` or `AGST0003`).
* **`FIELD06`**: Total invoice amount.
* **`FIELD07`**: Taxable amount.
* **`FIELD10`**: Purchase Invoice No (Purchases only).
* **`FIELD11`**: Purchase Invoice Date (Purchases only).
* **`FIELD12`**: Sales Bill No (Sales only).
* **`FIELD16`**: `'D'` (Debit indicator).
* **`FIELD21`**: `'T'` (Tax Invoice).
* **`FIELD74`**: `'SP'` (Sales/Purchases).
* **`T41F45`**: Year suffix (e.g. `27` for YR27).
* **`EDGAS00001` & `EDGAS00002`**: CGST and SGST amounts.
* **`EDVAS00099`**: Round-off amount.
* **`EAVAS00099`**: `'AVAUTO99'` (Round-off code).
* **`U0000005`**: Vehicle Number (Custom field).
* **`U0000006`**: E-Way Bill Number (Custom field).

### B. Ledger Lines (`RKACCT01.DBF`)
Double-entry lines matching the Voucher ID (`FIELD01`):
1. **Party line**: Mapped to Party Code (`FIELD03`). Credit for Purchases, Debit for Sales. `FIELD21` = `'PR'`.
2. **Sales/Purchase line**: Mapped to Sales/Purchase Account (`FIELD03`). Debit for Purchases, Credit for Sales. `FIELD21` = `'TP'` or `'TS'`.
3. **Tax lines**: Mapped to tax ledger codes (`AGST0005` - `AGST0010`). Debit for Purchases, Credit for Sales. `FIELD21` = `'TX'`.
4. **Round-off line**: Mapped to `AVAUTO99` (if ro != 0). `FIELD21` = `'PT'`.
