import pdfplumber
import re
from datetime import datetime as _ddt

pdf_path = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/Test_Samples_And_Archives/DEMO SALES/Aksharbrahm/259876778999_1785754792241.pdf"

def extract_dates(text):
    dates = []
    # Try to find standard dates like "1 July 2026", "31 July 2026"
    standard_matches = re.findall(r'\b\d{1,2}\s+[A-Za-z]+\s+\d{4}\b', text)
    for m in standard_matches:
        try:
            dt = _ddt.strptime(m, "%d %B %Y")
            dates.append(dt)
        except ValueError:
            try:
                dt = _ddt.strptime(m, "%d %b %Y")
                dates.append(dt)
            except ValueError:
                pass
                
    # Also find split dates like "2026-\n07-31" by replacing newline or joining
    # Let's clean the text by replacing newline followed by date components
    cleaned = text
    # Match "2026-\n07-31" and merge to "2026-07-31"
    cleaned = re.sub(r'(\d{4}-)\s*\n\s*(\d{2}-\d{2})', r'\1\2', cleaned)
    # Match "07-31\n2026-" and merge
    cleaned = re.sub(r'(\d{2}-\d{2})\s*\n\s*(\d{4}-)', r'\2\1', cleaned)
    
    # Now look for YYYY-MM-DD
    matches = re.findall(r'\b\d{4}-\d{2}-\d{2}\b', cleaned)
    for m in matches:
        try:
            dt = _ddt.strptime(m, "%Y-%m-%d")
            dates.append(dt)
        except ValueError:
            pass
            
    # If no dates found, look for DD/MM/YYYY or DD-MM-YYYY
    matches = re.findall(r'\b\d{2}[-/.]\d{2}[-/.]\d{4}\b', cleaned)
    for m in matches:
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                dt = _ddt.strptime(m, fmt)
                dates.append(dt)
                break
            except ValueError:
                pass
                
    return dates

with pdfplumber.open(pdf_path) as pdf:
    total_p = len(pdf.pages)
    
    # First page
    first_txt = pdf.pages[0].extract_text() or ""
    first_dates = extract_dates(first_txt)
    print("First page dates:", first_dates)
    
    # Scan from end to find last page with dates
    last_dates = []
    for idx in range(total_p - 1, -1, -1):
        txt = pdf.pages[idx].extract_text() or ""
        dates = extract_dates(txt)
        if dates:
            print(f"Found dates on Page {idx+1}:", dates)
            last_dates = dates
            break
            
    if first_dates and last_dates:
        avg_first = sum(d.timestamp() for d in first_dates) / len(first_dates)
        avg_last = sum(d.timestamp() for d in last_dates) / len(last_dates)
        print(f"avg_first = {avg_first}, avg_last = {avg_last}")
        if avg_first > avg_last:
            print("Detected: REVERSE")
        else:
            print("Detected: FORWARD")
