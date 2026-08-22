import json
import os
import sys

# Add backend to PYTHONPATH
sys.path.append(os.path.abspath("backend"))

from gemini_service import GeminiService
from ai_memory import AIMemoryVault

pdf_path = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/Test_Samples_And_Archives/DEMO SALES/Aksharbrahm/259876778999_1785754792241.pdf"

# Load settings
with open("backend/settings.json", "r") as f:
    settings = json.load(f)

api_key = settings.get("gemini_api_key")
gs = GeminiService(api_key=api_key)

# Mock client memory
client_memory = {
    "_client_id": "CMP0021",
    "existing_ledgers": [],
    "expense_mappings": {},
    "business_profile": ""
}

print("🚀 Running full chronological extraction on Aksharbrahm PDF...")
try:
    result = gs.extract_invoice_data(pdf_path, client_memory, "Bank Statements")
    print("\n✅ Extraction completed!")
    extracted_data = result.get("extracted_data", [])
    print(f"📊 Total Rows Extracted: {len(extracted_data)}")
    
    # Save results to inspect
    with open("scratch/extraction_result.json", "w") as out:
        json.dump(result, out, indent=2)
    print("💾 Saved full result to scratch/extraction_result.json")
    
    # Print the first 5 and last 5 rows to see what was extracted
    print("\n--- First 5 Rows (Newest-first in output) ---")
    for r in extracted_data[:5]:
        print(f"Date: {r.get('date')}, Narration: {r.get('narration')[:50]}, Type: {r.get('transaction_type')}, Amt: {r.get('amount')}, Bal: {r.get('running_balance')}")
        
    print("\n--- Last 5 Rows (Oldest-first in output) ---")
    for r in extracted_data[-5:]:
        print(f"Date: {r.get('date')}, Narration: {r.get('narration')[:50]}, Type: {r.get('transaction_type')}, Amt: {r.get('amount')}, Bal: {r.get('running_balance')}")

except Exception as e:
    print(f"❌ Extraction failed: {e}")
