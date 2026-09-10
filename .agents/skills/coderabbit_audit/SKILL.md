---
name: coderabbit_audit
description: Automated line-by-line AI Code Reviewer & Security Auditor for Antigravity. Triggers when requested to review PRs, audit DBF handles, inspect memory leaks, or verify bug fixes.
---

# CodeRabbit Automated AI Audit Protocol for Antigravity

> **Purpose**: Perform rigorous, line-by-line automated code auditing to detect DBF locks, un-imported modules, floating-point precision flaws, unhandled API errors, and security vulnerabilities.

---

## 🔍 CodeRabbit Checklist for Miracle AI Auto-Entry

When triggered, audit code changes against these 6 core vulnerability patterns:

### 1. DBF File Handle & Lock Auditing
- Verify every `dbf.Table` or `dbfread.DBF` context opens and explicitly closes file handles (`table.close()` or `with dbf.Table(...)`).
- Ensure `.CDX` index files are not left locked after write operations.

### 2. Module & Import Integrity
- Check for un-imported or missing Python dependencies (e.g. `fastapi`, `dbf`, `dbfread`, `google-genai`).
- Verify no implicit undefined variables exist in modified functions.

### 3. Precision & Financial Math Audit
- Ensure GST (CGST/SGST/IGST) and TDS (194Q) calculations use exact rounding/decimal precision rather than floating-point drift.
- Verify double-entry balances: `Sum(Debit) == Sum(Credit)` for every generated voucher.

### 4. Exception Handling & Logging
- Ensure generic `except Exception:` blocks log exact tracebacks rather than silently swallowing errors.
- Verify fallback pathways exist when Gemini API rate-limits or fails response parsing.

### 5. Rule Compliance Check
- Cross-reference code changes against `docs/AI_RULES.md` (25 Smart Rules Protocol) and `docs/AI_RULES_BOOK.md`.

---

## 💡 How to Trigger CodeRabbit Audit in Antigravity
Start your request with:
`[AUDIT] Review recent changes in backend/dbf_handler.py`
or
`[CODERABBIT] Perform a line-by-line security and DB lock review on backend/main.py`
