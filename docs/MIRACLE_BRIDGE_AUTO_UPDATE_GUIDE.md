# Master Architectural Guide: How Miracle Bridge Automatic OTA Updates Work Across All Clients

---

## 1. Executive Summary

Yes! You can update the Miracle Bridge Agent automatically across **ALL client PCs** without visiting each client or asking them to manually re-install.

The platform includes a built-in **Over-The-Air (OTA) Hot-Update Engine**:
1. Every client PC running `MiracleBridge.exe` checks the Render Cloud server (`/api/bridge/version`) in the background.
2. When you push a new code release or update `dbf_handler.py`, the cloud server notifies all client PCs that an update is available.
3. Every client PC automatically downloads the new binary, replaces `MiracleBridge.exe`, and restarts port `9123` seamlessly in 3 seconds — **with 0 clicks required from the client!**

---

## 2. OTA Auto-Update System Architecture

```
┌───────────────────────────────────────────────────────────┐
│ ☁️ Render Cloud Backend (https://miracle-ai-autoentry.onrender.com) │
│                                                           │
│  • Endpoint 1: GET /api/bridge/version                    │
│    Returns: {"needs_update": true, "latest_version": "1.2.0"} │
│                                                           │
│  • Endpoint 2: GET /api/bridge/download                   │
│    Serves: MiracleBridge.exe (Compiled Binary)            │
└─────────────────────────────▲─────────────────────────────┘
                              │
                    Every 4 hours (Background HTTP Query)
                              │
┌─────────────────────────────┴─────────────────────────────┐
│ 💻 Client Windows PC (Client Machine #1, #2, #3...)       │
│                                                           │
│ 1. Background loop checks /api/bridge/version             │
│ 2. Detects version bump (v1.1.0 -> v1.2.0)                │
│ 3. Downloads binary to MiracleBridge_new.exe              │
│ 4. Spawns update_bridge.bat script                       │
│ 5. Hot-swaps executable & restarts Port 9123              │
└───────────────────────────────────────────────────────────┘
```

---

## 3. How to Release an Automatic Update to All Clients (3-Step Workflow)

When you make improvements to `dbf_handler.py` or `miracle_bridge_agent.py`:

### Step 1: Bump the Version Number
In `miracle_bridge/miracle_bridge_agent.py`, update `BRIDGE_VERSION`:
```python
# Line 162
BRIDGE_VERSION = "1.2.0"  # Increment from 1.1.0 to 1.2.0
```

In `backend/routers/vouchers.py`, update `LATEST_BRIDGE_VERSION`:
```python
# Line 2335
LATEST_BRIDGE_VERSION = "1.2.0"
```

### Step 2: Build the Compiled Binary (`MiracleBridge.exe`)
On your development machine, run the build script:
```bash
python3 miracle_bridge/build_bridge_exe.py
```
*(Or double-click `miracle_bridge/install_and_build.bat` on Windows)*.

This compiles the updated code into `miracle_bridge/dist/MiracleBridge.exe`.

### Step 3: Push to GitHub / Deploy to Render
Commit and push your changes to GitHub:
```bash
git add .
git commit -m "Release Miracle Bridge v1.2.0 with enhanced multi-year product scanning"
git push origin main
```

**That’s it!** Once Render builds the deployment, **all client PCs will automatically update themselves**.

---

## 4. Code Evidence & Mechanism Breakdown

### A. Background Check Loop ([`miracle_bridge_agent.py`](file:///Users/jaydevnakum/Work%20Place/WORK/APP%20DETAILS/Mirracle%20Auto%20Entre%20Sale%20or%20Purchase%20or%20Bank/miracle_bridge/miracle_bridge_agent.py#L225-L256))
```python
def check_for_updates_background(manual_trigger: bool = False):
    """Queries Render Cloud version endpoint for OTA update triggers."""
    import requests
    check_url = f"{CLOUD_URL}/api/bridge/version?current_version={BRIDGE_VERSION}"
    r = requests.get(check_url, timeout=10)
    if r.status_code == 200:
        data = r.json()
        if data.get("needs_update") and data.get("download_url"):
            print(f"🔔 Update available: v{data.get('latest_version')} (Current: v{BRIDGE_VERSION})")
            trigger_ota_update(data.get("download_url"))
```

### B. Hot Replacement & Seamless Process Restart ([`miracle_bridge_agent.py`](file:///Users/jaydevnakum/Work%20Place/WORK/APP%20DETAILS/Mirracle%20Auto%20Entre%20Sale%20or%20Purchase%20or%20Bank/miracle_bridge/miracle_bridge_agent.py#L182-L218))
```python
def trigger_ota_update(download_url: str):
    """Downloads updated binary, creates batch replacement script, and restarts MiracleBridge."""
    # 1. Download updated executable to MiracleBridge_new.exe
    resp = requests.get(full_url, stream=True, timeout=30)
    with open("MiracleBridge_new.exe", "wb") as f:
        f.write(resp.content)
        
    # 2. Create batch script to release process locks, swap file, and restart
    bat_content = """@echo off
timeout /t 2 /nobreak > nul
del /f /q "MiracleBridge.exe"
move /y "MiracleBridge_new.exe" "MiracleBridge.exe"
start "" "MiracleBridge.exe"
del "%~f0"
"""
    with open("update_bridge.bat", "w") as bf:
        bf.write(bat_content)

    # 3. Launch updater script in background and terminate old process
    subprocess.Popen(["cmd.exe", "/c", "update_bridge.bat"], creationflags=0x08000000)
    sys.exit(0)
```

---

## 5. Summary Checklist for Auto-Updates

| Trigger Event | Server Action | Client PC Action |
|---|---|---|
| Developer bumps version to `1.2.0` and pushes to main | Render hosts new `MiracleBridge.exe` binary on `/api/bridge/download` | Client background check detects `needs_update = true` |
| Client PC pings `/api/bridge/version` | Responds with `latest_version: 1.2.0` | Downloads `MiracleBridge_new.exe` silently in background |
| Binary Download Completes | Server completes HTTP streaming | Batch script swaps binary, restarts `MiracleBridge.exe`, and resumes port 9123 |
