---
name: miracle_bridge_hybrid_sync
description: Architecture and synchronization protocols for the Miracle Bridge desktop agent, remote client DBF sync, cloud backend integration, offline caching, and security authorization.
---

# Miracle Bridge Hybrid Sync & Remote Agent Protocol

> **Purpose**: Manage the desktop-to-cloud bridge architecture that securely synchronizes local Miracle ERP DBF files on Windows desktop computers with the central FastAPI cloud server, enforcing Smart Rules 6, 15, and 27.

---

## 1. Key Smart Rules Alignment (Rules 6, 15, 27)

- **Rule 6 — The 100-Client Rule**: Build self-healing, dynamic algorithms. NEVER hardcode single-client folder names, dates, or party strings in core backend engines or bridge agents.
- **Rule 15 — Thread-Safe Client DB Locks**: Wrap all database write operations in `get_client_lock(client_id)` to prevent race conditions across SMB network shares.
- **Rule 27 — Self-Healing Directory Permission Repair**: ALWAYS invoke `ensure_writable_recursive(path)` before creating client backups or opening DBF files for write operations. Automatically repair read-only folder attributes (`dr-xr-xr-x` / mode `555`).

---

## 2. Hybrid Architecture Overview

The system operates in a hybrid deployment mode:

```
[ Local Desktop PC (Windows) ]              [ Cloud Deployment (Render / VPS) ]
  ├── Miracle ERP Software                      ├── Central FastAPI Server
  ├── Local DBF Storage (C:\Miracle\CMPxxxx)    ├── Gemini AI Mapping Engine
  └── Miracle Bridge Agent (EXE/Python)         ├── Web UI Dashboard
            │                                           │
            └────────── Secure HTTPS / WSS API ─────────┘
```

---

## 3. Miracle Bridge Agent Core Responsibilities (`miracle_bridge_agent.py`)

1. **Auto-Discovery**: Scans local Windows drives (`C:\Miracle`, `D:\Miracle`) to locate active company folders (`CMP0001` - `CMP9999`) and accounting year subdirectories.
2. **Ledger Master Sync**: Reads `RKACCM01.DBF` and `RKACCM11.DBF` locally, compresses ledger JSON, and pushes to cloud API `/api/sync/ledgers`.
3. **Local Client Offloading & Zero-Cost Regex Intelligence**:
   - **`/api/local/optimize-image`**: Resizes and compresses invoice photos locally on Client PC (< 300 KB) before uploading to save 90% cloud bandwidth.
   - **`/api/local/match-regex`**: Matches narrations against local SQLite DB (`client_intel.db`) in < 1ms with 0 cloud AI API tokens.
   - **`/api/local/learn-rule`**: Auto-learns regex pattern upon voucher approval and auto-prunes stale rules (> 90 days unused, max 500 rules per client).
4. **Single-Instance Execution Lock**: Employs socket-level port lock on `127.0.0.1:9123` (`check_single_instance_lock`) to prevent duplicate instances from running.
5. **Localhost Security**: Binds Uvicorn HTTP server strictly to `127.0.0.1` (localhost only) to block unauthorized local network access.
6. **Automatic Cleanup**: Automatically purges temporary uploads older than 7 days (`cleanup_old_temp_files`) on agent launch.
7. **Offline Transaction Queue Management**: Caches pending sync tasks in local SQLite database if internet connection drops; automatically flushes queue upon reconnect.

---

## 4. Universal Cloud JSON Ingestion & Offloaded Parsing (`/api/vouchers/process-json`)

- Handles pre-parsed JSON payloads from Client PC desktop bridge across all 4 accounting modules: Bank Statements, Sales Invoices, Purchase Bills (with 194Q TDS), and Cash Entries.
- Operates statelessly on cloud backend consuming < 1 MB RAM per request.

---

## 5. Security & Multi-Client Authentication

- **Device Token Authentication**: Every Bridge Agent registers using a unique hardware machine ID + client secret token.
- **Data Isolation**: Cloud API enforces strict client tenant separation (`client_id`). A client cannot read or overwrite DBF paths belonging to another company code.
- **Localhost Only Binding**: Port 9123 is bound strictly to `127.0.0.1`.

---

## 6. Bridge Executable Build & Auto-Update Protocol (`build_bridge_exe.py`)

1. **Standalone Build**: Packaged via PyInstaller into a single lightweight Windows `.exe` (`MiracleBridgeAgent.exe`):
   ```bash
   python backend/build_bridge_exe.py
   ```
2. **Auto-Update Sequence**:
   - On startup, Bridge Agent checks `/api/bridge/version`.
   - If a newer binary version exists, downloads update zip, spawns `updater.bat`, terminates running process, replaces `MiracleBridgeAgent.exe`, and restarts automatically.

---

## 7. Troubleshooting & Audit Commands

- Test local DBF access: `python backend/miracle_bridge_agent.py --test-dbf`
- Verify cloud connectivity: `python backend/miracle_bridge_agent.py --ping-cloud`
- Re-build executable: `python backend/build_bridge_exe.py`

