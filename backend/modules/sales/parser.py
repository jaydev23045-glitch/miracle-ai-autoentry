import re
import os
import json
import pandas as pd
from typing import List, Dict, Any
from core.models import InvoiceSchema, InvoiceItemSchema

class SalesParser:
    def __init__(self, api_key: str | None = None, model_name: str = "gemini-3.1-flash-lite"):
        self.api_key = api_key
        self.model_name = model_name

    def validate_and_normalize_gst_pct(self, gst_pct: float) -> float:
        VALID_RATES = {0.0, 0.1, 0.25, 1.5, 2.5, 3.0, 5.0, 6.0, 9.0, 12.0, 14.0, 18.0, 28.0}
        
        # If it's a fraction (e.g. 0.18 for 18%), multiply by 100 first
        if gst_pct < 1.0 and gst_pct > 0:
            gst_pct = gst_pct * 100
            
        rounded = round(gst_pct, 2)
        if rounded in VALID_RATES:
            return rounded
            
        if round(rounded * 2.0, 2) in VALID_RATES:
            return rounded
            
        return 18.0

    def parse_gst_pct(self, val) -> float:
        val_str = str(val).strip()
        if "(" in val_str and ")" in val_str:
            try:
                inside = val_str.split("(")[1].split(")")[0]
                val_str = inside
            except:
                pass
        
        try:
            raw_val = float(val_str)
        except:
            # Extract first number from string
            match = re.search(r"[-+]?\d*\.\d+|\d+", val_str)
            raw_val = float(match.group()) if match else 0.0
            
        return self.validate_and_normalize_gst_pct(raw_val)

    def parse_gst_amt(self, val) -> float:
        val_str = str(val).strip()
        if "(" in val_str:
            val_str = val_str.split("(")[0].strip()
        try:
            return float(val_str.replace(",", "").replace("₹", ""))
        except:
            return 0.0

    def clean_invoice_data(self, result_json: dict, client_memory: dict, module: str = "Sales") -> dict:
        """
        Cleans and validates the JSON output from Gemini using Pydantic models.
        """
        if isinstance(result_json, list):
            result_json = {"status": "success", "extracted_data": result_json}
        if not isinstance(result_json, dict):
            return {"status": "error", "extracted_data": []}
        if "extracted_data" not in result_json or not isinstance(result_json["extracted_data"], list):
            result_json["extracted_data"] = []

        cleaned_vouchers = []
        INVALID_ITEM_WORDS = {"sale", "sales", "purchase", "purchases", "creditnote", "debitnote", "credit", "debit", "journal", "receipt", "payment", "voucher"}

        for row in result_json["extracted_data"]:
            party_name = str(row.get("party_name", "")).strip().upper()
            
            # Clean and filter items
            items_raw = row.get("items", [])
            valid_items = []
            for item in items_raw:
                item_name = str(item.get("name", "")).strip()
                item_norm = item_name.lower().replace(" ", "").replace(".", "").replace("_", "")
                
                is_invalid = False
                if item_norm in INVALID_ITEM_WORDS:
                    is_invalid = True
                elif len(item_name) < 2:
                    is_invalid = True
                    
                if is_invalid:
                    continue
                
                # Parse GST Pct
                gst_pct_val = item.get("gst_pct")
                if gst_pct_val is None or (isinstance(gst_pct_val, float) and pd.isna(gst_pct_val)):
                    gst_pct_val = item.get("gst_amt", 0.0)
                
                item_gst = self.parse_gst_pct(gst_pct_val)
                item_amt = self.parse_gst_amt(item.get("amount", 0.0))
                item_taxable = self.parse_gst_amt(item.get("taxable", 0.0))
                
                valid_items.append(InvoiceItemSchema(
                    name=item_name,
                    qty=float(item.get("qty", 1.0)) if item.get("qty") else 1.0,
                    rate=float(item.get("rate", 0.0)) if item.get("rate") else 0.0,
                    gst_pct=item_gst,
                    taxable_amount=item_taxable or (item_amt - (item.get("gst_amt") or 0.0)),
                    gst_amount=self.parse_gst_amt(item.get("gst_amt", 0.0)),
                    hsn=str(item.get("hsn_code" if "hsn_code" in item else "hsn", "")).strip(),
                    uom=str(item.get("uom", "UNT")).strip(),
                    discount=self.parse_gst_amt(item.get("discount", 0.0))
                ))
            
            if not valid_items and items_raw:
                default_name = "SALES" if module == "Sales" else "PURCHASES"
                valid_items.append(InvoiceItemSchema(
                    name=default_name,
                    qty=1.0,
                    rate=0.0,
                    gst_pct=18.0
                ))

            # Parse root fields
            gst_val = row.get("gst_pct")
            if gst_val is None or (isinstance(gst_val, float) and pd.isna(gst_val)):
                gst_val = row.get("gst_amt", 0.0)
                
            raw_gst = self.parse_gst_pct(gst_val)

            # Build cleaned voucher
            cleaned_vouchers.append(InvoiceSchema(
                bill_no=str(row.get("bill_no", "")).strip(),
                date=str(row.get("date", "")).strip(),
                party_name=str(row.get("party_name", "")).strip(),
                party_gstin=str(row.get("party_gstin", "")).strip(),
                taxable_amount=float(row.get("taxable_amount" if "taxable_amount" in row else "taxable", 0.0)),
                cgst=float(row.get("cgst", 0.0)),
                sgst=float(row.get("sgst", 0.0)),
                igst=float(row.get("igst", 0.0)),
                gst=float(row.get("gst", 0.0)),
                discount=float(row.get("discount", 0.0)),
                freight=float(row.get("freight", 0.0)),
                tcs=float(row.get("tcs", 0.0)),
                tds=float(row.get("tds", 0.0)),
                total=float(row.get("total", 0.0)),
                items=valid_items,
                confidence_score=float(row.get("confidence_score", 100.0)),
                flags=list(row.get("flags", []))
            ).dict())

        result_json["extracted_data"] = cleaned_vouchers
        return result_json
