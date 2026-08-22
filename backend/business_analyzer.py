import os
import dbf
from collections import Counter
from dbf_handler import MiracleDBFHandler
import json

class BusinessAnalyzer:
    def __init__(self, client_path: str):
        self.client_path = client_path
        self.handler = MiracleDBFHandler(client_path)
        
        # Mapping of Group Codes (common to Miracle)
        self.DEBTORS = ['19', '22']
        self.CREDITORS = ['20', '23']
        self.BANKS = ['14']
        self.EXPENSES = ['24', '25'] # Direct, Indirect
        self.TAXES = ['21']

    def generate_raw_business_data(self) -> str:
        """Scans the DBF files to aggregate business context data."""
        print(f"Aggregating business data...")
        
        # 1. Load Ledgers
        ledgers = self.handler.read_ledgers()
        
        # 2. Tally Ledger usage frequency from RKACCT01.DBF
        ledger_freq = Counter()
        folders_to_scan = self.handler._get_all_year_folders()
        folders_to_scan.sort(reverse=True)
        
        for yr in folders_to_scan:
            t01_path = self.handler._get_table_path('RKACCT01.DBF', yr)
            if not os.path.exists(t01_path):
                t01_path = self.handler._get_table_path('rkacct01.dbf', yr)
                
            if os.path.exists(t01_path):
                try:
                    table = dbf.Table(t01_path)
                    table.open(mode=dbf.READ_ONLY)
                    
                    # Scan last 10,000 records for a solid sample of recent business
                    total_records = len(table)
                    start_idx = max(0, total_records - 10000)
                    
                    for i in range(total_records - 1, start_idx - 1, -1):
                        try:
                            r = table[i]
                            if not dbf.is_deleted(r):
                                l_code = str(r['FIELD04']).strip()
                                if l_code:
                                    ledger_freq[l_code] += 1
                        except Exception:
                            pass
                    table.close()
                except Exception as e:
                    print(f"Error reading {yr} T01 for analysis: {e}")
                    
            if len(ledger_freq) > 0:
                break
                
        # 3. Categorize Ledgers based on frequency
        debtors = []
        creditors = []
        banks = []
        expenses = []
        taxes = []
        
        for led in ledgers:
            code = led['code']
            cls = led.get('classification', 'Other')
            name = led['name']
            freq = ledger_freq.get(code, 0)
            
            entry = {"name": name, "freq": freq}
            
            if cls == 'Debtor':
                debtors.append(entry)
            elif cls == 'Creditor':
                creditors.append(entry)
            elif cls == 'Bank':
                banks.append(entry)
            elif cls == 'Expense':
                expenses.append(entry)
            elif 'tax' in name.lower() or 'gst' in name.lower() or 'duty' in name.lower():
                taxes.append(entry)
                
        # Sort each by frequency
        debtors.sort(key=lambda x: x['freq'], reverse=True)
        creditors.sort(key=lambda x: x['freq'], reverse=True)
        banks.sort(key=lambda x: x['freq'], reverse=True)
        expenses.sort(key=lambda x: x['freq'], reverse=True)
        taxes.sort(key=lambda x: x['freq'], reverse=True)
        
        # Take Top N
        def format_top(lst, n=20):
            names = [x['name'] for x in lst[:n]]
            return ", ".join(names) if names else "None detected"
            
        raw_data = f"""
CLIENT RAW AGGREGATED DATA:
Top Customers (Debtors): {format_top(debtors, 30)}
Top Suppliers (Creditors): {format_top(creditors, 30)}
Bank Accounts Used: {format_top(banks, 10)}
Common Expenses: {format_top(expenses, 30)}
Tax Ledgers Used: {format_top(taxes, 10)}
"""
        return raw_data
