"""
Miracle AI Auto-Entry — PyInstaller Executable Builder for MiracleBridge.exe
-----------------------------------------------------------------------------
Run this script on a Windows PC to compile miracle_bridge_agent.py into a 
standalone MiracleBridge.exe binary for client distribution.

Usage:
    python build_bridge_exe.py
"""

import os
import subprocess
import sys

def build_exe():
    print("🔨 Starting PyInstaller build for MiracleBridge.exe...")
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(current_dir, "miracle_bridge_agent.py")
    backend_dir = os.path.abspath(os.path.join(current_dir, "..", "backend"))

    if not os.path.exists(script_path):
        print(f"❌ Error: Script file not found at '{script_path}'")
        sys.exit(1)

    command = [
        "pyinstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name=MiracleBridge",
        f"--paths={backend_dir}",
        "--hidden-import=core",
        "--hidden-import=core.config",
        "--hidden-import=dbf_handler",
        "--hidden-import=routers",
        "--hidden-import=routers.vouchers",
        "--hidden-import=dbfread",
        "--hidden-import=dbf",
        "--clean",
        script_path
    ]

    print(f"Executing build command: {' '.join(command)}")
    try:
        res = subprocess.run(command, check=True)
        print("\n✅ MiracleBridge.exe successfully compiled!")
        print(f"📁 Output binary location: {os.path.join(current_dir, 'dist', 'MiracleBridge.exe')}")
        print("💡 Place MiracleBridge.exe on the client's PC and double-click to start local DBF agent!")
    except Exception as e:
        print(f"❌ Build failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build_exe()
