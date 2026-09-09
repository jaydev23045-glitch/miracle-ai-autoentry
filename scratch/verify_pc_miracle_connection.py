#!/usr/bin/env python3
"""
Miracle AI Auto-Entry — Client PC Diagnostic & Connection Verification Tool
-----------------------------------------------------------------------------
This script tests and verifies:
1. Miracle folder paths on the PC (C:\\Miracle, D:\\Miracle, C:\\Miracle9070, etc.)
2. Discovery of client folders (CMPxxxx)
3. Reading RKACCM01.DBF (ledgers) & RKACCM11.DBF (account groups)
4. Financial year folder detection (YRxx)
5. Local Miracle Bridge Agent connection (http://127.0.0.1:9123/status)
"""

import os
import sys
import json
import urllib.request
import urllib.error

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

def check_bridge_agent():
    print("=" * 65)
    print("🔍 1. TESTING LOCAL MIRACLE BRIDGE AGENT (Port 9123)")
    print("=" * 65)
    url = "http://127.0.0.1:9123/status"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "DiagnosticScript"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            print(f"✅ Bridge Status: ONLINE (200 OK)")
            print(f"   Agent Name: {data.get('agent_name', 'Unknown')}")
            print(f"   Version:    {data.get('version', 'Unknown')}")
            print(f"   Port:       {data.get('port', 9123)}")
            return True
    except urllib.error.URLError as e:
        print(f"❌ Bridge Status: OFFLINE / UNREACHABLE ({e.reason})")
        print("   👉 MiracleBridge.exe is not running on this PC, or port 9123 is blocked by Firewall.")
        return False
    except Exception as e:
        print(f"⚠️ Bridge Status Check Error: {e}")
        return False

def discover_miracle_paths():
    print("\n" + "=" * 65)
    print("🔍 2. DISCOVERING MIRACLE DIRECTORIES ON LOCAL HARD DRIVES")
    print("=" * 65)
    
    try:
        from miracle_bridge_agent import scan_all_miracle_paths
        discovered = scan_all_miracle_paths()
        found_paths = []
        for item in discovered:
            p = item["path"]
            cmps = item["clients"]
            found_paths.append((p, cmps))
            print(f"✅ Found Miracle Directory: {p} (Contains {len(cmps)} client CMP folders)")
        if not found_paths:
            print("❌ No Miracle installation paths found on local drives.")
        return found_paths
    except Exception as e:
        print(f"⚠️ Error during path discovery: {e}")
        return []

def test_dbf_ledger_capture(base_path, client_id):
    print("\n" + "=" * 65)
    print(f"🔍 3. TESTING DBF LEDGER & DATA CAPTURE FOR {client_id}")
    print("=" * 65)
    
    client_path = os.path.join(base_path, client_id)
    if not os.path.exists(client_path):
        print(f"❌ Client path does not exist: {client_path}")
        return
        
    print(f"📂 Client Folder Path: {client_path}")
    
    try:
        from dbf_handler import MiracleDBFHandler
        handler = MiracleDBFHandler(client_path)
        
        company_name = handler.get_company_name()
        print(f"🏢 Company Name: {company_name or 'N/A'}")
        
        years = handler.get_available_year_folders()
        rec_year = handler.get_latest_year_folder()
        print(f"📅 Year Folders Detected: {[y['name'] for y in years]} (Recommended: {rec_year})")
        
        target_year = rec_year or "YR25"
        
        # Check files inside year folder or root
        yr_path = os.path.join(client_path, target_year)
        ledger_dbf = os.path.join(yr_path, "RKACCM01.DBF") if os.path.exists(yr_path) else os.path.join(client_path, "RKACCM01.DBF")
        group_dbf = os.path.join(yr_path, "RKACCM11.DBF") if os.path.exists(yr_path) else os.path.join(client_path, "RKACCM11.DBF")
        
        print(f"   RKACCM01.DBF (Ledgers): {'✅ Present' if os.path.exists(ledger_dbf) else '❌ MISSING (' + ledger_dbf + ')'}")
        print(f"   RKACCM11.DBF (Groups):  {'✅ Present' if os.path.exists(group_dbf) else '❌ MISSING (' + group_dbf + ')'}")
        
        ledgers = handler.get_all_ledgers(target_year)
        print(f"📊 Total Classified Ledgers Captured: {len(ledgers)}")
        
        if ledgers:
            # Breakdown by Nature
            sales_count = sum(1 for l in ledgers if l.get("nature") == "Sales")
            purchase_count = sum(1 for l in ledgers if l.get("nature") == "Purchase")
            bank_count = sum(1 for l in ledgers if l.get("nature") == "Bank")
            party_count = sum(1 for l in ledgers if l.get("nature") in ["Debtors", "Creditors", "Party"])
            expense_count = sum(1 for l in ledgers if l.get("nature") in ["Indirect Expenses", "Direct Expenses"])
            
            print(f"   • Sales Ledgers:             {sales_count}")
            print(f"   • Purchase Ledgers:          {purchase_count}")
            print(f"   • Bank Accounts:             {bank_count}")
            print(f"   • Party Ledgers (Deb/Cred):  {party_count}")
            print(f"   • Expense Accounts:          {expense_count}")
            
            print("\n📋 Sample Captured Ledgers:")
            for l in ledgers[:7]:
                print(f"   - [{l.get('code')}] {l.get('name')} | Group: {l.get('group_name')} | Nature: {l.get('nature')}")
        else:
            print("⚠️ WARNING: 0 Ledgers were captured! Check if RKACCM01.DBF is empty or corrupt.")
            
    except Exception as e:
        print(f"❌ Error during DBF Ledger Capture: {e}")
        import traceback
        traceback.print_exc()

def main():
    print("🚀 MIRACLE AI AUTO-ENTRY — CLIENT PC DIAGNOSTIC TOOL")
    print("=" * 65)
    
    bridge_online = check_bridge_agent()
    found_paths = discover_miracle_paths()
    
    if found_paths:
        base_path, cmps = found_paths[0]
        if cmps:
            # Find a CMP with year folders if possible
            target_cmp = cmps[0]
            for c in cmps:
                c_p = os.path.join(base_path, c)
                if any(os.path.isdir(os.path.join(c_p, d)) and d.upper().startswith("YR") for d in os.listdir(c_p)):
                    target_cmp = c
                    break
            test_dbf_ledger_capture(base_path, target_cmp)
        else:
            print("⚠️ No CMP client folders found inside Miracle path.")
    else:
        print("❌ No Miracle installation paths found on this machine.")
        
    print("\n" + "=" * 65)
    print("📌 DIAGNOSTIC SUMMARY & TROUBLESHOOTING RECOMMENDATIONS")
    print("=" * 65)
    if not bridge_online:
        print("1. 🔴 MiracleBridge.exe is OFFLINE. Run MiracleBridge.exe on the client PC.")
    else:
        print("1. 🟢 MiracleBridge.exe is ONLINE on port 9123.")
        
    if not found_paths:
        print("2. 🔴 Miracle folder not found. Check if Miracle is installed on C:, D:, or E: drive.")
    else:
        print(f"2. 🟢 Miracle folder found at: {found_paths[0][0]}")

if __name__ == "__main__":
    main()
