"""
AI Business Profiler - Gap 2 Implementation
"""
import json, sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from business_analyzer import BusinessAnalyzer
from ai_memory import AIMemoryVault

_INDUSTRY_OPTIONS = [
    "Manufacturing & Industrial",
    "Retail & Trading",
    "Restaurant & Food Services",
    "IT Services & Software",
    "Healthcare & Pharma",
    "Construction & Real Estate",
    "Transport & Logistics",
    "Agriculture & Farming",
    "Education & Coaching",
    "Finance & Investment",
    "Service Business (General)",
    "Other / Mixed",
]

class AIBusinessProfiler:
    def __init__(self, client_path, client_id, api_key, model_name="gemini-2.5-flash",
                 vault_path="../AI_Memory_Vault", tenant_id=None, miracle_base_path="", company_name=""):
        self.client_path = client_path
        self.client_id = client_id
        self.api_key = api_key
        self.model_name = model_name
        self.vault = AIMemoryVault(vault_path=vault_path)
        self.tenant_id = tenant_id
        self.miracle_base_path = miracle_base_path
        self.company_name = company_name

    def _load_existing_profile(self):
        memory = self.vault.load_memory(self.client_id, tenant_id=self.tenant_id,
            miracle_base_path=self.miracle_base_path, company_name=self.company_name)
        return memory.get("business_profile", "")

    def _save_profile(self, profile):
        memory = self.vault.load_memory(self.client_id, tenant_id=self.tenant_id,
            miracle_base_path=self.miracle_base_path, company_name=self.company_name)
        memory["business_profile"] = profile
        self.vault.save_memory(self.client_id, memory, tenant_id=self.tenant_id,
            miracle_base_path=self.miracle_base_path, company_name=self.company_name)
        print(f"[AI Profiler] Business profile saved for client {self.client_id!r}")

    def _generate_profile_via_gemini(self, raw_data):
        try:
            industry_list = "\n".join(f"- {i}" for i in _INDUSTRY_OPTIONS)
            prompt = f"""You are a forensic accountant and business analyst.
A client historical accounting data from Miracle ERP is aggregated below.
Analyse and provide a structured business profile.

{raw_data}

Return JSON ONLY in this format:
{{
  "industry": "One of the options listed below",
  "business_summary": "2-3 sentence description",
  "primary_revenue_source": "Main income source",
  "primary_customers": ["Customer type 1"],
  "primary_suppliers": ["Supplier type 1"],
  "primary_expenses": ["Expense category 1"],
  "key_accounting_notes": "GST, export, cash observations"
}}

Available Industries:
{industry_list}
"""
            result_text = ""
            try:
                from google import genai
                from google.genai import types
                client = genai.Client(api_key=self.api_key)
                response = client.models.generate_content(
                    model=self.model_name, contents=prompt,
                    config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1))
                result_text = response.text.strip() if response and hasattr(response, "text") and response.text else ""
            except Exception:
                import google.generativeai as legacy_genai
                legacy_genai.configure(api_key=self.api_key)
                model = legacy_genai.GenerativeModel(self.model_name)
                response = model.generate_content(prompt)
                result_text = response.text.strip() if response and hasattr(response, "text") and response.text else ""

            if result_text.startswith("```"):
                parts = result_text.split("```")
                result_text = parts[1] if len(parts) > 1 else ""
                if result_text.startswith("json"):
                    result_text = result_text[4:]
            parsed = json.loads(result_text)
            lines = [
                "Industry: " + str(parsed.get("industry", "Unknown")),
                "Business Summary: " + str(parsed.get("business_summary", "")),
                "Primary Revenue: " + str(parsed.get("primary_revenue_source", "")),
                "Key Customers: " + ", ".join(parsed.get("primary_customers", []) if isinstance(parsed.get("primary_customers"), list) else []),
                "Key Suppliers: " + ", ".join(parsed.get("primary_suppliers", []) if isinstance(parsed.get("primary_suppliers"), list) else []),
                "Primary Expenses: " + ", ".join(parsed.get("primary_expenses", []) if isinstance(parsed.get("primary_expenses"), list) else []),
                "Accounting Notes: " + str(parsed.get("key_accounting_notes", "")),
            ]
            return "\n".join(lines)
        except Exception as e:
            print(f"[AI Profiler] Gemini call failed: {e}")
            return ""

    def run(self, force_refresh=False):
        existing = self._load_existing_profile()
        if existing and not force_refresh:
            print(f"[AI Profiler] Profile already exists for {self.client_id!r}. Pass force_refresh=True to regenerate.")
            return {"success": True, "profile": existing, "source": "existing"}
        print(f"[AI Profiler] Analysing business data for {self.client_id!r}...")
        try:
            analyzer = BusinessAnalyzer(self.client_path)
            raw_data = analyzer.generate_raw_business_data()
        except Exception as e:
            print(f"[AI Profiler] BusinessAnalyzer failed: {e}")
            return {"success": False, "profile": "", "source": "failed"}
        if not raw_data or "None detected" in raw_data:
            print(f"[AI Profiler] No meaningful DBF data for {self.client_id!r}")
            return {"success": False, "profile": "", "source": "failed"}
        profile = self._generate_profile_via_gemini(raw_data)
        if not profile:
            return {"success": False, "profile": "", "source": "failed"}
        self._save_profile(profile)
        return {"success": True, "profile": profile, "source": "newly_generated"}
