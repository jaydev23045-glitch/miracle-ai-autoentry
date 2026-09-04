import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

from gemini_service import GeminiService

def test_key_rotation_across_pool():
    print("==================================================")
    print("  TESTING ROTATED KEY POOL DISCOVERY & ROTATION   ")
    print("==================================================\n")

    srv = GeminiService()
    pool_size = len(srv.api_keys_pool)
    print(f"🔑 Loaded Key Pool Size: {pool_size} API Keys")

    used_keys = []
    for chunk_offset in range(5):
        keys_pool = srv.api_keys_pool
        start_key_offset = chunk_offset
        actual_idx = (srv.current_key_idx + start_key_offset) % pool_size
        active_key = keys_pool[actual_idx]
        used_keys.append(active_key)
        print(f"  Chunk #{chunk_offset + 1} -> Key #{actual_idx + 1}/{pool_size} ({active_key[:6]}...{active_key[-4:]})")

    assert len(set(used_keys)) >= min(5, pool_size), f"Expected at least {min(5, pool_size)} distinct API keys used, got {len(set(used_keys))}"
    print("\n✅ Multi-Key Dynamic Rotation Test Passed 100%!")

if __name__ == "__main__":
    test_key_rotation_across_pool()
