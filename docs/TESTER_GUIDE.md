# 🧪 Miracle AI Auto-Entry — Comprehensive Testing & Troubleshooting Guide

This guide is designed for anyone testing the **Miracle AI Auto-Entry Platform**. Follow these steps to set up, test features, and resolve any issues that may arise during testing.

---

## 📋 1. Prerequisites & System Requirements

- **Operating System**: macOS or Windows (10/11)
- **Python**: Python 3.9, 3.10, or 3.11 installed
- **Browser**: Google Chrome, Brave, Microsoft Edge, or Firefox
- **Google Gemini API Key**: Free key from [Google AI Studio](https://aistudio.google.com/)
- **Miracle Data Folder**: Active client company folder (e.g. `CMP0005` or `CMP0006`) containing fiscal year subfolders (e.g. `YR25`).

---

## ⚡ 2. Step-by-Step Setup Guide

### Step 1: Open Terminal / Command Prompt
Navigate to the project root directory:
- **macOS / Linux**:
  ```bash
  cd "/path/to/Mirracle Auto Entre Sale or Purchase or Bank"
  ```
- **Windows (CMD / PowerShell)**:
  ```cmd
  cd "C:\path\to\Mirracle Auto Entre Sale or Purchase or Bank"
  ```

### Step 2: Create & Activate Virtual Environment

- **macOS / Linux**:
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  pip install -r backend/requirements.txt
  ```

- **Windows**:
  ```cmd
  python -m venv venv
  venv\Scripts\activate
  pip install -r backend\requirements.txt
  ```

### Step 3: Configure `backend/settings.json` (Crucial Step!)

Before launching, check `backend/settings.json`. Since paths vary by machine, update the path settings:

```json
{
  "gemini_api_key": "YOUR_GEMINI_API_KEY_HERE",
  "miracle_base_path": "YOUR_ABSOLUTE_PATH_TO_THIS_FOLDER",
  "active_client_id": "CMP0005",
  "memory_path": "YOUR_ABSOLUTE_PATH_TO_THIS_FOLDER/AI_Memory_Vault",
  "active_year_folder": "YR25"
}
```

> 💡 **Tip:** You can also update these paths directly inside the web UI Settings Modal after launching!

---

## 🚀 3. How to Launch the Application

### macOS
1. Double-click `start_backend.command`  
   *OR*
2. Run in Terminal:
   ```bash
   cd backend
   ../venv/bin/python main.py
   ```

### Windows
Run in Command Prompt / PowerShell:
```cmd
cd backend
..\venv\Scripts\python main.py
```

### Accessing the Web Dashboard
Open your web browser and go to:
👉 **`http://localhost:8000`**

---

## 🧪 4. Testing Workflow Checklist

### A. Initial Settings Check
1. Open the dashboard at `http://localhost:8000`.
2. Click the **⚙️ Settings** button at the top right.
3. Verify:
   - **Gemini API Key**: Must be entered.
   - **Miracle Base Path**: Must point to the folder containing your `CMPxxxx` client directories.
   - **Active Client ID**: Select `CMP0005` or your target client.
   - **Active Fiscal Year**: Select `YR25`, `YR26`, or `YR27`.
4. Click **Save Settings**.

---

### B. Testing Module 1: Bank Statements
1. Click on the **Bank Statements** tab.
2. Upload a sample Bank Statement (PDF or Excel).
3. **Verify Extraction**:
   - Check if dates, withdrawal/deposit amounts, balance, and narrations are extracted cleanly.
   - Check status badges: `Mapped`, `Auto-Create`, or `Review`.
4. **Resolve Suspense / Unknown Ledgers**:
   - Click **Resolve Suspense** or select a ledger from the drop-down.
5. **Test Push to Miracle**:
   - Click **Push to Miracle**.
   - Check that entries appear in Miracle DBF tables without balance errors.

---

### C. Testing Module 2: Sales Invoices
1. Click on the **Sales Vouchers** tab.
2. Upload a Sales Invoice (PDF, Image, or Excel).
3. **Verify Line Items**:
   - Party ledger selection (Debtor).
   - Item pricing, quantity, and tax breakdown (CGST/SGST/IGST).
   - Single discount header rule validation.
4. Click **Push to Miracle** and verify entry creation in `RKACCT41.DBF` (`SS` prefix).

---

### D. Testing Module 3: Purchase Invoices
1. Click on the **Purchase Vouchers** tab.
2. Upload a Purchase Bill.
3. **Verify Vendor Details**:
   - Vendor GSTIN & party auto-detection.
   - Purchase ledger assignment (`AGST0003` / `AGST0004`).
4. Click **Push to Miracle** (`PP` prefix).

---

### E. Testing Modules 4 & 5: Cash Entries & Opening Balances
1. Test cash receipt/payment entry creation under **Cash Entries**.
2. Verify ledger debit/credit balances under **Opening Balances**.

---

## 🛠️ 5. Troubleshooting & FAQ (If Any Issue Comes Up)

| Issue / Symptom | Possible Cause | How to Resolve |
|---|---|---|
| **Backend fails to start / `ModuleNotFoundError`** | Virtualenv not activated or packages missing | Run `pip install -r backend/requirements.txt` inside your virtual environment. |
| **"Path does not exist" or empty client list in Settings** | `miracle_base_path` points to a non-existent folder from another machine | Open **Settings Modal** in UI or edit `backend/settings.json`, set `miracle_base_path` to your current folder path. |
| **Extraction Error / 403 Invalid API Key** | Missing or invalid Gemini API key | Get a free key from [Google AI Studio](https://aistudio.google.com/) and update it in Settings. |
| **DBF Lock / Write Permission Error** | Miracle Accounting Software is currently open with the target client active | **Close Miracle Accounting Software** (or exit the active client company in Miracle) before pushing. VFP locks DBF files when open. |
| **Date Out of Bounds Warning on Push** | Voucher date doesn't match active year folder (e.g. 2024 date pushed to `YR25`) | Change the Active Year Folder in Settings or edit the date on the grid. |
| **"Debit and Credit totals do not balance"** | Round-off discrepancy or tax line mismatch | Review grid line items and adjust round-off or tax amounts before pushing. |
| **UI layout looks unstyled / broken** | Port conflict or cached static assets | Hard-refresh the browser (`Ctrl+F5` or `Cmd+Shift+R`). Ensure backend is running on `port 8000`. |

---

## 🛡️ 6. Data Safety & Backup Restoration

- **Automatic Backups**: Every time **Push to Miracle** is clicked, a pre-push snapshot zip is automatically saved in the `/BACKUPS/` folder.
- **How to Restore**: If any bad data is pushed during testing, unzip the latest backup file from `/BACKUPS/` back into your active client folder (e.g., `CMP0005/YR25`).

---

*This guide ensures safe, reliable testing for any developer or tester receiving this project package.*
