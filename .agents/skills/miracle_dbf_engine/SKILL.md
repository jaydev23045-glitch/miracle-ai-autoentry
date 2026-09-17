---
name: miracle_dbf_engine
description: Technical instructions and protocols for FoxPro .DBF file binary management, CDX index handling, file lock isolation, 12-char Voucher ID generation, and multi-year directory routing in Miracle ERP.
---

# Miracle DBF Engine — Binary Database Management Protocol

> [!IMPORTANT]
> **DBF FILE LOCK & INTEGRITY SAFETY DIRECTIVES:**
> 1. Miracle ERP uses FoxPro `.DBF` tables and `.CDX` composite index files. Improper file handle closures will lock out Miracle desktop users!
> 2. Always open tables using explicit context managers (`with dbf.Table(...)`) or ensure `table.close()` is executed in a `finally:` block.
> 3. Enforce **Rule 27** (`ensure_writable_recursive`), **Rule 15** (`get_client_lock`), and **Rule 22** (ZIP backups in `/BACKUPS/`) before attempting any DBF write operation.

---

## 1. Miracle DBF File Structure & Directory Layout

Miracle ERP organizes client data into company folders (`CMPxxxx`). Multi-year accounting data resides in subdirectories:

```
[ Base Path: C:\Miracle ]
   └── CMP0001/
       ├── 2024-2025/               <-- Year-specific data folder (YRxx)
       │   ├── RKACCT41.DBF         <-- Voucher Header Table (50-char FIELD82 narration)
       │   ├── RKACCT40.DBF         <-- Voucher Memo Table (Unlimited T40F02 narration)
       │   ├── RKACCT41.CDX         <-- Voucher Header Index File
       │   ├── RKACCT01.DBF         <-- Voucher Detail / Line Item Table
       │   ├── RKACCT01.CDX         <-- Voucher Detail Index File
       │   ├── RKACCM01.DBF         <-- Ledger Master Table
       │   ├── RKACCM11.DBF         <-- Account Group Master Table
       │   ├── RKACCGID.DBF         <-- Master GUID Registration Table (FIELD04 = 'Y')
       │   └── RKHEAD41.DBF         <-- Bill / Header Extra Fields
       └── CMP0002/
```

---

## 2. Core DBF Rules & Field Specifications (Smart Rules 8, 9, 13, 33, 36)

### Rule 8 — Dual Field Narration Storage Protocol
All voucher postings MUST write transaction narrations to BOTH tables:
- **`FIELD82` in `RKACCT41.DBF`**: 50-character truncated string via `fit_dbf_str(narration, 50)`.
- **`T40F02` in `RKACCT40.DBF`**: Full, un-truncated memo string linked by matching Voucher ID (`FIELD01`).

### Rule 13 & 14 — DBF String Width Truncation & Memo Bypass
- Pass all character fields through `fit_dbf_str(val, max_len)` to enforce schema limits and prevent byte overflow crashes.
- Exclude memo pointer fields (type `'M'`) from length truncation functions.

### Rule 33 — Guarded Group Code Lookup & Bank OCC Isolation Guard
- `find_group_by_name()` in DBF resolution MUST use two-phase matching (exact match first, then guarded substring match).
- Substring search MUST explicitly exclude special loan/bank codes like `G0000016` (`Bank OCC a/c`) and `G0000017` (`Secured Loans`) unless explicitly requested.
- Query `RKACCM11.DBF` dynamically for account group codes. Never hardcode static group codes.

### Rule 36 — Miracle Party Master GUID Registration Protocol
- Whenever auto-creating or syncing party master ledgers in `RKACCM01.DBF`, GUID records in `RKACCGID.DBF` MUST explicitly set `FIELD04 = 'Y'` (25 characters padded).
- Newly created parties MUST automatically sync across all active financial year folders (`YR27`, `YR26`, `YR25`), and `repair_unregistered_party_guids()` MUST repair missing GUID entries.

---

## 3. Unique 12-Character Voucher ID Generation (`dbf_handler.py`)

Miracle ERP requires every voucher across `RKACCT41`, `RKACCT40`, and `RKACCT01` to share a unique 12-character ID:

```python
import uuid

def generate_miracle_voucher_id() -> str:
    """Generates a 12-character Miracle Voucher ID prefixed with SS."""
    raw_uuid = uuid.uuid4().hex.upper()
    return f"SS{raw_uuid[:10]}"
```

---

## 4. File Lock Prevention, Permission Repair & Backup Protocol

1. **Permission Repair (Rule 27)**: Invoke `ensure_writable_recursive(path)` prior to opening DBF files for write operations to fix read-only attributes (`dr-xr-xr-x` / mode `555`).
2. **Thread-Safe Client Locks (Rule 15)**: Wrap all DB write functions in `get_client_lock(client_id)` to prevent race conditions over network shares.
3. **Lock-Resilient Backups (Rule 22)**: Always create a timestamped client backup zip in `/BACKUPS/` prior to performing DBF pushes.
4. **Context Manager Pattern**: Wrap table interactions inside context managers:
   ```python
   import dbf

   def safe_append_voucher(dbf_path: str, record_data: dict):
       with dbf.Table(dbf_path) as table:
           table.open(mode=dbf.READ_WRITE)
           table.append(record_data)
   ```
5. **CDX Index Files**: Never delete or rename `.CDX` files directly while Miracle desktop is active. If index corruption occurs, instruct user to run Miracle's built-in "Reindex / Utilities" tool.
