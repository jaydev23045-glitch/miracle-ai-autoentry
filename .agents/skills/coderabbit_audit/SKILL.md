---
name: coderabbit_audit
description: Automated line-by-line AI Code Reviewer & Security Auditor for Antigravity. Triggers when requested to review PRs, audit DBF file handles, inspect memory leaks, or verify bug fixes in Miracle AI Auto-Entry.
---

# CodeRabbit Automated AI Audit Protocol for Antigravity

> **Purpose**: Perform rigorous, line-by-line automated code auditing to detect DBF file handle locks, un-imported modules, floating-point precision flaws, unhandled API errors, RAM memory leaks, and violations of the 37 Smart Rules Protocol.

---

## 🔍 CodeRabbit Audit Checklist for Miracle AI Auto-Entry

When triggered, audit code changes against these core vulnerability patterns:

### 1. Log Inspection & Ground Truth (Smart Rules 1 – 5)
- **Rule 1 — Log-First Mandate**: Inspect full un-truncated error tracebacks before forming diagnostic hypotheses. Never guess line numbers or root causes.
- **Rule 2 — Complete Symbol & Schema Inspection**: View complete function definitions and database schemas before writing code. Snippet tunnel vision is strictly forbidden.
- **Rule 4 — Dual Method Route Registration**: Administrative and repair endpoints (e.g. `/api/repair-narrations`) MUST accept both `GET` and `POST` methods so browser URL navigation never returns `404 Not Found`.

### 2. Defensive Programming & Safety Guards (Smart Rules 11 – 15, 27 – 29)
- **Rule 11 — Zero Masking / No Superficial Patches**: Generic `except Exception:` blocks MUST log exact tracebacks (`logging.exception(...)`) rather than swallowing errors (`except: pass`) or returning fake fallbacks (`0`, `""`).
- **Rule 12 — Defensive Numeric Sanitization**: Use `parse_float()` / `_parse_float()` to strip commas, currency symbols (`₹`, `$`), and spaces before float conversion.
- **Rule 13 — DBF String Width Truncation Guard**: Pass string values through `fit_dbf_str(val, max_len)` to enforce DBF schema byte width limits.
- **Rule 15 & Thread Locks**: Wrap database write operations in `get_client_lock(client_id)` to prevent race conditions across network shares.
- **Rule 27 — Self-Healing Directory Permission Repair**: ALWAYS invoke `ensure_writable_recursive(path)` before creating backups or opening DBF files for write operations. Automatically repair read-only folder attributes.
- **Rule 28 — Scope & Unbound Variable Guard**: Pre-declare and initialize all local variables (`year_bounds = {}`, `handler = None`, `client_memory = {}`) outside `try:` blocks if referenced in outer/subsequent blocks.
- **Rule 29 — Class Body Integrity & Resilient Error Parsing**: Define standalone helper functions outside `class` declarations. Frontend API wrappers MUST safely handle non-JSON text/HTML error responses.

### 3. DBF File Handle & Lock Auditing (`backend/dbf_handler.py`)
- **Context Management**: Verify every `dbf.Table` or `dbfread.DBF` interaction uses strict context managers (`with dbf.Table(...)`) or explicit `table.close()` calls in `finally:` blocks.
- **FoxPro CDX Locking**: Ensure `.CDX` index files are unlocked after write operations. Never leave table open in read-write mode across async await boundaries.

### 4. Financial Math & Precision Audit (Smart Rule 7)
- **Exact Decimal Arithmetic**: Ensure GST (CGST/SGST/IGST), TDS (194Q), and voucher line totals use `Decimal` with `ROUND_HALF_UP` rather than floating-point floats (`float`).
- **Double-Entry Balance Rule**: Verify `Sum(Debit) == Sum(Credit)` for every generated voucher header and line batch in `RKACCT41.DBF` & `RKACCT01.DBF`.

### 5. Memory & RAM Ceiling Audit (512 MB Limit)
- **Garbage Collection & RAM Release**: Ensure heavy PDF/Excel processing releases large binary objects and invokes `gc.collect()` when necessary. Verify `/api/admin/gc` endpoint remains functional.

---

## 💡 How to Trigger CodeRabbit Audit in Antigravity

Start your request with:
`[AUDIT] Review recent changes in backend/dbf_handler.py`
or
`[CODERABBIT] Perform a line-by-line security and DB lock review on backend/routers/vouchers.py`
