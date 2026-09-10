import re

def parse_currency(val) -> float:
    """
    Unified math-safe currency parsing engine.
    Sanitizes commas, currency symbols, and parenthesized negative numbers,
    and returns a clean float. Default fallback is 0.0.
    """
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
        
    val_str = str(val).strip()
    if not val_str:
        return 0.0
        
    # Check for parenthesized negative number like (500.00)
    is_negative = False
    if val_str.startswith('(') and val_str.endswith(')'):
        is_negative = True
        val_str = val_str[1:-1].strip()
        
    # Remove currency signs and commas
    val_str = val_str.replace(',', '').replace('₹', '').replace('$', '').strip()
    
    try:
        res = float(val_str)
        return -res if is_negative else res
    except ValueError:
        # Fallback to regex extraction of the first float/int found in the string
        match = re.search(r'[-+]?\d*\.\d+|\d+', val_str)
        if match:
            try:
                res = float(match.group())
                return -res if is_negative else res
            except ValueError:
                pass
        return 0.0

import os
import sys
import gc
import platform
import time

_SERVER_START_TIME = time.time()

def get_process_memory_mb() -> float:
    """Returns current process Resident Set Size (RSS) memory in Megabytes."""
    try:
        import psutil
        return round(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024), 2)
    except Exception:
        pass

    if os.path.exists("/proc/self/status"):
        try:
            with open("/proc/self/status", "r") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        parts = line.split()
                        kb = float(parts[1])
                        return round(kb / 1024.0, 2)
        except Exception:
            pass

    try:
        import resource
        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if platform.system() == "Darwin":
            return round(usage / (1024 * 1024), 2)
        else:
            return round(usage / 1024.0, 2)
    except Exception:
        return 0.0

def get_server_health_metrics() -> dict:
    """
    Returns comprehensive server health metrics including RSS memory usage,
    512MB RAM percentage, uptime, active client, and Gemini key pool status.
    """
    from core.config import load_settings, get_gemini_api_key_pool

    rss_mb = get_process_memory_mb()
    ram_limit_mb = 512.0
    usage_pct = round((rss_mb / ram_limit_mb) * 100, 1) if rss_mb > 0 else 0.0

    if rss_mb == 0:
        health_status = "OK"
    elif usage_pct < 50.0:
        health_status = "EXCELLENT"
    elif usage_pct < 75.0:
        health_status = "GOOD"
    elif usage_pct < 90.0:
        health_status = "WARN_HIGH_RAM"
    else:
        health_status = "CRITICAL_OOM_RISK"

    uptime_sec = round(time.time() - _SERVER_START_TIME, 1)

    settings = {}
    try:
        settings = load_settings()
    except Exception:
        pass

    keys_pool = get_gemini_api_key_pool(settings)
    active_client = settings.get("active_client_id", "Not Configured")

    return {
        "status": "online",
        "service": "Miracle AI Auto-Entry Backend",
        "health": health_status,
        "memory": {
            "rss_mb": rss_mb,
            "limit_mb": ram_limit_mb,
            "usage_pct": usage_pct,
            "status": health_status
        },
        "system": {
            "uptime_seconds": uptime_sec,
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "workers": 1,
            "gc_count": list(gc.get_count())
        },
        "config": {
            "active_client_id": active_client,
            "gemini_keys_available": len(keys_pool),
            "gemini_model": settings.get("gemini_model", "gemini-3.1-flash-lite")
        }
    }

