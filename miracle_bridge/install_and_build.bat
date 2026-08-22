@echo off
title MiracleBridge 1-Click Auto Setup & Exe Builder

:: Ensure working directory is set to the batch file folder
cd /d "%~dp0"

:: Auto-elevate Administrator Privileges on Windows
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting Administrator privileges to setup Python...
    powershell -Command "Start-Process '%~f0' -WorkingDirectory '%~dp0' -Verb RunAs"
    exit /b
)

:: Re-verify working directory inside elevated window
cd /d "%~dp0"

echo =================================================================
echo  Miracle AI Auto-Entry -- 1-Click Auto Setup & Builder
echo =================================================================
echo.

:: 0. Automatically stop any old running MiracleBridge.exe process
echo 🛑 Stopping any running MiracleBridge.exe instance...
taskkill /F /IM MiracleBridge.exe >nul 2>&1
timeout /t 1 /nobreak >nul

:: 1. Check if Python is installed
python --version >nul 2>&1
if %errorlevel% equ 0 goto HAS_PYTHON

echo ⚠️ Python is not detected on this computer.
echo 🚀 Auto-downloading Python 3.11 official installer for Windows...
echo.

powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.8/python-3.11.8-amd64.exe' -OutFile '%temp%\python_setup.exe'"

if not exist "%temp%\python_setup.exe" (
    echo ❌ Download failed. Opening browser to Python download page...
    start https://www.python.org/downloads/
    pause
    exit /b
)

echo ⚙️ Installing Python 3.11 automatically (Adding to PATH)...
"%temp%\python_setup.exe" /quiet InstallAllUsers=1 PrependPath=1 Include_pip=1

set "PATH=C:\Program Files\Python311;C:\Program Files\Python311\Scripts;%PATH%"
timeout /t 3 /nobreak >nul

:HAS_PYTHON
echo ✅ Python environment ready!

echo.
echo 📦 Installing required dependencies...
python -m pip install --upgrade pip
python -m pip install pyinstaller fastapi uvicorn dbfread dbf pydantic requests

echo.
echo 🔨 Compiling MiracleBridge.exe...
python build_bridge_exe.py

echo.
echo =================================================================
if exist "dist\MiracleBridge.exe" (
    echo 🎉 SUCCESS! MiracleBridge.exe built successfully at:
    echo 👉 %cd%\dist\MiracleBridge.exe
    echo.
    echo 🚀 Auto-launching new MiracleBridge.exe in background...
    start "" "%cd%\dist\MiracleBridge.exe"
    echo.
    echo ✅ MiracleBridge.exe is now ACTIVE and running on port 9123!
) else (
    echo ⚠️ Build complete. Check output above.
)
echo =================================================================
echo.
pause
