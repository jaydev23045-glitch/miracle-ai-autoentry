# 🚀 Miracle AI Auto-Entry Platform

An AI-powered, high-speed automated accounting entry tool designed for **Miracle Accounting Software (DBF)**. 
Automatically extracts, validates, and injects Sales Invoices, Purchase Bills, Bank Statements, Cash Entries, and Opening Balances into Miracle DBF databases with 100% math precision.

---

## 📁 Clean Directory Architecture

```
Mirracle Auto Entre Sale or Purchase or Bank/
├── backend/                     # 🐍 Python FastAPI Backend & Engines
│   ├── main.py                  # Server entry point & CORS configuration
│   ├── gemini_service.py        # Gemini 2.5 AI extraction & Ledger Mapping engine
│   ├── dbf_handler.py           # Direct Miracle DBF reader/writer engine
│   ├── ai_memory.py             # Memory Vault manager (product/supplier/expense catalogs)
│   ├── core/                    # Core schema models, config & validators
│   ├── modules/                 # Decoupled module parsers
│   │   ├── sales/               # Sales voucher engine
│   │   ├── purchases/           # Purchase voucher engine
│   │   ├── bank/                # Native PDF & statement engine
│   │   └── cash/                # Cash entries engine
│   └── routers/                 # FastAPI REST API endpoints
│
├── frontend/                    # 🎨 Web Dashboard User Interface
│   ├── index.html               # Main dashboard HTML (Tailwind CSS, FontAwesome)
│   ├── app.js                   # Client-side UI logic, virtual table grid, live search
│   └── AI_ARCHITECTURE_SUMMARY.md
│
├── AI_Memory_Vault/             # 🧠 Per-Client AI Memory Storage
│   └── CMPxxxx_memory.json      # Client-specific learned products, suppliers & ledger rules
│
├── BACKUPS/                     # 🛡️ Automatic Pre-Push Miracle DBF Backups
├── docs/                        # 📚 Architecture & technical specifications
├── scratch/                     # 🧪 Diagnostic & utility scratch scripts
├── temp_uploads/                # 📂 Staging area for uploaded documents
└── start_backend.command        # ⚡ Mac launcher script (Double-click to start)
```

---

## 🌟 Modules & Features

1. **Sales Vouchers** (`Sales`)
   - Native Excel parser + Gemini AI OCR for PDF/Images.
   - Smart HSN/GST rate auto-healing & item mapping.

2. **Purchase Vouchers** (`Purchases`)
   - Vendor GSTIN verification & automatic B2B/B2C party creation.
   - Ghost freight & discount double-counting prevention.

3. **Bank Statements** (`Bank Statements`)
   - **Deterministic Native PDF Engine** (0.05s, 100% math precision).
   - **6-Stage Intelligent Ledger Mapper** (Token intersection scoring, 26-category keywords, UPI name extraction, fuzzy match).
   - Live Search, Status Filter Badges (`All`, `Mapped`, `Auto-Create`, `Review`), and **1-Click Resolve Suspense**.

4. **Cash Entries** (`Cash Entries`)
   - Fast cash voucher creation with auto-fill debtors/creditors.

5. **Opening Balances** (`Opening Balances`)
   - Extract and inject initial debit/credit ledger balances.

---

## ⚡ How to Run

Double-click `start_backend.command` or run in terminal:

```bash
cd backend
python3 main.py
```

Then open your browser at `http://localhost:8000`.
