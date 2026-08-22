import json
from gemini_service import GeminiService

pdf_path = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/Test_Samples_And_Archives/DEMO SALES/Aksharbrahm/259876778999_1785754792241.pdf"

# Load settings
with open("backend/settings.json", "r") as f:
    settings = json.load(f)

api_key = settings.get("gemini_api_key")
gs = GeminiService(api_key=api_key)

print("🔍 Testing PDF chronology detection on Aksharbrahm PDF...")
chronology = gs.detect_pdf_chronology(pdf_path)
print(f"📊 Result: {chronology}")
