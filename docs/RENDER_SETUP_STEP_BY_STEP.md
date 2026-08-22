# 🚀 Step-by-Step Render Setup Plan (Zero Code Changes Required)

This guide shows you how to deploy your project to **Render.com** right now without touching or modifying any of your source code.

---

## 📌 Step 1: Push Code to a Private GitHub Repository (5 Mins)

1. Open **[GitHub.com](https://github.com/)** and log in to your account.
2. Click **New Repository**.
3. Name it: `miracle-ai-autoentry`.
4. **CRITICAL**: Select **PRIVATE** (so nobody else can see your repository).
5. Push your local project folder to GitHub:
   ```bash
   git init
   git add .
   git commit -m "Production ready release"
   git branch -M main
   git remote add origin https://github.com/YOUR_GITHUB_USERNAME/miracle-ai-autoentry.git
   git push -u origin main
   ```

---

## 📌 Step 2: Deploy on Render.com (10 Mins)

1. Open **[Render.com](https://render.com/)** and sign up / log in.
2. Click the blue **New +** button at the top right $\rightarrow$ Select **Web Service**.
3. Connect your GitHub account and select your **`miracle-ai-autoentry`** private repository.
4. Fill in the deployment form:

| Setting Field | What to Enter / Select |
|---|---|
| **Name** | `miracle-ai-app` (or your chosen app name) |
| **Region** | `Singapore` or `Frankfurt` (closest to India for high speed) |
| **Branch** | `main` |
| **Root Directory** | Leave blank |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r backend/requirements.txt` |
| **Start Command** | `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT` |
| **Instance Type** | Select **Free ($0/month)** |

5. Click **Create Web Service**.

---

## 📌 Step 3: Access & Test Your Live Web URL

1. Render will spend 2 to 3 minutes building your server environment.
2. Once complete, you will see a green **Live** status badge.
3. Render will display your live public Web URL:
   👉 **`https://miracle-ai-app.onrender.com`**
4. Open the link in your browser!
5. Go to **Settings** in the dashboard UI:
   - Client enters their **Gemini API Key**.
   - Client tests uploading Bank Statements & Sales/Purchase invoices live on the cloud!

---

## 📌 Step 4: How Clients Will Push to Miracle DBF

When the client is using the live Render Web URL (`https://miracle-ai-app.onrender.com`):
1. All AI extraction, PDF parsing, grid rendering, and memory vault matching happen on the Render Cloud.
2. When the client clicks **Push to Miracle**, the browser sends the extracted entries to their local `MiracleBridge.exe` running on `http://localhost:9123`, which instantly writes to `C:\Miracle\CMP0005\YR25`.

---

## 🎯 Summary Checklist
- [x] **No source code changes needed** — your FastAPI backend and frontend already support this!
- [ ] Push local project to **Private GitHub Repository**.
- [ ] Create **Render Free Web Service** with build/start commands above.
- [ ] Test your live URL: `https://miracle-ai-app.onrender.com`.
