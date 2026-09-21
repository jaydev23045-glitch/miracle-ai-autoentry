"""
HMAC-SHA256 Security & Hardware Authentication Module
Secures API communication between Miracle Desktop Bridge Agent and Cloud Server.
"""

import hmac
import hashlib
import time
import uuid
import platform
import subprocess
import logging
from typing import Tuple, Dict, Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_BRIDGE_SECRET = "MIRACLE_BRIDGE_SECURE_HMAC_KEY_2026_V2"

def generate_hmac_signature(secret_key: str, timestamp: str, nonce: str, payload_str: str) -> str:
    """
    Generates a deterministic HMAC-SHA256 signature for a request payload.
    """
    if not secret_key:
        secret_key = DEFAULT_BRIDGE_SECRET
    message = f"{timestamp}:{nonce}:{payload_str}".encode('utf-8')
    return hmac.new(secret_key.encode('utf-8'), message, hashlib.sha256).hexdigest()

def verify_hmac_signature(
    secret_key: str,
    timestamp: str,
    nonce: str,
    payload_str: str,
    signature: str,
    max_drift_seconds: int = 300
) -> Tuple[bool, str]:
    """
    Verifies an incoming HMAC-SHA256 request signature and checks for timestamp drift (replay attacks).
    """
    if not secret_key:
        secret_key = DEFAULT_BRIDGE_SECRET

    if not signature:
        return False, "Missing X-Signature header"
    if not timestamp:
        return False, "Missing X-Timestamp header"
    if not nonce:
        return False, "Missing X-Nonce header"
        
    try:
        req_time = float(timestamp)
        now = time.time()
        if abs(now - req_time) > max_drift_seconds:
            return False, f"Timestamp drift excessive ({round(abs(now - req_time), 1)}s)"
    except ValueError:
        return False, "Invalid timestamp format"
        
    expected_signature = generate_hmac_signature(secret_key, timestamp, nonce, payload_str)
    if not hmac.compare_digest(expected_signature, signature):
        return False, "Signature mismatch / Payload tampered"
        
    return True, "Valid signature"

def get_hardware_fingerprint() -> str:
    """
    Generates a unique hardware signature hash for the client machine.
    """
    system_info = []
    system_info.append(platform.node())
    system_info.append(platform.machine())
    system_info.append(platform.processor())
    
    if platform.system() == "Windows":
        try:
            cmd = "wmic csproduct get uuid"
            output = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
            lines = [line.strip() for line in output.splitlines() if line.strip() and "UUID" not in line]
            if lines:
                system_info.append(lines[0])
        except Exception:
            pass
    elif platform.system() == "Darwin":
        try:
            cmd = "ioreg -d2 -c IOPlatformExpertDevice | grep IOPlatformUUID"
            output = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
            if "IOPlatformUUID" in output:
                uuid_val = output.split("=")[-1].replace('"', '').strip()
                system_info.append(uuid_val)
        except Exception:
            pass

    # Fallback to MAC address based node UUID
    system_info.append(str(uuid.getnode()))
    raw_str = "|".join(system_info)
    return hashlib.sha256(raw_str.encode('utf-8')).hexdigest()
