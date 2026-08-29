import os
import shutil
import re
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from core.config import (
    SystemSettings,
    load_settings,
    save_settings_to_file,
    clean_api_key,
    get_company_name,
    discover_clients
)
from dbf_handler import MiracleDBFHandler
from ai_memory import AIMemoryVault
from gemini_service import GeminiService

router = APIRouter()

def clean_gemini_error(e: Exception) -> str:
    error_msg = str(e)
    if "API_KEY_INVALID" in error_msg or "API key not valid" in error_msg or ("400" in error_msg and "key" in error_msg.lower()):
        return "Invalid Gemini API Key. Please open 'Configure Settings' in the sidebar, enter a valid Google Gemini API Key (starts with AIzaSy...), and click Save Settings."
    if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
        return "Gemini API Quota Exceeded (429 Resource Exhausted). Free Tier keys are limited to 20 requests per day. Please check your Gemini API billing details or wait for the quota to reset."
    return error_msg

@router.get("/api/test-keys")
@router.post("/api/test-keys")
def test_all_keys_endpoint():
    """Endpoint to test and verify all Gemini API keys in the key pool."""
    from verify_keys import verify_all_keys
    return verify_all_keys()

@router.get("/api/health")
def read_health():
    return {"status": "Miracle AI Backend is running."}

@router.get("/api/upload-status")
@router.post("/api/upload-status")
def get_upload_status():
    """Poll the status of the current deep extraction progress."""
    try:
        import json
        status_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "extraction_status.json")
        if os.path.exists(status_path):
            with open(status_path, "r") as f:
                return json.load(f)
        return {"filename": "", "part": 0, "total": 0, "progress_pct": 0, "percentage": 0, "message": "Idle"}
    except Exception as e:
        return {"filename": "", "part": 0, "total": 0, "progress_pct": 0, "percentage": 0, "message": f"Error: {e}"}

@router.get("/api/settings")
def get_settings():
    settings = load_settings()
    clients = discover_clients(settings["miracle_base_path"])
    
    client_id = settings.get("active_client_id", "")
    profile = ""
    product_mappings = {"gst_rules": {}, "keyword_rules": {}}
    try:
        vault = AIMemoryVault(vault_path=settings.get("memory_path", "../AI_Memory_Vault"))
        profile = vault.get_business_profile(client_id)
        product_mappings = vault.get_product_mappings(client_id)
    except Exception:
        pass
        
    return {
        "settings": settings,
        "clients": clients,
        "business_profile": profile,
        "product_mappings": product_mappings
    }

@router.post("/api/settings")
def update_settings(payload: SystemSettings):
    settings = load_settings()
    payload_dict = payload.model_dump()
    if "gemini_api_key" in payload_dict:
        payload_dict["gemini_api_key"] = clean_api_key(payload_dict["gemini_api_key"])
    for k, v in payload_dict.items():
        if k in ['sales_series', 'sales_prefix', 'purchase_prefix', 'gemini_api_key', 'miracle_base_path', 'memory_path']:
            if not v and settings.get(k):
                continue
        settings[k] = v
        
    save_settings_to_file(settings)
    return {"status": "success", "settings": settings}

@router.get("/api/clients")
def get_clients():
    settings = load_settings()
    clients = discover_clients(settings["miracle_base_path"])
    return {"clients": clients}

@router.get("/api/client-setup-ids")
def get_client_setup_ids(client_id: str):
    if not client_id:
        raise HTTPException(status_code=400, detail="client_id is required")
        
    settings = load_settings()
    base_path = settings.get("miracle_base_path")
    if not base_path:
        raise HTTPException(status_code=400, detail="Miracle Base Path not configured")
        
    client_path = os.path.join(base_path, client_id)
    if not os.path.exists(client_path):
        return {"sales_setup_id": 5, "purchase_setup_id": 6}
        
    handler = MiracleDBFHandler(client_path=client_path)
    discovered = handler.auto_discover_prefixes(force_separate=True)
    
    return {
        "sales_setup_id": discovered.get("sales_setup_id", 5),
        "purchase_setup_id": discovered.get("purchase_setup_id", 6)
    }

@router.get("/api/client-years")
def get_client_years(client_id: str):
    if not client_id:
        raise HTTPException(status_code=400, detail="client_id is required")
        
    settings = load_settings()
    base_path = settings.get("miracle_base_path")
    if not base_path:
        raise HTTPException(status_code=400, detail="Miracle Base Path not configured")
        
    client_path = os.path.join(base_path, client_id)
    if not os.path.exists(client_path):
        return {"years": [], "recommended": ""}
        
    handler = MiracleDBFHandler(client_path=client_path)
    available = handler.get_available_year_folders()
    recommended = handler.get_latest_year_folder()
    bounds_map = handler.get_all_year_folder_bounds()
    
    mapped_years = []
    for yinfo in available:
        y = yinfo['name']
        is_valid = yinfo['is_valid']
        has_transactions = yinfo['has_transactions']
        
        b_info = bounds_map.get(y, {})
        f_start = b_info.get("fy_start", "")
        f_end = b_info.get("fy_end", "")
        
        if f_start and f_end and len(f_start) >= 4 and len(f_end) >= 4:
            fy_s_yr = f_start[:4]
            fy_e_yr = f_end[:4]
            label = f"{fy_s_yr}-{str(fy_e_yr)[-2:]} ({y})"
        else:
            try:
                num = int(y[2:])
                fy_end = 2000 + num
                fy_start = fy_end - 1
                label = f"{fy_start}-{str(fy_end)[-2:]} ({y})"
            except Exception:
                label = y
        
        if not is_valid:
            label += " ⚠️ Missing DBF files"
        elif not has_transactions:
            label += " (New / Empty)"
            
        mapped_years.append({
            "folder": y,
            "label": label,
            "is_valid": is_valid,
            "has_transactions": has_transactions,
            "recommended": y == recommended,
            "fy_start": f_start,
            "fy_end": f_end
        })
        
    return {"years": mapped_years, "recommended": recommended}

class DiscoverClientsPayload(BaseModel):
    path: str

@router.post("/api/discover-clients")
def discover_clients_endpoint(payload: DiscoverClientsPayload):
    path = payload.path.strip()
    if not path:
        return {"clients": []}
    
    if (path.startswith('"') and path.endswith('"')) or (path.startswith("'") and path.endswith("'")):
        path = path[1:-1]
        
    clients = []
    if os.path.exists(path):
        try:
            for item in os.listdir(path):
                full_path = os.path.join(path, item)
                if os.path.isdir(full_path) and item.upper().startswith("CMP"):
                    name = get_company_name(full_path)
                    clients.append({"id": item, "name": name or "Unknown Company"})
        except Exception as e:
            print(f"Error reading directory: {str(e)}")
            
    return {"clients": sorted(clients, key=lambda x: x["id"]) if clients else []}

@router.post("/api/train_specifications")
async def train_specifications(file: UploadFile = File(...)):
    """Receives a client specifications file, extracts the text, and saves to AI Memory."""
    settings = load_settings()
    api_key = settings.get("gemini_api_key", "")
    client_id = settings.get("active_client_id", "")
    
    if not client_id:
        raise HTTPException(status_code=400, detail="No active client selected.")
        
    temp_file_path = f"spec_{file.filename}"
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        gemini = GeminiService(
            api_key=api_key, 
            model_name=settings.get("gemini_model", "gemini-3.1-flash-lite"),
            is_paid_api_key=settings.get("is_paid_api_key", False)
        )
        spec_data = gemini.extract_structured_specifications(temp_file_path)
        if not spec_data or not isinstance(spec_data, dict):
            spec_data = {}
        summary_text = spec_data.get("specifications_summary", "")
        expense_mappings = spec_data.get("expense_mappings", {})
        product_mappings = spec_data.get("product_mappings", {})
        
        vault = AIMemoryVault(vault_path=settings.get("memory_path", "../AI_Memory_Vault"))
        
        if summary_text:
            vault.set_specifications(client_id, summary_text)
            
        learned_count = 0
        if expense_mappings and isinstance(expense_mappings, dict):
            valid_mappings = {k: v for k, v in expense_mappings.items() if k and v}
            if valid_mappings:
                vault.batch_add_expense_mappings(client_id, valid_mappings)
                learned_count = len(valid_mappings)
                    
        if product_mappings and isinstance(product_mappings, dict):
            for k, v in product_mappings.items():
                if k and v:
                    vault.add_product_keyword_rule(client_id, k, v)
                    
        return {
            "status": "success", 
            "message": f"Successfully trained AI Memory JSON for client {client_id}! Learned {learned_count} direct ledger rules and updated AI specifications.",
            "learned_rules_count": learned_count,
            "summary": summary_text
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error training specs: {e}")
        error_detail = clean_gemini_error(e)
        status_code = 400 if ("API_KEY_INVALID" in str(e) or "API key not valid" in str(e)) else (429 if ("RESOURCE_EXHAUSTED" in str(e) or "429" in str(e)) else 500)
        raise HTTPException(status_code=status_code, detail=error_detail)
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

@router.post("/api/train_brain")
def train_brain():
    """Analyzes the active client's history and generates a Business Profile."""
    settings = load_settings()
    client_id = settings.get("active_client_id", "")
    client_path = os.path.join(settings["miracle_base_path"], client_id)
    
    if not os.path.exists(client_path):
        raise HTTPException(status_code=404, detail=f"Client folder not found at {client_path}")
        
    try:
        from business_analyzer import BusinessAnalyzer
        
        analyzer = BusinessAnalyzer(client_path)
        raw_data = analyzer.generate_raw_business_data()
        
        gemini = GeminiService(
            api_key=settings.get("gemini_api_key", ""), 
            model_name=settings.get("gemini_model", "gemini-3.1-flash-lite"),
            is_paid_api_key=settings.get("is_paid_api_key", False)
        )
        business_profile = gemini.generate_business_profile(raw_data)
        
        handler = MiracleDBFHandler(client_path)
        tech_settings = handler.auto_discover_prefixes(force_separate=True)
        bill_formats = handler.detect_bill_formats()
        
        tech_settings.update(bill_formats)

        vault = AIMemoryVault(vault_path=settings.get("memory_path", "../AI_Memory_Vault"))
        vault.set_business_profile(client_id, business_profile)
        vault.set_company_settings(client_id, tech_settings)
        
        return {"status": "success", "profile": business_profile, "settings": tech_settings}
    except Exception as e:
        error_detail = clean_gemini_error(e)
        status_code = 429 if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e) else 500
        raise HTTPException(status_code=status_code, detail=error_detail)

class ProfilePayload(BaseModel):
    profile: str

@router.post("/api/save_profile")
def save_profile(payload: ProfilePayload):
    """Manually updates the active client's Business Profile."""
    settings = load_settings()
    client_id = settings.get("active_client_id", "")
    try:
        vault = AIMemoryVault(vault_path=settings.get("memory_path", "../AI_Memory_Vault"))
        vault.set_business_profile(client_id, payload.profile)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/train-memory")
def train_memory():
    """Triggers the AI Memory Vault to scan historical DBFs and learn expense mappings."""
    settings = load_settings()
    client_id = settings.get("active_client_id", "")
    if not client_id:
        raise HTTPException(status_code=400, detail="No active client selected")
        
    try:
        vault = AIMemoryVault(vault_path=settings.get("memory_path", "../AI_Memory_Vault"))
        client_path = os.path.join(settings["miracle_base_path"], client_id)
        trained_count = vault.train_from_history(client_id, client_path)
        return {"status": "success", "message": f"Successfully trained AI Memory! Learned {trained_count} expense mappings across database years.", "trained_count": trained_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/prune-memory")
def prune_memory():
    """Manually cleans, prunes, and deduplicates the active client's memory JSON."""
    settings = load_settings()
    client_id = settings.get("active_client_id", "")
    if not client_id:
        raise HTTPException(status_code=400, detail="No active client selected")
        
    try:
        vault = AIMemoryVault(vault_path=settings.get("memory_path", "../AI_Memory_Vault"))
        memory = vault.load_memory(client_id)
        vault.save_memory(client_id, memory)
        
        pruned_memory = vault.load_memory(client_id)
        final_count = len(pruned_memory.get("expense_mappings", {}))
        return {"status": "success", "final_count": final_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class VerifyGstinPayload(BaseModel):
    gstin: str

@router.post("/api/verify_gstin")
def verify_gstin(payload: VerifyGstinPayload):
    """Verifies the mathematical/structural format of an Indian GSTIN."""
    gstin = payload.gstin.strip().upper()
    if not gstin:
        return {"valid": False, "message": "GSTIN is empty."}
        
    pattern = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}[Z]{1}[0-9A-Z]{1}$"
    if re.match(pattern, gstin):
        return {"valid": True, "message": "Valid GSTIN format."}
    else:
        return {"valid": False, "message": "Invalid GSTIN format. Check state code or structure."}
