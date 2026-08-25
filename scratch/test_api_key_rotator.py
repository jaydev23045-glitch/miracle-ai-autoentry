import sys
import os

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Set mock env variables matching Render dashboard setup
os.environ["GEMINI_API_KEY"] = "AIzaSyMockKey000000000000000000000001"
os.environ["GEMINI_API_KEY_2"] = "AIzaSyMockKey000000000000000000000002"
os.environ["GEMINI_API_KEY_3"] = "AIzaSyMockKey000000000000000000000003"
os.environ["GEMINI_API_KEY_4"] = "AIzaSyMockKey000000000000000000000004"
os.environ["GEMINI_API_KEY_5"] = "AIzaSyMockKey000000000000000000000005"
os.environ["GEMINI_API_KEY_6"] = "AIzaSyMockKey000000000000000000000006"
os.environ["GEMINI_API_KEY_7"] = "AIzaSyMockKey000000000000000000000007"
os.environ["GEMINI_API_KEY_8"] = "AIzaSyMockKey000000000000000000000008"
os.environ["GEMINI_API_KEY_9"] = "AIzaSyMockKey000000000000000000000009"
os.environ["GEMINI_API_KEY_10"] = "AIzaSyMockKey000000000000000000000010"

print("🧪 Starting 10-Key API Pool Rotator Verification Suite...")

from core.config import get_gemini_api_key_pool
pool = get_gemini_api_key_pool()

print(f"  Discovered {len(pool)} keys in environment API key pool:")
for idx, k in enumerate(pool):
    print(f"   - Key #{idx+1}: {k}")

assert len(pool) == 10, f"Expected 10 keys, but found {len(pool)}"
print("  ✅ All 10 Gemini API keys successfully gathered from environment variables!")

from gemini_service import GeminiService
service = GeminiService()
assert len(service.api_keys_pool) == 10, "GeminiService failed to initialize 10-key pool"
assert service.api_keys_pool[0] == "AIzaSyMockKey000000000000000000000001"
assert service.api_keys_pool[9] == "AIzaSyMockKey000000000000000000000010"

print("  ✅ GeminiService correctly initialized 10-Key Rotator Pool!")
print("🎉 10-Key API Pool Rotator Verification PASSED 100%!")
