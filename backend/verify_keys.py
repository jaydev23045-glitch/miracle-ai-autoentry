import os
import sys
import json
import time
import urllib.request
import urllib.error

# Ensure backend path is in sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from core.config import get_gemini_api_key_pool, load_settings

def test_single_key(api_key: str) -> dict:
    """
    Tests a single Gemini API key against Google's API endpoint.
    Returns status: 'WORKING', 'QUOTA_EXHAUSTED', or 'INVALID'.
    """
    masked = (api_key[:6] + "..." + api_key[-4:]) if len(api_key) > 10 else api_key
    start_time = time.time()
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    
    req = urllib.request.Request(url, headers={"User-Agent": "MiracleAutoEntry/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            latency_ms = int((time.time() - start_time) * 1000)
            if resp.status == 200:
                return {
                    "key": masked,
                    "full_key": api_key,
                    "status": "WORKING",
                    "code": 200,
                    "latency_ms": latency_ms,
                    "message": "✅ Active & Working (0.05s response)"
                }
    except urllib.error.HTTPError as e:
        latency_ms = int((time.time() - start_time) * 1000)
        body = e.read().decode('utf-8', errors='ignore')
        if e.code == 429 or "RESOURCE_EXHAUSTED" in body or "quota" in body.lower():
            return {
                "key": masked,
                "full_key": api_key,
                "status": "QUOTA_EXHAUSTED",
                "code": 429,
                "latency_ms": latency_ms,
                "message": "⚠️ 429 Quota Exhausted (Daily Limit Reached)"
            }
        else:
            return {
                "key": masked,
                "full_key": api_key,
                "status": "INVALID",
                "code": e.code,
                "latency_ms": latency_ms,
                "message": f"❌ Invalid API Key ({e.code} Bad Request)"
            }
    except Exception as ex:
        latency_ms = int((time.time() - start_time) * 1000)
        return {
            "key": masked,
            "full_key": api_key,
            "status": "ERROR",
            "code": 500,
            "latency_ms": latency_ms,
            "message": f"❌ Network Connection Error: {ex}"
        }

def verify_all_keys() -> dict:
    """
    Scans and tests all Gemini API keys in the key pool.
    """
    settings = load_settings()
    pool = get_gemini_api_key_pool(settings)
    
    results = []
    working_count = 0
    quota_count = 0
    invalid_count = 0
    
    print("\n================================================================================")
    print(f"🔑 MIRACLE AI GEMINI KEY POOL HEALTH CHECK ({len(pool)} Keys Discovered)")
    print("================================================================================\n")
    
    if not pool:
        print("❌ No Gemini API keys found! Add keys to PROJECT.env or Settings modal.")
        return {
            "total_keys": 0,
            "working_keys": 0,
            "quota_exhausted_keys": 0,
            "invalid_keys": 0,
            "results": []
        }

    for idx, key in enumerate(pool, start=1):
        res = test_single_key(key)
        res["index"] = idx
        results.append(res)
        
        if res["status"] == "WORKING":
            working_count += 1
        elif res["status"] == "QUOTA_EXHAUSTED":
            quota_count += 1
        else:
            invalid_count += 1

        print(f"Key #{idx:02d} [{res['key']}]: {res['message']} ({res['latency_ms']}ms)")

    print("\n--------------------------------------------------------------------------------")
    print(f"📊 SUMMARY: Total Pool: {len(pool)} | ✅ Working: {working_count} | ⚠️ Quota Exhausted: {quota_count} | ❌ Invalid: {invalid_count}")
    print("================================================================================\n")
    
    return {
        "total_keys": len(pool),
        "working_keys": working_count,
        "quota_exhausted_keys": quota_count,
        "invalid_keys": invalid_count,
        "results": results
    }

if __name__ == "__main__":
    verify_all_keys()
