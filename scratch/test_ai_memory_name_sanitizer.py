#!/usr/bin/env python3
"""
Empirical Verification Test Suite for AI Memory & Party Name Sanitizer Engine.
Tests dirty bank narrations, corporate suffixes, Title Case formatting, and Memory Vault purification.
"""
import sys
import os

# Add backend directory to sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from gemini_service import GeminiService
from ai_memory import AIMemoryVault

def main():
    print("=" * 70)
    print("🚀 RUNNING EMPIRICAL VERIFICATION FOR PARTY NAME SANITIZER ENGINE")
    print("=" * 70)

    test_cases = [
        ("UPI-329481903-PAWANKUMARSHAH04@OKICIC", "Pawan Kumar Shah"),
        ("DU82848 PTYES SENT USING PAYTM", ""),  # Cryptic ref code -> rejected to Suspense Account
        ("SHRIKANT DANGE56 KAXIS", "Shrikant Dange"),
        ("UPI-233100050316029-BONYKUNCHIKORVE@OKICICI SENT USING PHONEPE", "Bony Kunchi Korve"),
        ("RUPALIWAGH39@OKAXIS", "Rupali Wagh"),
        ("SAMPADAVEDAK@YBL", "Sampada Vedak"),
        ("SWATIBTILAK@NAVIAXIS", "Swati B Tilak"),
        ("PALLAVIPANCHAL793@OKA XIS", "Pallavi Panchal"),
        ("PE PULSE PVT LTD@OKAXIS", "Pe Pulse Pvt Ltd"),
        ("GIBZ SOLUTIONS PRIVATE LIMITED", "Gibz Solutions Private Limited"),
        ("AATHIRACHANDRAN2014@OKICICI", "Aathira Chandran"),
        ("NIKHILAKIRALE-1@KOTAK", "Nikhila Kirale"),
    ]

    passed = 0
    failed = 0

    print("\n--- TEST SUITE 1: Party Extraction & Title Case Sanitizer ---")
    for narr, expected in test_cases:
        extracted = GeminiService.extract_clean_party_from_narration(narr)
        if extracted.lower() == expected.lower():
            print(f"  ✅ PASS: '{narr}' -> '{extracted}'")
            passed += 1
        else:
            print(f"  ❌ FAIL: '{narr}' -> Got '{extracted}', Expected '{expected}'")
            failed += 1

    print("\n--- TEST SUITE 2: AI Memory Vault Purification ---")
    vault = AIMemoryVault()
    purify_res = vault.purify_all_client_memories()
    print(f"  Purification Result: {purify_res}")
    if purify_res.get("status") == "success":
        print(f"  ✅ PASS: Successfully purified memory vault files for {purify_res.get('processed_clients')} clients.")
        passed += 1
    else:
        print(f"  ❌ FAIL: Memory vault purification failed.")
        failed += 1

    print("\n=" * 70)
    total = passed + failed
    print(f"SUMMARY: {passed}/{total} Test Suites Passed ({passed/total*100:.1f}%)")
    print("=" * 70)

    if failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
