# 🛑 AI ASSISTANT MASTER DIRECTORY & 25 SMART RULES PROTOCOL 🛑

> **CRITICAL INSTRUCTION FOR ALL AI AGENTS (Claude, Gemini, Antigravity, etc.):**
> Before writing or modifying a SINGLE line of code in this project, you **MUST** read and strictly obey these **25 Smart Rules**.
> Ignoring these rules will result in repeated bugs, broken Miracle accounting database files, or misdiagnosed runtime failures.

---

## 🏛️ PART 1 — THE 25 SMART COMMANDMENTS OF AI BUG RESOLUTION

### 🔍 Category I: Log Inspection & Ground Truth (Rules 1 – 5)
1. **Rule 1 — Log-First Mandate**: You MUST read the full un-truncated error traceback or HTTP response before forming a diagnostic hypothesis. NEVER guess line numbers or root causes.
2. **Rule 2 — Complete Symbol & Schema Inspection**: View the entire function definition and database schema before making edits. Snippet tunnel vision is strictly forbidden.
3. **Rule 3 — Path Integrity**: Always verify file paths on the local filesystem. Fix any stale or broken directory path references immediately.
4. **Rule 4 — Dual Method Route Registration**: Administrative and repair endpoints (e.g. `/api/repair-narrations`) MUST accept both `GET` and `POST` methods so browser URL navigation never returns `404 Not Found`.
5. **Rule 5 — Grounding in Empirical Evidence**: Base all solutions on verified runtime log outputs, stack traces, and automated test execution.

---

### ⚖️ Category II: Universal Accounting & 100-Client Mindset (Rules 6 – 10)
6. **Rule 6 — The 100-Client Rule**: Build self-healing, dynamic algorithms. NEVER hardcode single-client folder names, dates, or party strings in core backend engines.
7. **Rule 7 — Double-Entry Math Balance**: Every voucher push MUST mathematically balance total Debits and total Credits to exact 0.00.
8. **Rule 8 — Dual Field Narration Storage**: Always write transaction narrations to BOTH `FIELD82` (50-char short string in `RKACCT41.DBF`) and `T40F02` (unlimited memo string in `RKACCT40.DBF`).
9. **Rule 9 — Dynamic Group Lookup**: Query `RKACCM11.DBF` dynamically for account group codes. NEVER hardcode group codes like `G0000017`.
10. **Rule 10 — Financial Year Date Bounds Guard**: Validate voucher dates against the active fiscal year bounds (`YRxx`) and flag out-of-range dates prior to DBF push.

---

### 🛡️ Category III: Defensive Programming & Error Prevention (Rules 11 – 15)
11. **Rule 11 — Zero Masking / No Superficial Patches**: NEVER swallow exceptions with `except: pass` or return fake fallback values (`0`, `""`). Fix the broken contract at its root.
12. **Rule 12 — Defensive Numeric Sanitization**: Use `parse_float()` / `_parse_float()` to strip commas, currency symbols (`₹`, `$`), and spaces before float conversion.
13. **Rule 13 — DBF String Width Truncation Guard**: Pass all string values through `fit_dbf_str(val, max_len)` to enforce DBF schema byte width limits and prevent overflow crashes.
14. **Rule 14 — Memo Field Truncation Bypass**: Exclude memo pointer fields (type `'M'`) from text length truncation functions.
15. **Rule 15 — Thread-Safe Client DB Locks**: Wrap all database write operations in `get_client_lock(client_id)` to prevent race conditions across SMB network shares.

---

### 🤖 Category IV: AI Data Extraction & Memory (Rules 16 – 20)
16. **Rule 16 — Sequential Balance Carryover**: Process bank PDF chunks sequentially, injecting closing balances into subsequent prompts to preserve transaction continuity.
17. **Rule 17 — Universal Date-Gap Continuity Check**: Trigger recursive sub-page splitting if consecutive transaction rows exhibit a date gap $>28$ days.
18. **Rule 18 — Indian Standard Date Parsing**: Always prioritize Day-First date parsing formats (`%d/%m/%Y`, `%d-%m-%Y`) over Month-First American formats.
19. **Rule 19 — Single Discount Header Posting**: Sales invoice discounts post strictly to header `EDVAS00095` (`DISCOUNT A/C`) while item discounts are set to `0.0`, preventing double-counting.
20. **Rule 20 — Priority Name-Based Group Overrides**: Auto-classify new party ledgers containing keywords like `EXPENSE`, `RENT`, `SALARY`, or `MAINTENANCE` directly under `Indirect Expenses`.

---

### 🧪 Category V: Automated Verification & Memory Persistence (Rules 21 – 25)
21. **Rule 21 — Mandatory Empirical Compilation**: You MUST run `python3 -m py_compile` or execution scripts after editing code. Never declare success without running verification.
22. **Rule 22 — Lock-Resilient ZIP Backups**: Always create a full timestamped client backup in `/BACKUPS/` prior to performing DBF table pushes.
23. **Rule 23 — Premium UI/UX Styling Protection**: Maintain glassmorphic dark-mode aesthetics in `/frontend/`. Never add plain browser-default inputs or break module navigation.
24. **Rule 24 — Mandatory Changelog Update**: Append a detailed summary of all code modifications to `docs/CHANGELOG.md` upon task completion.
25. **Rule 25 — Master Memory Sync**: Update `docs/AI_RULES.md` and `docs/AI_RULES_BOOK.md` whenever a new bug or system rule is established.

---

## 📚 PART 2 — REQUIRED ARCHITECTURE FILES TO CONSULT
Before modifying core components, inspect these references in order:
1. **Master AI Rules Book**: `docs/AI_RULES_BOOK.md`
2. **Master Architecture Specification**: `docs/AI_UNIVERSAL_ONBOARDING.md`
3. **Historical Bug Reports & Fixes**: `docs/BUG_REPORT_AND_FIXES.md`
4. **Miracle DBF Table Schemas**: `.agents/skills/miracle_accounting/SKILL.md`
5. **Project Changelog**: `docs/CHANGELOG.md`

*By reading this document, you agree to follow the 25 Smart Rules Protocol strictly.*
