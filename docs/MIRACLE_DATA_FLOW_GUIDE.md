# Master Architectural & Operational Guide: How Miracle Data Appears in the Web Browser Tool

---

## 1. Executive Summary & Core Explanation

If you open the web tool on the Render server (`miracle-ai-autoentry.onrender.com`) and open the **AI Needs Clarification** (Party Mapping) or **Match Extracted Product Items** modal, you might wonder:

> *"Why were my existing Miracle ledgers, customers, suppliers, and stock products NOT showing in the web browser dropdowns?"*

### 💡 The Root Cause (In Simple Terms)

1. **Cloud vs. Local Machine Isolation**:
   - The Web Application Dashboard is hosted on **Render Cloud Servers** on the internet.
   - Your Miracle Accounting software and data files (`.DBF` database files) reside **locally on your Windows PC hard drive** (e.g. `C:\Miracle\CMP0005`).
   - The cloud server on the internet cannot directly read your local PC's `C:\` drive.

2. **Misdirected API Queries**:
   - Previously, when opening the product or ledger mapping dropdowns in the browser, the web app tried to fetch ledgers directly from the Render Cloud Server (`https://miracle-ai-autoentry.onrender.com/api/products`).
   - Because Render's cloud server does not have your local `C:\Miracle` database files on its hard drive, it returned an empty list (`0 ledgers, 0 products`).
   - Consequently, the browser modal only showed generic auto-create options (`-- Select Miracle Product --`, `[Auto-Create 0% Product]`, `[Auto-Create B2B/B2C]`).

3. **Single Financial Year DBF Traversal**:
   - In Miracle Accounting, master tables like `RKACCM21.DBF` (Product Items) are often stored in the **Client Root Directory** (`C:\Miracle\CMP0005\RKACCM21.DBF`) or in older year folders (`YR25`).
   - The backend was only looking inside the active year subfolder (e.g., `YR27`), returning `0` items if the file was located in the client root.

---

## 2. System Architecture: How Local Miracle Database Connects to the Web Tool

```
┌─────────────────────────────────────────────────────────┐
│ 💻 Local Windows PC (Your Computer)                      │
│                                                         │
│  🔌 Miracle Bridge Agent (Port 9123)                     │
│     http://localhost:9123                               │
│        │                                                │
│        ▼ Direct DBF Read/Write                          │
│  📂 Local Miracle Database Files                        │
│     C:\Miracle\CMP0005\                                 │
│     • RKACCM01.DBF (Ledgers)                            │
│     • RKACCM21.DBF (Products)                           │
└──────────▲──────────────────────────────────────────────┘
           │
           │ Direct Browser-to-Bridge Fetch
           │
┌──────────┴──────────────────────────────────────────────┐
│ 🌐 Web Browser (Chrome / Edge)                           │
│  🎨 Miracle AI Auto-Entry Dashboard                      │
│     miracle-ai-autoentry.onrender.com                   │
└──────────▲──────────────────────────────────────────────┘
           │
           │ PDF Upload & AI Data Extraction
           │
┌──────────┴──────────────────────────────────────────────┐
│ ☁️ Render Cloud Backend                                  │
│  🤖 Gemini AI Engine                                    │
└─────────────────────────────────────────────────────────┘
```

---

## 3. How The Fix Solves The Problem (Step-by-Step)

### A. Dynamic Bridge Routing (`app.js`)
When you open the web tool, it checks if the **Miracle Bridge Agent** is running on your PC (indicated by the green badge at the top: `Miracle Bridge Connected (9123)`).

- **Before the Fix**: The product modal always called `https://miracle-ai-autoentry.onrender.com/api/products` (Cloud server $\rightarrow$ 0 products).
- **After the Fix**: The web dashboard automatically routes ledger and product requests directly to `http://localhost:9123/api/local-products` and `http://localhost:9123/api/local-ledgers`.

### B. Auto Pre-Fetch on Modal Open
Whenever you upload a PDF bill and the AI opens the **Party Clarification Modal** or **Product Mapping Modal**, the web browser now automatically triggers a pre-fetch call (`fetchLedgers()` & `fetchProducts()`) to pull fresh data from your local `C:\Miracle` database before displaying the UI dropdowns.

### C. Comprehensive Multi-Year & Root DBF Scanner (`dbf_handler.py`)
The DBF reader engine has been upgraded with a **3-Tier Master Scanner**:
1. Checks the active year directory (e.g. `CMP0005/YR27/RKACCM21.DBF`).
2. If missing, checks the client root directory (`CMP0005/RKACCM21.DBF`).
3. Merges product records across all available financial years (`YR27`, `YR26`, `YR25`), ensuring no item or customer ledger is ever missed.

---

## 4. Operational Checklist

To guarantee that your existing Miracle ledgers and products ALWAYS display properly in the web tool, follow these steps:

| Step | Action | Expected Result |
|---|---|---|
| **1** | Run **Miracle Bridge Agent** on your Windows PC (`python miracle_bridge_agent.py` or double-click launcher). | Port `9123` starts listening locally. |
| **2** | Open the web browser tool (`miracle-ai-autoentry.onrender.com`). | Top bar badge shows **`Miracle Bridge Connected (9123)`** in green. |
| **3** | Select your Active Miracle Client (e.g. `CMP0005`) and Financial Year (e.g. `YR27`). | The web app syncs with the active client folder on your PC. |
| **4** | Upload a Sales/Purchase PDF bill. | When the clarification modal appears, all existing Miracle customers, suppliers, expenses, and stock items will be grouped and visible in the dropdowns. |
| **5** | Click the **Refresh Button (<i class="fa-solid fa-arrows-rotate"></i>)** inside any mapping row. | Triggers instant re-reading of your local DBF database files to pull any newly added Miracle accounts. |

---

## 5. Summary Table: Before vs. After Fix

| Feature / Behavior | Before Fix ❌ | After Fix ✅ |
|---|---|---|
| **Product Item Dropdown** | Showed only `-- Select Miracle Product --` & `[Auto-Create 0% Product]` | Displays all existing Miracle Stock Products categorized by Commodity Group with GST rate matching badges. |
| **Party Account Dropdown** | Showed only B2B/B2C Auto-Create options when memory was empty | Displays all existing Sundry Debtors, Sundry Creditors, Expenses, and Bank Accounts from your local Miracle DBFs. |
| **Cloud Server Operation** | Failed to fetch local DBFs from cloud server (`0` records) | Routes queries to `http://localhost:9123` directly from your browser, bypassing cloud disk limitations. |
| **Multi-Year Product Reading** | Single-year folder query failed if file was in client root | 3-tier scanner searches active year, client root folder, and all historical years. |
