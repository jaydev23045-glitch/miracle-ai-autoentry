import os
import re
import json
import difflib
import pandas as pd
from datetime import datetime
from core.utils import parse_currency

COLUMN_MAPS = {
    "bill_no": ["invoiceno", "invoiceno.", "invoice_no", "invoice_no.", "invno", "invno.", "billinvoiceno", "billno", "billno.", "bill_no.", "billnumber", "invoicenumber", "voucherno", "vchno", "vchno.", "bill/invoiceno", "bill/invoice_no.", "srno", "srno.", "sr_no.", "docno", "docno.", "serialno", "refno", "refno.", "reference_no"],
    "date": ["date", "invoicedate", "billdate", "voucherdate", "vchdate", "bill/invoicedate", "invoicedt", "billdt", "invoice_date"],
    "party_name": ["partyname", "party", "party_name", "customername", "suppliername", "vendorname", "customer", "vendor", "supplier", "accountname", "ledgername", "partysname", "party's_name"],
    "party_gstin": ["partysgstinno", "partysgstin", "gstin", "gstno", "partygst", "tin", "gstinno", "partygstin", "partygstinno", "party's_gstin_no."],
    "item_name": ["itemname", "item", "productname", "product", "stockitem", "stockname", "item_name"],
    "hsn": ["hsnsac", "hsn", "sac", "hsncode", "saccode", "hsn/sac", "hsn_code"],
    "qty": ["quantity", "qty", "qnty", "nos", "pieces", "volume"],
    "rate": ["price/unit", "price", "rate", "unitprice", "rate/unit", "unitrate", "price_unit"],
    "gst_pct": ["gst%", "gstpct", "tax%", "taxpct", "taxrate", "gstrate", "gst_percentage", "gst_rate", "gst"],
    "gst_amt": ["gstamount", "gstamt", "taxamount", "taxamt", "gst_amount", "gst"],
    "discount": ["discountamount", "discount", "disc", "discamount", "discount_amount"],
    "freight": ["freight", "freightamount", "freightcharges", "transport", "transportcharges", "packing", "forwarding", "loading"],
    "taxable_amt": ["taxableamount", "taxable", "taxablevalue", "taxableamt", "basicamount", "basic"],
    "total_amt": ["totalamount", "total", "invoicetotal", "billamount", "totalvalue", "invvalue", "nettotal", "grandtotal", "total_amount", "billtotal", "nettotalamount", "amount", "itemamount"]
}

INVALID_ITEM_WORDS = {"sale", "sales", "purchase", "purchases", "creditnote", "debitnote", "credit", "debit", "journal", "receipt", "payment", "voucher"}

def find_and_clean_header(df_raw):
    all_aliases = set()
    for aliases in COLUMN_MAPS.values():
        for a in aliases:
            clean = str(a).strip().lower().replace(".", "").replace(" ", "").replace("_", "").replace("/", "").replace("'", "")
            all_aliases.add(clean)
            
    header_idx = -1
    for idx, row in df_raw.iterrows():
        match_count = 0
        for val in row:
            if pd.isna(val): continue
            val_clean = str(val).strip().lower().replace(".", "").replace(" ", "").replace("_", "").replace("/", "").replace("'", "")
            if val_clean in all_aliases:
                match_count += 1
        if match_count >= 3:
            header_idx = idx
            break
            
    if header_idx != -1:
        new_cols = []
        header_row = df_raw.iloc[header_idx]
        for col_val in header_row:
            if pd.isna(col_val):
                new_cols.append(f"Unnamed_{len(new_cols)}")
            else:
                new_cols.append(str(col_val).strip())
                
        df_cleaned = df_raw.iloc[header_idx + 1:].copy()
        df_cleaned.columns = new_cols
        return df_cleaned.reset_index(drop=True)
    return df_raw

def safe_float(val, default=0.0):
    try:
        return parse_currency(val)
    except:
        return default

def parse_gst_pct(val):
    val_str = str(val).strip()
    if "(" in val_str and ")" in val_str:
        try:
            inside = val_str.split("(")[1].split(")")[0]
            val_str = inside
        except:
            pass
    raw_val = safe_float(val_str)
    VALID_RATES = {0.0, 0.1, 0.25, 1.5, 2.5, 3.0, 5.0, 6.0, 9.0, 12.0, 14.0, 18.0, 28.0}
    if raw_val < 1.0 and raw_val > 0:
        raw_val = raw_val * 100
    rounded = round(raw_val, 2)
    if rounded in VALID_RATES:
        return rounded
    if round(rounded * 2.0, 2) in VALID_RATES:
        return rounded
    return 18.0

def parse_gst_amt(val):
    val_str = str(val).strip()
    if "(" in val_str:
        val_str = val_str.split("(")[0].strip()
    return safe_float(val_str)

def normalize_sheet_columns(df):
    def clean_str(s):
        return str(s).strip().lower().replace(".", "").replace(" ", "").replace("_", "").replace("/", "").replace("'", "")
    
    df_copy = df.copy()
    # 1. Deduplicate raw column names so every column is unique
    new_cols = []
    seen = {}
    for col in df_copy.columns:
        col_str = str(col).strip()
        if col_str in seen:
            seen[col_str] += 1
            new_cols.append(f"{col_str}_dup{seen[col_str]}")
        else:
            seen[col_str] = 0
            new_cols.append(col_str)
    df_copy.columns = new_cols

    rename_dict = {}
    used_orig_cols = set()
    resolved = {}
    
    for key, aliases in COLUMN_MAPS.items():
        matched_col = None
        for alias in aliases:
            norm_alias = clean_str(alias)
            for c in df_copy.columns:
                if c in used_orig_cols:
                    continue
                if clean_str(c) == norm_alias:
                    matched_col = c
                    break
            if matched_col:
                break
        if matched_col:
            resolved[key] = matched_col
            rename_dict[matched_col] = key
            used_orig_cols.add(matched_col)

    # Pass 2: Substring / Partial Match Fallback for essential fields (bill_no, date, party_name)
    if not resolved.get("bill_no"):
        bill_keywords = ["invoice", "invoiceno", "bill", "billno", "vch", "voucherno", "docno", "refno", "srno", "serial"]
        for c in df_copy.columns:
            if c in used_orig_cols: continue
            c_clean = clean_str(c)
            if any(kw in c_clean for kw in bill_keywords):
                resolved["bill_no"] = c
                rename_dict[c] = "bill_no"
                used_orig_cols.add(c)
                print(f"🎯 Substring Column Match: '{c}' mapped to 'bill_no'")
                break

    if not resolved.get("date"):
        date_keywords = ["date", "dt", "invoicedate", "billdate", "vchdate"]
        for c in df_copy.columns:
            if c in used_orig_cols: continue
            c_clean = clean_str(c)
            if any(kw in c_clean for kw in date_keywords):
                resolved["date"] = c
                rename_dict[c] = "date"
                used_orig_cols.add(c)
                print(f"🎯 Substring Column Match: '{c}' mapped to 'date'")
                break

    # Pass 3: Data Content Pattern Fallback for bill_no if header was custom or unmapped
    if not resolved.get("bill_no"):
        inv_pattern = re.compile(r'^[A-Za-z0-9\-_]{2,10}[/\-][A-Za-z0-9\-_]{1,12}$|^INV[-_]?\d+|^BILL[-_]?\d+', re.I)
        for c in df_copy.columns:
            if c in used_orig_cols: continue
            sample_vals = df_copy[c].dropna().astype(str).str.strip().tolist()[:10]
            match_count = sum(1 for val in sample_vals if inv_pattern.search(val))
            if match_count >= 2:
                resolved["bill_no"] = c
                rename_dict[c] = "bill_no"
                used_orig_cols.add(c)
                print(f"🔮 Data Pattern Match: Column '{c}' auto-detected as 'bill_no' based on values {sample_vals[:3]}")
                break

    renamed_df = df_copy.rename(columns=rename_dict)
    
    # 2. Enforce 100% unique string names for all renamed columns
    final_cols = []
    seen_renamed = {}
    for c in renamed_df.columns:
        c_str = str(c).strip()
        if c_str in seen_renamed:
            seen_renamed[c_str] += 1
            final_cols.append(f"{c_str}_dup{seen_renamed[c_str]}")
        else:
            seen_renamed[c_str] = 0
            final_cols.append(c_str)
    renamed_df.columns = final_cols
    
    return renamed_df, resolved

def get_group_key(row):
    b_val = row.get("bill_no")
    b_str = str(b_val).strip() if pd.notna(b_val) else ""
    if b_str and b_str.lower() != "nan":
        return b_str
    d_val = str(row.get("date", "")).strip()
    p_val = str(row.get("party_name", "")).strip()
    return f"NO_INV_{d_val}_{p_val}"

def parse_excel_to_json(file_path: str, company_state_code: str = '24', instruction: str = '', product_catalog: dict = None) -> dict:
    """Parses the Sales/Purchases Excel spreadsheet into standard JSON using dynamic column normalization with AI product catalog auto-filling."""
    try:
        xl = pd.ExcelFile(file_path)
        sheet_names = xl.sheet_names
        
        # --- SHEET DETECTION & SELECTION STRATEGY ---
        # 0. Check if user prompt instruction explicitly targets a specific sheet by name (e.g. "read only Miracle Sale Import")
        requested_sheet_data = []
        if instruction:
            inst_clean = str(instruction).lower().strip()
            for s in sheet_names:
                s_clean = str(s).lower().strip()
                s_compact = s_clean.replace(" ", "").replace("_", "").replace("-", "")
                inst_compact = inst_clean.replace(" ", "").replace("_", "").replace("-", "")
                if (s_clean in inst_clean or s_compact in inst_compact or inst_clean in s_clean) and len(s_clean) >= 3:
                    try:
                        df_raw = pd.read_excel(file_path, sheet_name=s)
                        df_raw = find_and_clean_header(df_raw)
                        if len(df_raw) > 0:
                            df_norm, resolved = normalize_sheet_columns(df_raw)
                            for col_name in ["date", "bill_no", "party_name", "party_gstin"]:
                                if col_name in df_norm.columns:
                                    df_norm[col_name] = df_norm[col_name].ffill()
                            requested_sheet_data.append((s, df_norm))
                            print(f"🎯 User specified sheet '{s}' via prompt instruction '{instruction}'. Reading this sheet directly.")
                            break
                    except Exception as e:
                        print(f"Error parsing user-requested sheet '{s}': {e}")

        # 1. Check for Miracle macro pre-processed sheets (e.g. Miracle Registered B2B, Miracle Unregistered B2C, Miracle Cash Sales)
        miracle_sheet_names = [s for s in sheet_names if any(kw in str(s).lower() for kw in ["miracle registered", "miracle unregistered", "miracle cash"])]
        miracle_sheets_data = []
        if miracle_sheet_names:
            for m_sheet in miracle_sheet_names:
                try:
                    df_raw = pd.read_excel(file_path, sheet_name=m_sheet)
                    df_raw = find_and_clean_header(df_raw)
                    if len(df_raw) > 0:
                        df_norm, resolved = normalize_sheet_columns(df_raw)
                        if resolved["bill_no"] and resolved["date"] and resolved["party_name"]:
                            for col_name in ["date", "bill_no", "party_name", "party_gstin"]:
                                if col_name in df_norm.columns:
                                    df_norm[col_name] = df_norm[col_name].ffill()
                            miracle_sheets_data.append((m_sheet, df_norm))
                except Exception:
                    pass

        flat_sheets_data = []
        header_only_sheets_data = []

        if requested_sheet_data:
            flat_sheets_data = requested_sheet_data
        elif miracle_sheets_data:
            print(f"✨ Found Miracle pre-processed sheets: {[s for s, _ in miracle_sheets_data]}. Using these directly to prevent duplicate voucher creation.")
            flat_sheets_data = miracle_sheets_data
        else:
            # 2. Check for 2-Sheet structure (e.g. 'Sale Report' + 'Sale Items')
            report_sheet = None
            items_sheet = None
            for s in sheet_names:
                s_lower = str(s).lower().replace(" ", "").replace("_", "")
                if s_lower in ["salereport", "salesreport", "purchasereport"]:
                    report_sheet = s
                elif s_lower in ["saleitems", "salesitems", "purchaseitems", "itemreport", "itemsreport"]:
                    items_sheet = s

            if report_sheet and items_sheet and report_sheet != items_sheet:
                print(f"🎯 Detected 2-Sheet layout: Report Sheet '{report_sheet}' + Items Sheet '{items_sheet}'. Performing deterministic metadata join.")
                try:
                    df_rep_raw = pd.read_excel(file_path, sheet_name=report_sheet)
                    df_item_raw = pd.read_excel(file_path, sheet_name=items_sheet)
                    df_rep_raw = find_and_clean_header(df_rep_raw)
                    df_item_raw = find_and_clean_header(df_item_raw)
                    df_rep, res_rep = normalize_sheet_columns(df_rep_raw)
                    df_item, res_item = normalize_sheet_columns(df_item_raw)

                    # Forward fill ONLY date and bill_no within df_item (NEVER party_name across different bills)
                    for col_name in ["date", "bill_no"]:
                        if col_name in df_rep.columns: df_rep[col_name] = df_rep[col_name].ffill()
                        if col_name in df_item.columns: df_item[col_name] = df_item[col_name].ffill()

                    if "party_name" in df_rep.columns: df_rep["party_name"] = df_rep["party_name"].ffill()
                    if "party_gstin" in df_rep.columns: df_rep["party_gstin"] = df_rep["party_gstin"].ffill()

                    # Build authoritative metadata dictionary from Report sheet keyed by bill_no
                    report_meta = {}
                    for _, r_row in df_rep.iterrows():
                        b_no = str(r_row.get("bill_no", "")).strip()
                        if b_no and b_no.lower() != "nan":
                            if b_no.endswith(".0"): b_no = b_no[:-2]
                            gstin_val = str(r_row.get("party_gstin", "")).strip() if pd.notna(r_row.get("party_gstin")) else ""
                            if gstin_val.lower() == "nan": gstin_val = ""
                            p_name = str(r_row.get("party_name", "")).strip() if pd.notna(r_row.get("party_name")) else ""
                            if p_name.lower() == "nan": p_name = ""
                            pay_type = str(r_row.get("payment_type", "")).strip() if pd.notna(r_row.get("payment_type")) else ""
                            report_meta[b_no] = {
                                "party_gstin": gstin_val,
                                "payment_type": pay_type,
                                "party_name": p_name,
                                "date": r_row.get("date")
                            }

                    # Authoritatively assign Party Name, GSTIN, and Date from Report Sheet (Sheet 1) into Items Sheet (Sheet 2) per bill_no
                    party_list = []
                    gstin_list = []
                    date_list = []
                    for _, i_row in df_item.iterrows():
                        b_no = str(i_row.get("bill_no", "")).strip()
                        if b_no.endswith(".0"): b_no = b_no[:-2]
                        
                        meta = report_meta.get(b_no, {})
                        
                        # Party Name from Report sheet takes precedence over item sheet
                        rep_party = meta.get("party_name", "")
                        item_party = str(i_row.get("party_name", "")).strip() if pd.notna(i_row.get("party_name")) else ""
                        final_party = rep_party if rep_party and rep_party.lower() != "nan" else item_party
                        party_list.append(final_party)
                        
                        # GSTIN
                        rep_gstin = meta.get("party_gstin", "")
                        item_gstin = str(i_row.get("party_gstin", "")).strip() if pd.notna(i_row.get("party_gstin")) else ""
                        final_gstin = rep_gstin if rep_gstin and rep_gstin.lower() != "nan" else item_gstin
                        gstin_list.append(final_gstin)
                        
                        # Date
                        rep_date = meta.get("date")
                        item_date = i_row.get("date")
                        final_date = rep_date if pd.notna(rep_date) else item_date
                        date_list.append(final_date)

                    df_item["party_name"] = party_list
                    df_item["party_gstin"] = gstin_list
                    if any(pd.notna(d) for d in date_list):
                        df_item["date"] = date_list

                    flat_sheets_data = [(items_sheet, df_item)]
                except Exception as ex_join:
                    print(f"⚠️ 2-Sheet join failed: {ex_join}. Falling back to standard sheet scan.")

            # 3. Standard Sheet Scan if no Miracle sheets or 2-sheet join occurred
            if not flat_sheets_data:
                for sheet in sheet_names:
                    try:
                        df_raw = pd.read_excel(file_path, sheet_name=sheet)
                        df_raw = find_and_clean_header(df_raw)
                        df_norm, resolved = normalize_sheet_columns(df_raw)
                        if resolved["bill_no"] and resolved["date"] and resolved["party_name"]:
                            for col_name in ["date", "bill_no", "party_name", "party_gstin"]:
                                if col_name in df_norm.columns:
                                    df_norm[col_name] = df_norm[col_name].ffill()
                            
                            if resolved["item_name"]:
                                flat_sheets_data.append((sheet, df_norm))
                            else:
                                header_only_sheets_data.append((sheet, df_norm))
                    except Exception:
                        pass

        if flat_sheets_data:
            # User instruction sheet filtering
            if instruction:
                instr_lower = instruction.lower()
                matching_sheets = []
                for sheet_name, df_sheet in flat_sheets_data:
                    sn_lower = sheet_name.lower()
                    if sn_lower in instr_lower or f"only {sn_lower}" in instr_lower or f"{sn_lower} sheet" in instr_lower or f"tab {sn_lower}" in instr_lower:
                        matching_sheets.append((sheet_name, df_sheet))
                if matching_sheets:
                    print(f"🎯 Extra AI Guideline Sheet Filter Applied: Filtering flat_sheets_data for requested sheet(s): {[s for s, _ in matching_sheets]}")
                    flat_sheets_data = matching_sheets
                    
            df_flat = pd.concat([df for name, df in flat_sheets_data], ignore_index=True)
            initial_row_count = len(df_flat)
            
            # Only perform deduplication if multiple duplicate sheets were concatenated
            if len(flat_sheets_data) > 1:
                subset_cols = [col for col in ["date", "bill_no", "party_name", "item_name", "qty", "rate", "taxable_amt", "total_amt"] if col in df_flat.columns]
                if len(subset_cols) >= 4:
                    df_flat = df_flat.drop_duplicates(subset=subset_cols)
                else:
                    df_flat = df_flat.drop_duplicates()
                    
                removed_count = initial_row_count - len(df_flat)
                if removed_count > 0:
                    print(f"🧹 Smart Deduplicator removed {removed_count} redundant transactions across duplicate sheets.")
            
            summary_keywords = ["total for", "subtotal", "grand total", "total amount", "total gst"]
            
            def is_summary_row(row):
                p_val = str(row.get("party_name", "")).strip().lower()
                i_val = str(row.get("item_name", "")).strip().lower()
                b_val = str(row.get("bill_no", "")).strip().lower()
                d_val = str(row.get("date", "")).strip().lower()
                combined = f"{p_val} {i_val} {b_val} {d_val}"
                return any(kw in combined for kw in summary_keywords)
                
            df_flat = df_flat[~df_flat.apply(is_summary_row, axis=1)]
            total_rows = len(df_flat)
            print(f"Detected Flat File format. Forward-filled & cleaned (subtotals excluded): {total_rows} total rows.")
            
            df_flat['Group_Key'] = df_flat.apply(get_group_key, axis=1)
            df_flat = df_flat[df_flat["date"].notna()]
            
            extracted_data = []
            grouped = df_flat.groupby("Group_Key")
            
            for group_key, group in grouped:
                first_row = group.iloc[0]
                date_raw = first_row["date"]
                
                if isinstance(date_raw, datetime):
                    date_str = date_raw.strftime("%Y-%m-%d")
                elif isinstance(date_raw, (int, float)) or (isinstance(date_raw, str) and date_raw.replace('.', '').isdigit() and float(date_raw) > 30000):
                    try:
                        date_str = (pd.to_datetime(float(date_raw), unit='D', origin='1899-12-30')).strftime("%Y-%m-%d")
                    except Exception:
                        date_str = str(date_raw).strip()
                else:
                    date_str = str(date_raw).strip()
                    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y", "%d-%m-%y", "%Y/%m/%d"):
                        try:
                            date_dt = datetime.strptime(date_str, fmt)
                            date_str = date_dt.strftime("%Y-%m-%d")
                            break
                        except ValueError:
                            pass
                            
                party_name = str(first_row["party_name"]).strip()
                party_gstin = str(first_row.get("party_gstin", "")).strip() if pd.notna(first_row.get("party_gstin")) else ""
                if party_gstin.lower() == "nan":
                    party_gstin = ""
                    
                inv_no = ""
                if not str(group_key).startswith("NO_INV_"):
                    inv_no = str(group_key)
                    if inv_no.endswith(".0"):
                        inv_no = inv_no[:-2]
                        
                items_list = []
                taxable_sum = 0.0
                cgst_sum = 0.0
                sgst_sum = 0.0
                igst_sum = 0.0
                discount_sum = 0.0
                freight_sum = 0.0
                total_amt = 0.0
                
                for _, item_row in group.iterrows():
                    raw_item_val = item_row.get("item_name")
                    item_name = str(raw_item_val).strip() if pd.notna(raw_item_val) else ""
                    if not item_name or item_name.lower() == "nan":
                        raw_desc_val = item_row.get("description")
                        item_name = str(raw_desc_val).strip() if pd.notna(raw_desc_val) else ""
                    if not item_name or item_name.lower() == "nan":
                        item_name = "SALES"
                    
                    item_norm = item_name.lower().replace(" ", "").replace(".", "").replace("_", "")
                    if item_norm in INVALID_ITEM_WORDS:
                        print(f"⚠️ Skipping invalid item name (transaction type): '{item_name}'")
                        continue
                        
                    hsn = str(item_row.get("hsn", "")).strip() if pd.notna(item_row.get("hsn")) else ""
                    if hsn.endswith(".0"): hsn = hsn[:-2]
                    if hsn.lower() == "nan": hsn = ""
                        
                    qty = safe_float(item_row.get("qty", 1.0)) if pd.notna(item_row.get("qty")) else 1.0
                    rate = safe_float(item_row.get("rate", 0.0)) if pd.notna(item_row.get("rate")) else 0.0
                    
                    gst_pct_val = item_row.get("gst_pct")
                    gst_amt_raw = item_row.get("gst_amt")
                    
                    if gst_pct_val is None or (isinstance(gst_pct_val, float) and pd.isna(gst_pct_val)):
                        gst_pct_val = gst_amt_raw
                    if gst_amt_raw is None or (isinstance(gst_amt_raw, float) and pd.isna(gst_amt_raw)):
                        gst_amt_raw = gst_pct_val
                        
                    gst_pct = parse_gst_pct(gst_pct_val) if gst_pct_val is not None and pd.notna(gst_pct_val) else 0.0
                    if gst_pct < 1.0 and gst_pct > 0:
                        gst_pct = gst_pct * 100

                    # Pre-fill missing HSN / GST% from learned AI Product Catalog
                    if product_catalog and isinstance(product_catalog, dict):
                        cat_entry = product_catalog.get(item_name.lower())
                        if cat_entry:
                            if not hsn and cat_entry.get("hsn"):
                                hsn = str(cat_entry["hsn"])
                            if cat_entry.get("gst_pct") is not None and (gst_pct == 0.0 or gst_pct == 18.0):
                                gst_pct = float(cat_entry["gst_pct"])
                        
                    gst_amt = parse_gst_amt(gst_amt_raw) if gst_amt_raw is not None and pd.notna(gst_amt_raw) else 0.0
                    discount = parse_gst_amt(item_row.get("discount", 0.0)) if pd.notna(item_row.get("discount")) else 0.0
                    freight = parse_gst_amt(item_row.get("freight", 0.0)) if pd.notna(item_row.get("freight")) else 0.0
                    
                    taxable = 0.0
                    if "taxable_amt" in item_row and pd.notna(item_row["taxable_amt"]):
                        taxable = safe_float(item_row["taxable_amt"])
                    
                    calc_gross = round(qty * rate, 2) if (qty > 0 and rate > 0) else 0.0
                    
                    if taxable == 0.0 and calc_gross > 0:
                        taxable = round(calc_gross - discount, 2)
                    elif calc_gross > 0 and discount > taxable and taxable > 0 and abs((taxable + discount) - calc_gross) <= 1.0:
                        print(f"⚠️ Swapping inverted taxable ({taxable}) and discount ({discount}) for item '{item_name}'.")
                        taxable, discount = discount, taxable

                    item_total_amount = safe_float(item_row.get("total_amt", taxable + gst_amt)) if pd.notna(item_row.get("total_amt")) else (taxable + gst_amt)
                    if taxable == 0.0 and item_total_amount > 0:
                        taxable = round(item_total_amount - gst_amt, 2)
                        
                    gross_amt = calc_gross if calc_gross > 0 else (taxable + discount)
                    total_amt += item_total_amount
                    
                    uom = "UNT"
                    if "service" in item_name.lower():
                        uom = "OTH"
                        
                    is_igst = False
                    if party_gstin and not party_gstin.startswith(company_state_code):
                        is_igst = True
                        
                    if is_igst:
                        cgst, sgst, igst = 0.0, 0.0, gst_amt
                    else:
                        cgst, sgst, igst = round(gst_amt / 2, 4), round(gst_amt / 2, 4), 0.0
                        
                    items_list.append({
                        "name": item_name,
                        "hsn_code": hsn,
                        "uom": uom,
                        "qty": qty,
                        "rate": rate,
                        "gst_pct": gst_pct,
                        "taxable": taxable,
                        "amount": gross_amt,
                        "discount": discount,
                        "freight": freight
                    })
                    
                    taxable_sum += taxable
                    cgst_sum += cgst
                    sgst_sum += sgst
                    igst_sum += igst
                    discount_sum += discount
                    freight_sum += freight
                    
                if items_list:
                    extracted_data.append({
                        "date": date_str,
                        "bill_no": inv_no,
                        "party_name": party_name,
                        "party_gstin": party_gstin,
                        "party_address": "",
                        "party_city": "",
                        "party_pincode": "",
                        "taxable_amount": round(taxable_sum, 2),
                        "cgst": round(cgst_sum, 2),
                        "sgst": round(sgst_sum, 2),
                        "igst": round(igst_sum, 2),
                        "total": round(total_amt, 2) if total_amt > 0 else round(taxable_sum + cgst_sum + sgst_sum + igst_sum + freight_sum - discount_sum, 2),
                        "discount": round(discount_sum, 2),
                        "freight": round(freight_sum, 2),
                        "items": items_list
                    })
                    
            print(f"✅ Flat Excel parsing successful! Extracted {len(extracted_data)} vouchers.")
            return {
                "status": "success",
                "extracted_data": extracted_data
            }
            
        # --- HEADER-ONLY FLAT FILE FALLBACK ---
        if header_only_sheets_data:
            df_header = pd.concat([df for name, df in header_only_sheets_data], ignore_index=True)
            initial_header_count = len(df_header)
            
            subset_cols = [col for col in ["date", "bill_no", "party_name", "taxable_amt", "total_amt"] if col in df_header.columns]
            if subset_cols:
                df_header = df_header.drop_duplicates(subset=subset_cols)
            else:
                df_header = df_header.drop_duplicates()
                
            removed_count = initial_header_count - len(df_header)
            if removed_count > 0:
                print(f"🧹 Smart Deduplicator removed {removed_count} redundant header-only rows.")
                
            df_header = df_header[df_header["date"].notna()]
            df_header['Group_Key'] = df_header.apply(get_group_key, axis=1)
            print(f"Detected Header-Only Excel: {len(df_header)} invoice rows with no product column. Building synthetic items.")
            extracted_data = []
            for _, row in df_header.iterrows():
                group_key = row["Group_Key"]
                date_raw = row["date"]
                if isinstance(date_raw, datetime):
                    date_str = date_raw.strftime("%Y-%m-%d")
                else:
                    date_str = str(date_raw).strip()
                    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y", "%d-%m-%y", "%Y/%m/%d"):
                        try:
                            date_str = datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
                            break
                        except ValueError:
                            pass
                party_name = str(row["party_name"]).strip()
                party_gstin = str(row.get("party_gstin", "")).strip() if pd.notna(row.get("party_gstin")) else ""
                if party_gstin.lower() == "nan": party_gstin = ""

                inv_no = "" if str(group_key).startswith("NO_INV_") else str(group_key).rstrip(".0")

                total_raw = safe_float(row.get("total_amt", 0.0)) if pd.notna(row.get("total_amt")) else 0.0
                taxable_raw = safe_float(row.get("taxable_amt", 0.0)) if pd.notna(row.get("taxable_amt")) else 0.0
                gst_amt_raw = parse_gst_amt(row.get("gst_amt", 0.0)) if pd.notna(row.get("gst_amt")) else 0.0
                discount_raw = parse_gst_amt(row.get("discount", 0.0)) if pd.notna(row.get("discount")) else 0.0
                freight_raw = parse_gst_amt(row.get("freight", 0.0)) if pd.notna(row.get("freight")) else 0.0
                gst_pct_val = row.get("gst_pct")
                if gst_pct_val is None or (isinstance(gst_pct_val, float) and pd.isna(gst_pct_val)):
                    gst_pct_val = row.get("gst_amt", 0.0)
                gst_pct_raw = parse_gst_pct(gst_pct_val) if pd.notna(gst_pct_val) else 0.0
                if gst_pct_raw < 1.0 and gst_pct_raw > 0: gst_pct_raw = gst_pct_raw * 100
                hsn_raw = str(row.get("hsn", "")).strip() if pd.notna(row.get("hsn")) else ""
                if hsn_raw.lower() == "nan" or hsn_raw.endswith(".0"): hsn_raw = hsn_raw.rstrip(".0") if hsn_raw.endswith(".0") else ""

                if taxable_raw == 0.0 and total_raw > 0:
                    taxable_raw = round(total_raw - gst_amt_raw, 2)
                if total_raw == 0.0 and taxable_raw > 0:
                    total_raw = round(taxable_raw + gst_amt_raw, 2)

                is_igst = party_gstin and not party_gstin.startswith(company_state_code)
                if is_igst:
                    cgst, sgst, igst = 0.0, 0.0, gst_amt_raw
                else:
                    cgst, sgst, igst = round(gst_amt_raw / 2, 4), round(gst_amt_raw / 2, 4), 0.0

                synthetic_item = {
                    "name": "SALES",
                    "hsn_code": hsn_raw,
                    "uom": "OTH",
                    "qty": 1.0,
                    "rate": taxable_raw,
                    "gst_pct": gst_pct_raw,
                    "taxable": taxable_raw,
                    "amount": taxable_raw,
                    "discount": discount_raw,
                    "freight": freight_raw
                }

                extracted_data.append({
                    "date": date_str,
                    "bill_no": inv_no,
                    "party_name": party_name,
                    "party_gstin": party_gstin,
                    "party_address": "",
                    "party_city": "",
                    "party_pincode": "",
                    "taxable_amount": round(taxable_raw, 2),
                    "cgst": round(cgst, 2),
                    "sgst": round(sgst, 2),
                    "igst": round(igst, 2),
                    "total": round(total_raw, 2) if total_raw > 0 else round(taxable_raw + cgst + sgst + igst + freight_raw - discount_raw, 2),
                    "discount": round(discount_raw, 2),
                    "freight": round(freight_raw, 2),
                    "items": [synthetic_item]
                })

            print(f"✅ Header-Only Excel parsing successful! Extracted {len(extracted_data)} vouchers with synthetic items.")
            return {"status": "success", "extracted_data": extracted_data}
            
        # --- MULTI-SHEET FALLBACK (Normalized) ---
        report_sheet = None
        items_sheet = None
        for s in sheet_names:
            s_lower = str(s).lower().replace(" ", "").replace("_", "")
            if s_lower in ["salereport", "salesreport", "purchasereport"]:
                report_sheet = s
            elif s_lower in ["saleitems", "salesitems", "purchaseitems", "itemreport", "itemsreport"]:
                items_sheet = s
                
        if not report_sheet or not items_sheet:
            report_sheet = "Sale Report" if "Sale Report" in sheet_names else ("Purchase Report" if "Purchase Report" in sheet_names else sheet_names[0])
            items_sheet = "Sale Items" if "Sale Items" in sheet_names else ("Purchase Items" if "Purchase Items" in sheet_names else (sheet_names[1] if len(sheet_names) > 1 else sheet_names[0]))
            
        print(f"Reading Report Sheet: '{report_sheet}' and Items Sheet: '{items_sheet}'")
        
        if report_sheet == items_sheet:
            print(f"⚠️ Report and Items sheet are the same ('{report_sheet}'). Treating as header-only.")
            df_report_raw = pd.read_excel(file_path, sheet_name=report_sheet)
            df_report, report_res = normalize_sheet_columns(df_report_raw)
            df_report = df_report[df_report["date"].notna()]
            df_report['Group_Key'] = df_report.apply(
                lambda row: str(row['bill_no']).strip() if pd.notna(row.get('bill_no')) and str(row.get('bill_no')).strip() != "nan" else f"NO_INV_{row.get('date')}_{row.get('party_name')}",
                axis=1
            )
            extracted_data = []
            for _, row in df_report.iterrows():
                date_raw = row.get("date")
                if isinstance(date_raw, datetime):
                    date_str = date_raw.strftime("%Y-%m-%d")
                else:
                    date_str = str(date_raw).strip()
                    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y", "%d-%m-%y", "%Y/%m/%d"):
                        try: date_str = datetime.strptime(date_str, fmt).strftime("%Y-%m-%d"); break
                        except ValueError: pass
                party_name = str(row.get("party_name", "")).strip()
                party_gstin = str(row.get("party_gstin", "")).strip() if pd.notna(row.get("party_gstin")) else ""
                if party_gstin.lower() == "nan": party_gstin = ""
                inv_no = "" if str(row["Group_Key"]).startswith("NO_INV_") else str(row["Group_Key"]).rstrip(".0")
                total_raw = safe_float(row.get("total_amt", 0.0)) if pd.notna(row.get("total_amt")) else 0.0
                taxable_raw = safe_float(row.get("taxable_amt", 0.0)) if pd.notna(row.get("taxable_amt")) else 0.0
                gst_amt_raw = parse_gst_amt(row.get("gst_amt", 0.0)) if pd.notna(row.get("gst_amt")) else 0.0
                discount_raw = parse_gst_amt(row.get("discount", 0.0)) if pd.notna(row.get("discount")) else 0.0
                gst_pct_val = row.get("gst_pct")
                if gst_pct_val is None or (isinstance(gst_pct_val, float) and pd.isna(gst_pct_val)):
                    gst_pct_val = row.get("gst_amt", 0.0)
                gst_pct_raw = parse_gst_pct(gst_pct_val) if pd.notna(gst_pct_val) else 0.0
                if gst_pct_raw < 1.0 and gst_pct_raw > 0: gst_pct_raw = gst_pct_raw * 100
                if taxable_raw == 0.0 and total_raw > 0: taxable_raw = round(total_raw - gst_amt_raw, 2)
                if total_raw == 0.0 and taxable_raw > 0: total_raw = round(taxable_raw + gst_amt_raw, 2)
                is_igst = party_gstin and not party_gstin.startswith(company_state_code)
                cgst = sgst = igst = 0.0
                if is_igst: igst = gst_amt_raw
                else: cgst = sgst = round(gst_amt_raw / 2, 4)
                extracted_data.append({
                    "date": date_str, "bill_no": inv_no, "party_name": party_name, "party_gstin": party_gstin,
                    "party_address": "", "party_city": "", "party_pincode": "",
                    "taxable_amount": round(taxable_raw, 2), "cgst": round(cgst, 2), "sgst": round(sgst, 2),
                    "igst": round(igst, 2), "total": round(total_raw, 2), "discount": round(discount_raw, 2),
                    "items": [{"name": "SALES", "hsn_code": "", "uom": "OTH", "qty": 1.0,
                               "rate": taxable_raw, "gst_pct": gst_pct_raw, "taxable": taxable_raw,
                               "amount": taxable_raw, "discount": discount_raw}]
                })
            print(f"✅ Single-sheet header-only fallback: {len(extracted_data)} vouchers.")
            return {"status": "success", "extracted_data": extracted_data}
        
        df_report_raw = pd.read_excel(file_path, sheet_name=report_sheet)
        df_items_raw = pd.read_excel(file_path, sheet_name=items_sheet)
        
        df_report_raw = find_and_clean_header(df_report_raw)
        df_items_raw = find_and_clean_header(df_items_raw)
        
        df_report, report_res = normalize_sheet_columns(df_report_raw)
        df_items, items_res = normalize_sheet_columns(df_items_raw)
        
        df_report['Group_Key'] = df_report.apply(
            lambda row: str(row['bill_no']).strip() if pd.notna(row.get('bill_no')) and str(row.get('bill_no')).strip() != "nan" else f"NO_INV_{row.get('date')}_{row.get('party_name')}",
            axis=1
        )
        df_report = df_report[df_report["date"].notna()]
        
        if "date" in df_items.columns and "party_name" in df_items.columns:
            df_items['date'] = df_items['date'].ffill()
            df_items['party_name'] = df_items['party_name'].ffill()
        
        df_items['Group_Key'] = df_items.apply(
            lambda row: str(row.get('bill_no', '')).strip() if pd.notna(row.get('bill_no')) and str(row.get('bill_no')).strip() != "nan" else f"NO_INV_{row.get('date', '')}_{row.get('party_name', '')}",
            axis=1
        )
        
        extracted_data = []
        for _, row in df_report.iterrows():
            group_key = row["Group_Key"]
            date_raw = row["date"]
            
            if isinstance(date_raw, datetime):
                date_str = date_raw.strftime("%Y-%m-%d")
            else:
                date_str = str(date_raw).strip()
                for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d-%m-%Y", "%d-%m-%y", "%Y/%m/%d"):
                    try:
                        date_dt = datetime.strptime(date_str, fmt)
                        date_str = date_dt.strftime("%Y-%m-%d")
                        break
                    except ValueError:
                        pass
                        
            party_name = str(row["party_name"]).strip()
            party_gstin = str(row.get("party_gstin", "")).strip() if pd.notna(row.get("party_gstin")) else ""
            if party_gstin.lower() == "nan": party_gstin = ""
                
            total_amt = safe_float(row.get("total_amt", 0.0)) if pd.notna(row.get("total_amt")) else 0.0
            
            inv_no = ""
            if not str(group_key).startswith("NO_INV_"):
                inv_no = str(group_key)
                if inv_no.endswith(".0"): inv_no = inv_no[:-2]
                
            inv_items = df_items[df_items["Group_Key"] == group_key]
            items_list = []
            taxable_sum = 0.0
            cgst_sum = 0.0
            sgst_sum = 0.0
            igst_sum = 0.0
            discount_sum = 0.0
            freight_sum = 0.0
            
            for _, item_row in inv_items.iterrows():
                item_name = str(item_row.get("item_name", "")).strip()
                if not item_name or item_name.lower() == "nan":
                    continue
                
                item_norm = item_name.lower().replace(" ", "").replace(".", "").replace("_", "")
                if item_norm in INVALID_ITEM_WORDS:
                    print(f"⚠️ Skipping invalid item name (transaction type): '{item_name}'")
                    continue
                    
                hsn = str(item_row.get("hsn", "")).strip() if pd.notna(item_row.get("hsn")) else ""
                if hsn.endswith(".0"): hsn = hsn[:-2]
                if hsn.lower() == "nan": hsn = ""

                qty = safe_float(item_row.get("qty", 1.0)) if pd.notna(item_row.get("qty")) else 1.0
                rate = safe_float(item_row.get("rate", 0.0)) if pd.notna(item_row.get("rate")) else 0.0
                
                gst_pct_val = item_row.get("gst_pct")
                gst_amt_raw = item_row.get("gst_amt")
                
                if gst_pct_val is None or (isinstance(gst_pct_val, float) and pd.isna(gst_pct_val)):
                    gst_pct_val = gst_amt_raw
                if gst_amt_raw is None or (isinstance(gst_amt_raw, float) and pd.isna(gst_amt_raw)):
                    gst_amt_raw = gst_pct_val
                    
                gst_pct = parse_gst_pct(gst_pct_val) if gst_pct_val is not None and pd.notna(gst_pct_val) else 0.0
                if gst_pct < 1.0 and gst_pct > 0: gst_pct = gst_pct * 100
                gst_amt = parse_gst_amt(gst_amt_raw) if gst_amt_raw is not None and pd.notna(gst_amt_raw) else 0.0
                discount = parse_gst_amt(item_row.get("discount", 0.0)) if pd.notna(item_row.get("discount")) else 0.0
                freight = parse_gst_amt(item_row.get("freight", 0.0)) if pd.notna(item_row.get("freight")) else 0.0
                
                taxable = 0.0
                if "taxable_amt" in item_row and pd.notna(item_row["taxable_amt"]):
                    taxable = safe_float(item_row["taxable_amt"])
                
                calc_gross = round(qty * rate, 2) if (qty > 0 and rate > 0) else 0.0
                
                if taxable == 0.0 and calc_gross > 0:
                    taxable = round(calc_gross - discount, 2)
                elif calc_gross > 0 and discount > taxable and taxable > 0 and abs((taxable + discount) - calc_gross) <= 1.0:
                    print(f"⚠️ Swapping inverted taxable ({taxable}) and discount ({discount}) for item '{item_name}'.")
                    taxable, discount = discount, taxable

                item_total_amount = safe_float(item_row.get("total_amt", taxable + gst_amt)) if pd.notna(item_row.get("total_amt")) else (taxable + gst_amt)
                if taxable == 0.0 and item_total_amount > 0:
                    taxable = round(item_total_amount - gst_amt, 2)
                    
                gross_amt = calc_gross if calc_gross > 0 else (taxable + discount)
                
                uom = str(item_row.get("uom", "")).strip() if pd.notna(item_row.get("uom")) else ""
                if not uom or uom.lower() == "nan":
                    uom = "OTH" if "service" in item_name.lower() else "UNT"
                    
                is_igst = False
                if party_gstin and not party_gstin.startswith(company_state_code):
                    is_igst = True
                    
                if is_igst:
                    cgst, sgst, igst = 0.0, 0.0, gst_amt
                else:
                    cgst, sgst, igst = round(gst_amt / 2, 4), round(gst_amt / 2, 4), 0.0
                    
                items_list.append({
                    "name": item_name,
                    "hsn_code": hsn,
                    "uom": uom,
                    "qty": qty,
                    "rate": rate,
                    "gst_pct": gst_pct,
                    "taxable": taxable,
                    "amount": gross_amt,
                    "discount": discount,
                    "freight": freight
                })
                
                taxable_sum += taxable
                cgst_sum += cgst
                sgst_sum += sgst
                igst_sum += igst
                discount_sum += discount
                freight_sum += freight
                
            if items_list:
                extracted_data.append({
                    "date": date_str,
                    "bill_no": inv_no,
                    "party_name": party_name,
                    "party_gstin": party_gstin,
                    "party_address": "",
                    "party_city": "",
                    "party_pincode": "",
                    "taxable_amount": round(taxable_sum, 2),
                    "cgst": round(cgst_sum, 2),
                    "sgst": round(sgst_sum, 2),
                    "igst": round(igst_sum, 2),
                    "total": round(total_amt, 2) if total_amt > 0 else round(taxable_sum + cgst_sum + sgst_sum + igst_sum + freight_sum - discount_sum, 2),
                    "discount": round(discount_sum, 2),
                    "freight": round(freight_sum, 2),
                    "items": items_list
                })
                
        print(f"✅ Multi-sheet Excel parsing successful! Extracted {len(extracted_data)} vouchers.")
        return {
            "status": "success",
            "extracted_data": extracted_data
        }
        
    except Exception as e:
        print(f"❌ Excel parsing failed: {e}")
        raise ValueError(f"Excel parsing failed: {e}")
