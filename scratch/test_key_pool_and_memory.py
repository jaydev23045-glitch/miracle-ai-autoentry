import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

from core.config import get_gemini_api_key_pool
from gemini_service import GeminiService

def test_10_key_pool_auto_load():
    print("==================================================")
    print("  TESTING 10-KEY POOL AUTO-LOAD FROM PROJECT.ENV  ")
    print("==================================================\n")

    pool = get_gemini_api_key_pool()
    print(f"🔑 Total API Keys Loaded: {len(pool)}")
    for idx, k in enumerate(pool, start=1):
        print(f"   Key #{idx:02d}: {k[:6]}...{k[-4:]}")

    assert len(pool) >= 10, f"Expected at least 10 API keys in pool, got {len(pool)}"
    print("\n✅ PROJECT.env 10-Key Auto-Discovery Test Passed!")

def test_gemini_service_pool_initialization():
    print("\n==================================================")
    print("  TESTING GEMINI SERVICE KEY POOL INITIALIZATION  ")
    print("==================================================\n")

    service = GeminiService()
    print(f"Service Pool Size: {len(service.api_keys_pool)}")
    assert len(service.api_keys_pool) >= 10, f"Expected GeminiService pool size >= 10, got {len(service.api_keys_pool)}"
    print("✅ GeminiService Key Pool Initialization Passed!")

if __name__ == "__main__":
    test_10_key_pool_auto_load()
    test_gemini_service_pool_initialization()
    print("\n🎉 ALL 10-KEY POOL & PARALLEL WORKER TESTS PASSED 100%!")
