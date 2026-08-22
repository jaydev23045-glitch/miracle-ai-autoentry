import pdfplumber

pdf_path = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/Test_Samples_And_Archives/DEMO SALES/Aksharbrahm/259876778999_1785754792241.pdf"

with pdfplumber.open(pdf_path) as pdf:
    print("--- FIRST PAGE TEXT ---")
    print(pdf.pages[0].extract_text())
    print("\n--- LAST PAGE TEXT ---")
    print(pdf.pages[len(pdf.pages) - 1].extract_text())
