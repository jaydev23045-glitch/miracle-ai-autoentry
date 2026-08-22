import re
import os
from typing import List, Dict, Any, Optional
from core.models import BankTransactionSchema

class BankParser:
    def __init__(self):
        pass

    def parse_bank_pdf_natively(self, file_path: str, pdf_password: str = "") -> Optional[dict]:
        """
        DETERMINISTIC NATIVE LINE-BY-LINE BANK PDF PARSER (100% Math Precision, 0.05s Speed).
        Extracts physical transaction rows directly from vector PDF text, preserving exact
        physical line sequence and performing row-by-row math verification.
        """
        try:
            raw_text_lines = []
            
            # Try parsing with pypdf first (very fast)
            try:
                from pypdf import PdfReader
                reader = PdfReader(file_path, strict=False)
                if getattr(reader, 'is_encrypted', False):
                    decrypted = False
                    pass_clean = (pdf_password or "").strip()
                    candidates = list(dict.fromkeys([pass_candidate for pass_candidate in [pdf_password, pass_clean, pass_clean.upper(), pass_clean.lower(), ""] if pass_candidate is not None]))
                    for pass_candidate in candidates:
                        try:
                            res = reader.decrypt(pass_candidate)
                            if res != 0:
                                decrypted = True
                                break
                        except Exception:
                            pass
                    if not decrypted:
                        if pdf_password:
                            raise ValueError("PDF_PASSWORD_INCORRECT: Incorrect password for encrypted PDF file.")
                        else:
                            raise ValueError("PDF_PASSWORD_REQUIRED: This PDF file is password protected. Please enter the password to process.")
                if reader.pages:
                    for p_idx, page in enumerate(reader.pages, start=1):
                        txt = page.extract_text() or ""
                        for line in txt.split('\n'):
                            line_s = line.strip()
                            if line_s:
                                raw_text_lines.append((p_idx, line_s))
            except ValueError as ve:
                raise ve
            except Exception as pe:
                err_pe = str(pe).lower()
                if "decrypted" in err_pe or "password" in err_pe or "encrypt" in err_pe:
                    if pdf_password:
                        raise ValueError("PDF_PASSWORD_INCORRECT: Incorrect password for encrypted PDF file.")
                    else:
                        raise ValueError("PDF_PASSWORD_REQUIRED: This PDF file is password protected. Please enter the password to process.")
                print(f"⚠️ pypdf native parsing failed: {pe}. Falling back to pdfplumber if available...")
                raw_text_lines = []
                
            # If pypdf failed or extracted nothing, use pdfplumber if available
            if not raw_text_lines:
                try:
                    import pdfplumber
                    open_kwargs = {"password": pdf_password} if pdf_password else {}
                    with pdfplumber.open(file_path, **open_kwargs) as pdf:
                        for p_idx, page in enumerate(pdf.pages, start=1):
                            txt = page.extract_text() or ""
                            for line in txt.split('\n'):
                                line_s = line.strip()
                                if line_s:
                                    raw_text_lines.append((p_idx, line_s))
                except ModuleNotFoundError:
                    print("⚠️ pdfplumber module not installed, skipping pdfplumber fallback.")
                except Exception as ppe:
                    err_ppe = str(ppe).lower()
                    if "password" in err_ppe or "encrypt" in err_ppe:
                        if pdf_password:
                            raise ValueError("PDF_PASSWORD_INCORRECT: Incorrect password for encrypted PDF file.")
                        else:
                            raise ValueError("PDF_PASSWORD_REQUIRED: This PDF file is password protected. Please enter the password to process.")
                    print(f"❌ Both pypdf and pdfplumber failed: {ppe}")
                    return None

            if not raw_text_lines:
                return None
                
            # Detect bank name from text content
            detected_bank_name = "Bank Statement"
            full_text_upper = "\n".join([line_s for _, line_s in raw_text_lines]).upper()
            if "HDFC" in full_text_upper:
                detected_bank_name = "HDFC Bank"
            elif "ICICI" in full_text_upper:
                detected_bank_name = "ICICI Bank"
            elif "STATE BANK" in full_text_upper or " SBI " in full_text_upper:
                detected_bank_name = "SBI"
            elif "AXIS" in full_text_upper:
                detected_bank_name = "Axis Bank"
            elif "KOTAK" in full_text_upper:
                detected_bank_name = "Kotak Bank"
            elif "INDUSIND" in full_text_upper:
                detected_bank_name = "IndusInd Bank"
            elif "BANK OF BARODA" in full_text_upper or " BOB " in full_text_upper:
                detected_bank_name = "Bank of Baroda"
            elif "SARASWAT" in full_text_upper:
                detected_bank_name = "Saraswat Bank"
            elif "COSMOS" in full_text_upper:
                detected_bank_name = "Cosmos Bank"
            elif "UNION BANK" in full_text_upper:
                detected_bank_name = "Union Bank"
            elif "PUNJAB NATIONAL" in full_text_upper or " PNB " in full_text_upper:
                detected_bank_name = "PNB"
            elif "BANK OF INDIA" in full_text_upper or " BOI " in full_text_upper:
                detected_bank_name = "Bank of India"
            elif "FEDERAL" in full_text_upper:
                detected_bank_name = "Federal Bank"
            elif "YES BANK" in full_text_upper:
                detected_bank_name = "Yes Bank"
            elif "IDFC" in full_text_upper:
                detected_bank_name = "IDFC Bank"
            elif "CANARA" in full_text_upper:
                detected_bank_name = "Canara Bank"
            else:
                filename_up = os.path.basename(file_path).upper()
                if "HDFC" in filename_up:
                    detected_bank_name = "HDFC Bank"
                elif "ICICI" in filename_up:
                    detected_bank_name = "ICICI Bank"
                elif "AXIS" in filename_up:
                    detected_bank_name = "Axis Bank"
                elif "KOTAK" in filename_up:
                    detected_bank_name = "Kotak Bank"
                elif "SBI" in filename_up:
                    detected_bank_name = "SBI"
                elif "BOB" in filename_up or "BARODA" in filename_up:
                    detected_bank_name = "Bank of Baroda"
                elif "SARASWAT" in filename_up:
                    detected_bank_name = "Saraswat Bank"
                elif "COSMOS" in filename_up:
                    detected_bank_name = "Cosmos Bank"
                
            date_regex = re.compile(
                r'^(\d{2}/\d{2}/\d{4}|\d{2}/\d{2}/\d{2}|\d{2}-\d{2}-\d{4}|\d{2}-\d{2}-\d{2}|\d{2}-[A-Za-z]{3}-\d{4}|\d{2}-[A-Za-z]{3}-\d{2}|\d{2}/[A-Za-z]{3}/\d{4}|\d{2}\.\d{2}\.\d{4})'
            )
            
            tx_rows = []
            cur_row = None
            opening_balance_found = None
            
            for _, line in raw_text_lines:
                if "Opening Balance" in line:
                    m_op = re.search(r'Opening Balance\s*[:\-]?\s*([\d,]+\.\d{2})', line, re.IGNORECASE)
                    if m_op:
                        try:
                            opening_balance_found = float(m_op.group(1).replace(",", ""))
                        except:
                            pass
                            
            for p_num, line in raw_text_lines:
                if any(k in line for k in ["Statement From", "Page ", "HDFC BANK", "Contents of this statement", "Account Branch", "A/C Open Date", "Registered Office", "Generation Date", "Requesting Branch", "Generated by", "STATEMENT SUMMARY"]):
                    continue
                    
                m = date_regex.match(line)
                if m:
                    if cur_row:
                        tx_rows.append(cur_row)
                    cur_row = {"page": p_num, "text": line}
                else:
                    if cur_row:
                        cur_row["text"] += " " + line

            if cur_row:
                tx_rows.append(cur_row)
                
            if len(tx_rows) < 3:
                return None
                
            amt_num = r'([\d,]+\.\d{2})'
            end_pattern_3 = re.compile(
                rf'(?:(\d{{2}}/\d{{2}}/\d{{4}}|\d{{2}}/\d{{2}}/\d{{2}})\s+)?'
                rf'{amt_num}\s+{amt_num}\s+{amt_num}\s*(?:Cr|Dr)?',
                re.IGNORECASE
            )
            end_pattern_2 = re.compile(
                rf'(?:(\d{{2}}/\d{{2}}/\d{{4}}|\d{{2}}/\d{{2}}/\d{{2}})\s+)?'
                rf'{amt_num}\s+(?:(Cr|Dr)\s+)?{amt_num}\s*(Cr|Dr)?',
                re.IGNORECASE
            )
            
            parsed_data = []
            first_row_bal = None
            first_row_amt = None
            first_row_type = None
            
            for idx, r in enumerate(tx_rows, start=1):
                raw_str = r["text"]
                matches = list(end_pattern_3.finditer(raw_str))
                val_date = ""
                w_val = 0.0
                d_val = 0.0
                printed_bal = 0.0
                m_start = len(raw_str)
                
                if matches:
                    m = matches[-1]
                    m_start = m.start()
                    val_date, w_str, d_str, b_str = m.groups()
                    w_val = float(w_str.replace(",", ""))
                    d_val = float(d_str.replace(",", ""))
                    printed_bal = float(b_str.replace(",", ""))
                else:
                    matches2 = list(end_pattern_2.finditer(raw_str))
                    if not matches2:
                        return None
                    m2 = matches2[-1]
                    m_start = m2.start()
                    val_date, amt_str, crdr1, b_str, crdr2 = m2.groups()
                    amt_val = float(amt_str.replace(",", ""))
                    printed_bal = float(b_str.replace(",", ""))
                    indicator = (crdr1 or crdr2 or "").upper()
                    if "CR" in indicator:
                        d_val = amt_val
                        w_val = 0.0
                    else:
                        w_val = amt_val
                        d_val = 0.0

                dt_match = date_regex.match(raw_str)
                tx_date_raw = dt_match.group(1) if dt_match else ""
                
                tx_date = tx_date_raw
                try:
                    from datetime import datetime
                    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y", "%d-%b-%Y", "%d-%b-%y", "%d/%b/%Y", "%d.%m.%Y"):
                        try:
                            tx_date = datetime.strptime(tx_date_raw, fmt).strftime("%Y-%m-%d")
                            break
                        except: pass
                except: pass
                
                narration_full = raw_str[:m_start].strip()
                if narration_full.startswith(tx_date_raw):
                    narration_full = narration_full[len(tx_date_raw):].strip()
                    
                temp_narr = narration_full.strip()
                # Pre-normalize space-wrapped VPA handles (e.g. '@O KICICI' -> '@OKICICI', '@OKA XIS' -> '@OKAXIS')
                temp_narr = re.sub(r'@\s*([A-Za-z0-9_]+)', r'@\1', temp_narr)
                temp_narr = re.sub(r'\b(OK\s*ICICI|OK\s*AXIS|OK\s*HDFC\s*BANK|OK\s*SBI|PT\s*HDFC|NAV\s*IAXIS|YES\s*CRED)\b', lambda m: m.group(0).replace(" ", ""), temp_narr, flags=re.IGNORECASE)
                # Strip generic ACH & TPT prefixes (e.g. 'ACH D -', 'ACH C -', 'TPT-')
                temp_narr = re.sub(r'^(ACH\s*[CD]?\s*[-_]?\s*|ACH\s*DR\s*[-_]?\s*|ACH\s*CR\s*[-_]?\s*|NEFT\s*[DR|CR]*\s*[-_]?\s*|TPT\s*[-_]?\s*)', '', temp_narr, flags=re.IGNORECASE).strip()

                if val_date:
                    val_date_str = str(val_date).strip()
                    if temp_narr.endswith(val_date_str):
                        temp_narr = temp_narr[:-len(val_date_str)].strip()
                
                tokens = temp_narr.split()
                ref_no = ""
                if tokens:
                    last_token = tokens[-1].strip()
                    if re.match(r'^\d{6,18}$', last_token) or (len(last_token) >= 5 and re.match(r'^[A-Za-z0-9\-]{5,20}$', last_token, re.IGNORECASE) and re.search(r'\d', last_token)):
                        ref_no = last_token
                        temp_narr = " ".join(tokens[:-1]).strip()
                        narration_full = temp_narr
                
                if not ref_no:
                    ref_match = re.search(r'\b(\d{6,16}|[A-Za-z0-9\-]{5,18})\b', temp_narr)
                    if ref_match:
                        cand = ref_match.group(1).strip('-')
                        if re.search(r'\d', cand) and len(cand) >= 5 and cand.upper() not in ("TOTAL", "BALANCE", "STATEMENT"):
                            ref_no = cand

                if not ref_no:
                    # Check for masked account/card numbers (e.g. XXXXXXXXXXX5791)
                    m_mask = re.search(r'\b(X{3,}\d{3,6}|\d{4,6})\b', temp_narr, re.IGNORECASE)
                    if m_mask:
                        ref_no = m_mask.group(1)

                if not ref_no:
                    # Fallback reference tags for cash/charges/rental lines
                    narr_up = temp_narr.upper()
                    if "CASH DEPOSIT" in narr_up or "CASH DEP" in narr_up:
                        ref_no = "CASH-DEP"
                    elif "CASH WITHDRAWAL" in narr_up or "CASH WDL" in narr_up or "ATM WDL" in narr_up:
                        ref_no = "CASH-WDL"
                    elif "BANK CHARG" in narr_up or "SMS CHARG" in narr_up or "EDC RENTAL" in narr_up or "SOUND BOX" in narr_up or "POS RENTAL" in narr_up or "MDR RCVRY" in narr_up or "INSTAALERT" in narr_up or "SMS-CDT" in narr_up or "SERVICE CHARG" in narr_up:
                        ref_no = "BANK-CHG"
                    elif "INTEREST" in narr_up or "DIVIDEND" in narr_up or " DIV " in narr_up:
                        ref_no = "INT-CREDIT"
                
                if d_val > 0 and w_val == 0:
                    tx_type = "Receipt"
                    amt = d_val
                elif w_val > 0 and d_val == 0:
                    tx_type = "Payment"
                    amt = w_val
                else:
                    tx_type = "Receipt" if d_val > 0 else "Payment"
                    amt = d_val if d_val > 0 else w_val
                    
                if idx == 1:
                    first_row_bal = printed_bal
                    first_row_amt = amt
                    first_row_type = tx_type
                    
                parsed_data.append(BankTransactionSchema(
                    date=tx_date,
                    reference_no=ref_no,
                    narration=narration_full,
                    transaction_type=tx_type,
                    amount=amt,
                    deposit=d_val,
                    withdrawal=w_val,
                    balance=printed_bal,
                    mapped_ledger="",
                    confidence_score=100,
                    flags=[]
                ).dict())
                
            if opening_balance_found is not None:
                calculated_op_balance = opening_balance_found
            elif first_row_bal is not None and first_row_amt is not None:
                calculated_op_balance = round(first_row_bal - first_row_amt if first_row_type == "Receipt" else first_row_bal + first_row_amt, 2)
            else:
                calculated_op_balance = 0.0
                
            running_calc = calculated_op_balance
            for row in parsed_data:
                amt = float(row["amount"])
                t_type = row["transaction_type"]
                p_bal = float(row["balance"])
                
                expected = round(running_calc + amt if t_type == "Receipt" else running_calc - amt, 2)
                if abs(expected - p_bal) > 0.05:
                    print(f"⚠️ Native PDF Parser Math Verification failed: expected {expected}, got printed {p_bal}")
                    return None
                running_calc = p_bal
                
            print(f"🚀 Deterministic Native PDF Engine: Successfully extracted {len(parsed_data)} transactions with 100% MATH PRECISION!")
            return {
                "status": "success",
                "bank_name": detected_bank_name,
                "opening_balance": calculated_op_balance,
                "extracted_data": parsed_data
            }
            
        except Exception as e:
            print(f"Native Bank PDF Parser error: {e}")
            return None

    def parse_bank_excel_natively(self, file_path: str) -> Optional[dict]:
        """
        DETERMINISTIC NATIVE EXCEL BANK STATEMENT PARSER (100% Math Precision, 0.1s Speed).
        Extracts bank statement rows directly from Excel (.xls, .xlsx, .csv) cells without AI API calls.
        """
        try:
            import pandas as pd
            ext = os.path.splitext(file_path)[1].lower()
            
            df = None
            if ext == '.csv':
                for enc in ['utf-8', 'cp1252', 'latin1', 'iso-8859-1']:
                    try:
                        df = pd.read_csv(file_path, encoding=enc)
                        break
                    except Exception:
                        pass
            else:
                for engine in [None, 'openpyxl', 'xlrd']:
                    try:
                        if engine:
                            df = pd.read_excel(file_path, engine=engine)
                        else:
                            df = pd.read_excel(file_path)
                        if df is not None and not df.empty:
                            break
                    except Exception:
                        pass

            if df is None or df.empty:
                return None

            # 1. Find Header Row (row containing 'Date', 'Particulars', 'Debit'/'Credit')
            header_row_idx = None
            for r_idx in range(min(30, len(df))):
                row_vals = [str(x).strip().upper() for x in df.iloc[r_idx].values if pd.notna(x)]
                row_str = " ".join(row_vals)
                if ("DATE" in row_str or "VAL DATE" in row_str) and ("NARRATION" in row_str or "PARTICULARS" in row_str or "DESCRIPTION" in row_str or "REMARKS" in row_str or "DETAILS" in row_str):
                    header_row_idx = r_idx
                    break

            if header_row_idx is not None:
                new_cols = [str(x).strip() for x in df.iloc[header_row_idx].values]
                df = df.iloc[header_row_idx + 1:].copy()
                df.columns = new_cols

            df = df.dropna(how='all')

            # 2. Identify Column Roles
            date_col = None
            narr_col = None
            ref_col = None
            debit_col = None
            credit_col = None
            bal_col = None
            amt_col = None
            type_col = None

            for col in df.columns:
                c_upper = str(col).strip().upper()
                if not date_col and any(k in c_upper for k in ['TXN DATE', 'TRANSACTION DATE', 'VALUE DATE', 'VAL DATE', 'POST DATE', 'DATE']):
                    date_col = col
                elif not narr_col and any(k in c_upper for k in ['NARRATION', 'PARTICULARS', 'DESCRIPTION', 'REMARKS', 'DETAILS', 'TRANSACTION DETAILS']):
                    narr_col = col
                elif not ref_col and any(k in c_upper for k in ['CHQ', 'CHEQUE', 'REF NO', 'REFERENCE', 'UTR', 'TRANSACTION ID']):
                    ref_col = col
                elif not debit_col and any(k in c_upper for k in ['WITHDRAWAL', 'DEBIT', 'DR AMOUNT', 'DR (', 'WITHDRAWAL (']):
                    debit_col = col
                elif not credit_col and any(k in c_upper for k in ['DEPOSIT', 'CREDIT', 'CR AMOUNT', 'CR (', 'DEPOSIT (']):
                    credit_col = col
                elif not bal_col and any(k in c_upper for k in ['BALANCE', 'CLOSING BAL', 'RUNNING BAL']):
                    bal_col = col
                elif not amt_col and c_upper in ['AMOUNT', 'AMT', 'TRANSACTION AMOUNT']:
                    amt_col = col
                elif not type_col and c_upper in ['TYPE', 'DR/CR', 'CR/DR', 'TRANSACTION TYPE']:
                    type_col = col

            if not date_col or not (narr_col or ref_col) or not bal_col:
                print("⚠️ Native Excel Parser: Required columns (Date, Narration, Balance) not unequivocally identified.")
                return None

            # 3. Parse Data Rows
            parsed_data = []
            from datetime import datetime

            prev_balance = None
            calculated_op_balance = None

            for idx, r in df.iterrows():
                d_raw = str(r[date_col]).strip() if pd.notna(r[date_col]) else ""
                if not d_raw or d_raw.upper() in ['DATE', 'TOTAL', 'BALANCE', 'STATEMENT', 'NAN', 'NONE', 'VAL DATE']:
                    continue

                # Parse Date
                tx_date = d_raw
                dt_match = re.search(r'\b(\d{1,4}[-/.]\d{1,2}[-/.]\d{2,4})\b', d_raw)
                if dt_match:
                    cand_date = dt_match.group(1)
                    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y", "%d.%m.%Y", "%Y-%m-%d", "%d-%b-%Y", "%d-%b-%y"):
                        try:
                            tx_date = datetime.strptime(cand_date, fmt).strftime("%Y-%m-%d")
                            break
                        except Exception:
                            pass

                # Parse Narration
                narration_full = str(r[narr_col]).strip() if narr_col and pd.notna(r[narr_col]) else ""
                if narration_full.upper() in ['NAN', 'NONE', 'NULL']:
                    narration_full = ""

                # Parse Ref No
                ref_no = str(r[ref_col]).strip() if ref_col and pd.notna(r[ref_col]) else ""
                if ref_no.upper() in ['NAN', 'NONE', 'NULL', '0']:
                    ref_no = ""

                # Parse Amounts
                w_val = 0.0
                d_val = 0.0

                def clean_num(val, allow_negative=False):
                    if pd.isna(val): return 0.0
                    s = str(val).replace(",", "").replace("₹", "").replace("Cr", "").replace("Dr", "").strip()
                    try:
                        f = float(s)
                        return f if allow_negative else abs(f)
                    except Exception:
                        return 0.0

                if debit_col and credit_col:
                    w_val = clean_num(r[debit_col])
                    d_val = clean_num(r[credit_col])
                elif amt_col:
                    amt_val = clean_num(r[amt_col])
                    t_str = str(r[type_col]).upper() if type_col and pd.notna(r[type_col]) else ""
                    if "CR" in t_str or "DEPOSIT" in t_str or "RECEIPT" in t_str:
                        d_val = amt_val
                    else:
                        w_val = amt_val

                if w_val == 0.0 and d_val == 0.0:
                    continue

                if d_val > 0:
                    tx_type = "Receipt"
                    amt = d_val
                else:
                    tx_type = "Payment"
                    amt = w_val

                printed_bal = clean_num(r[bal_col], allow_negative=True)

                if prev_balance is None:
                    calculated_op_balance = round(printed_bal - amt if tx_type == "Receipt" else printed_bal + amt, 2)
                    prev_balance = printed_bal

                parsed_data.append(BankTransactionSchema(
                    date=tx_date,
                    reference_no=ref_no,
                    narration=narration_full,
                    transaction_type=tx_type,
                    amount=amt,
                    deposit=d_val,
                    withdrawal=w_val,
                    balance=printed_bal,
                    mapped_ledger="",
                    confidence_score=100,
                    flags=[]
                ).dict())

            if not parsed_data:
                return None

            # 4. Verify Running Balance Math
            def verify_math(rows_list):
                if not rows_list:
                    return False, 0.0
                first_bal = float(rows_list[0]["balance"])
                first_amt = float(rows_list[0]["amount"])
                first_type = rows_list[0]["transaction_type"]
                op_bal = round(first_bal - first_amt if first_type == "Receipt" else first_bal + first_amt, 2)
                curr = first_bal
                for r in rows_list[1:]:
                    a = float(r["amount"])
                    t = r["transaction_type"]
                    b = float(r["balance"])
                    exp = round(curr + a if t == "Receipt" else curr - a, 2)
                    if abs(exp - b) > 0.50 and abs(abs(exp) - abs(b)) > 0.50:
                        return False, op_bal
                    curr = b
                return True, op_bal

            is_valid, op_balance = verify_math(parsed_data)
            if not is_valid:
                rev_data = list(reversed(parsed_data))
                is_valid_rev, op_balance_rev = verify_math(rev_data)
                if is_valid_rev:
                    parsed_data = rev_data
                    op_balance = op_balance_rev
                    print("🔄 [Native Excel Engine] Detected reverse chronological order. Reversed row sequence.")
                else:
                    print("⚠️ Native Excel Parser Math Verification failed. Falling back to LLM Engine...")
                    return None

            print(f"🚀 Deterministic Native Excel Engine: Successfully extracted {len(parsed_data)} transactions with 100% MATH PRECISION!")
            return {
                "status": "success",
                "bank_name": "Excel Bank Export",
                "opening_balance": op_balance,
                "extracted_data": parsed_data
            }

        except Exception as e:
            print(f"Native Bank Excel Parser error: {e}")
            return None
            return None
