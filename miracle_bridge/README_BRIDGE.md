# 🌉 MiracleBridge — Local DBF Agent for Miracle Accounting

`MiracleBridge.exe` is a lightweight, background agent (5MB) designed to run locally on the client's Windows PC.

## 🎯 Purpose
When your Miracle AI Auto-Entry tool is hosted on the cloud (e.g. **Render.com** at `https://miracle-ai-app.onrender.com`), web browsers cannot directly write files to `C:\Miracle` on a local hard drive. 

`MiracleBridge` runs locally on `http://localhost:9123` and receives voucher payloads from the Render web app, safely injecting them into local Visual FoxPro DBF files (`RKACCT41.DBF`, `RKACCT01.DBF`, etc.).

---

## 🚀 How to Run locally on Windows

### Option 1: Direct Python Run
1. Install Python 3.10+ on Windows.
2. Install requirements:
   ```cmd
   pip install -r requirements_bridge.txt
   ```
3. Double click `start_bridge.bat` or run:
   ```cmd
   python miracle_bridge_agent.py
   ```
4. Verify by opening `http://localhost:9123/health` in your browser. You will see:
   ```json
   { "status": "online", "agent_name": "MiracleBridge Agent", "port": 9123 }
   ```

---

## 🔨 How to Build Standalone `MiracleBridge.exe`

To distribute a single `.exe` file to client computers so they don't need Python installed:

1. Install PyInstaller:
   ```cmd
   pip install pyinstaller
   ```
2. Run the build script:
   ```cmd
   python build_bridge_exe.py
   ```
3. The standalone binary will be created in `dist/MiracleBridge.exe`.
4. Copy `dist/MiracleBridge.exe` to the client's PC and place it in Startup folder or run on boot!

---

## 🛡️ Security & IP Protection
- All AI prompt logic, Gemini API engines, custom memory vault rules stay **100% protected on your Render cloud server**.
- Client PCs only run this lightweight bridge binary.
