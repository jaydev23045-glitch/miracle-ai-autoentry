import pdfplumber
import sys

file_path = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/Test_Samples_And_Archives/DEMO SALES/Aksharbrahm/259876778999_1785754792241.pdf"

with pdfplumber.open(file_path) as pdf:
    for idx, page in enumerate(pdf.pages):
        print(f"--- Page {idx+1} ---")
        print(page.extract_text())
