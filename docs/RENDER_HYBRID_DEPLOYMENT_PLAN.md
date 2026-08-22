# 🚀 Complete Master Guide: Render Free Plan Server & Client MiracleBridge Agent Setup

This guide provides the complete setup walkthrough for deploying the **Miracle AI Auto-Entry** backend server on **Render.com (Free Plan)** while running the lightweight **`MiracleBridge.exe` agent** on client Windows PCs.

---

## 🏗️ Architecture Overview

```
                          ┌──────────────────────────────────────────────┐
                          │         Render.com Cloud Server              │
                          │   https://miracle-ai-app.onrender.com       │
                          │                                              │
                          │  • Web Dashboard UI (HTML5 / JS / Tailwind) │
                          │  • Gemini 2.5 AI Multi-Modal Engine          │
                          │  • AI Memory Vault & Rules Engine            │
                          │  • 100% Code Protection & IP Security        │
                          └──────────────────────┬───────────────────────┘
                                                 │
                                  Browses Web UI │ Extracts PDF/Excel
                                                 ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                Client Windows PC (Office)                              │
│                                                                                        │
│   Web Browser (Chrome/Edge) ─── Push JSON ───► MiracleBridge Agent (http://localhost:9123) │
│                                                              │                         │
│                                                       Direct DBF Write                 │
│                                                              ▼                         │
│                                                   C:\Miracle\CMP0005\YR25              │
│                                                 (RKACCT41.DBF, RKACCT01.DBF)           │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📌 STEP 1: Deploy Backend Server on Render Free Plan (10 Minutes)

### 1. Push Project to a Private GitHub Repository
1. Log in to [GitHub.com](https://github.com).
2. Click **New Repository** $\rightarrow$ Name it `miracle-ai-autoentry`.
3. Select **PRIVATE** (to protect your source code).
4. Run in your project root terminal:
   ```bash
   git init
   git add .
   git commit -m "Production release for Render and MiracleBridge"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/miracle-ai-autoentry.git
   git push -u origin main
   ```

### 2. Create Render Web Service
1. Log in to [Render.com](https://render.com).
2. Click **New +** $\rightarrow$ Select **Web Service**.
3. Connect your GitHub account and select `miracle-ai-autoentry`.
4. Enter the deployment settings:
   - **Name**: `miracle-ai-app`
   - **Region**: `Singapore` or `Frankfurt` (closest to India)
   - **Branch**: `main`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r backend/requirements.txt`
   - **Start Command**: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type**: Select **Free ($0/month)**
5. Environment Variables:
   - `GEMINI_API_KEY`: *(Optional: user can also enter their key in settings UI)*
6. Click **Create Web Service**.

---

## 📌 STEP 2: Setup Client PC (`MiracleBridge.exe`) (5 Minutes)

On each client's Windows PC where Miracle Accounting Software is installed (`C:\Miracle`):

### Option A: Run `MiracleBridge.exe` (Recommended)
1. Download or copy `miracle_bridge/dist/MiracleBridge.exe` to the client's PC.
2. Double-click `MiracleBridge.exe`.
3. It will run quietly in the background, listening on `http://localhost:9123`.

### Option B: Run via Batch File
1. Copy the `miracle_bridge/` folder to the client's PC.
2. Double-click `start_bridge.bat`.
3. A command prompt window will launch:
   `🚀 Starting Miracle DBF Local Bridge Agent on port 9123...`

---

## 📌 STEP 3: Verify End-to-End Workflow

1. Open Chrome/Edge on client PC and navigate to:
   👉 **`https://miracle-ai-app.onrender.com`**
2. Check top navigation bar badge:
   - If connected, it displays: **`🟢 Miracle Bridge Connected (9123)`**
3. Upload Bank Statement PDF or Sales/Purchase Invoice.
4. Review extracted entries on the grid.
5. Click **Push to Miracle**.
6. The web app sends entries to `http://localhost:9123/inject`.
7. Entries appear inside Miracle Accounting Software instantly!

---

## 🛡️ Key Security & Maintenance Notes

1. **IP Security**: 100% of your source code, Gemini prompts, and rules stay on Render Cloud. Clients never get access to source code.
2. **Render Sleep Spindown**: Render free plan instances sleep after 15 minutes of inactivity. Cold start takes ~30 seconds when opened after a break.
3. **Backup Guarantee**: Every push through `MiracleBridge` automatically creates a timestamped ZIP backup of the active client directory in `/BACKUPS/` before modifying DBF files.
