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
3. **Pending Voucher Polling**: Polls cloud server for approved vouchers ready for DBF insertion.
4. **Local DBF Push**: Executes binary DBF writes directly on the desktop machine using `dbf_handler.py`.
5. **Offline Queue Management**: Caches pending sync tasks locally if internet connectivity is lost; resumes automatically upon reconnection.

---

## 4. Security & Multi-Client Authentication

- **Device Token Authentication**: Every Bridge Agent registers using a unique hardware machine ID + client secret token.
- **Data Isolation**: Cloud API enforces strict client tenant separation (`client_id`). A client cannot read or overwrite DBF paths belonging to another company code.
- **Payload Encryption**: All payload transmissions between Bridge EXE and cloud server use HTTPS with TLS 1.3 encryption.

---

## 5. Bridge Executable Build & Auto-Update Protocol (`build_bridge_exe.py`)

1. **Standalone Build**: Packaged via PyInstaller into a single lightweight Windows `.exe` (`MiracleBridgeAgent.exe`):
   ```bash
   python backend/build_bridge_exe.py
   ```
2. **Auto-Update Sequence**:
   - On startup, Bridge Agent checks `/api/bridge/version`.
   - If a newer binary version exists, downloads update zip, spawns `updater.bat`, terminates running process, replaces `MiracleBridgeAgent.exe`, and restarts automatically.

---

## 6. Troubleshooting & Audit Commands

- Test local DBF access: `python backend/miracle_bridge_agent.py --test-dbf`
- Verify cloud connectivity: `python backend/miracle_bridge_agent.py --ping-cloud`
- Re-build executable: `python backend/build_bridge_exe.py`
