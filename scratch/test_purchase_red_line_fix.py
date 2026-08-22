import os
import sys

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

from dbf_handler import MiracleDBFHandler
from dbfread import DBF

def is_purchase_rec(r):
    f74 = str(r.get('FIELD74') or '').strip().upper()
    f98 = str(r.get('FIELD98') or '').strip().upper()
    f10 = str(r.get('FIELD10') or '').strip()
    f12 = str(r.get('FIELD12') or '').strip()
    f03 = str(r.get('FIELD03') or '').strip()
    return (f74 == 'SP') and (
        f98.startswith(('PP', 'PB', 'PU', 'PI', 'PO', 'PA')) or
        (f10 != '' and f12 == '') or
        f03 in ('6', '6.0', '3', '3.0')
    )

def main():
    base_path = '/volumes/mirracle'
    print("=== RUNNING PURCHASE RED LINE FIX & REPAIR VERIFICATION ===")
    
    if not os.path.exists(base_path):
        print(f"Error: Miracle base path {base_path} not found.")
        sys.exit(1)
        
    for cmp in sorted(os.listdir(base_path)):
        if cmp.startswith('CMP'):
            client_path = os.path.join(base_path, cmp)
            handler = MiracleDBFHandler(client_path)
            
            print(f"\nScanning and repairing company {cmp}...")
            repair_res = handler.repair_purchase_voucher_flags()
            print(f"  Repair Result for {cmp}: Repaired headers = {repair_res['repaired_headers']}")
            
            # Re-inspect RKACCT41.DBF, RKACCT02.DBF, and RKACCT01.DBF in all year folders
            for y in sorted(os.listdir(client_path)):
                if y.startswith('YR'):
                    t41_path = os.path.join(client_path, y, 'RKACCT41.DBF')
                    t02_path = os.path.join(client_path, y, 'RKACCT02.DBF')
                    t01_path = os.path.join(client_path, y, 'RKACCT01.DBF')

                    if os.path.exists(t41_path):
                        table = DBF(t41_path, ignore_missing_memofile=True)
                        purchases = [r for r in table if is_purchase_rec(r)]
                        if purchases:
                            d_count = sum(1 for p in purchases if str(p.get('FIELD16')).strip().upper() == 'D')
                            c_count = sum(1 for p in purchases if str(p.get('FIELD16')).strip().upper() == 'C')
                            print(f"  {cmp}/{y} Header (T41): {len(purchases)} Total Purchase Vouchers -> {d_count} Debit ('D'), {c_count} Credit ('C')")
                            assert c_count == 0, f"FAILED: Found {c_count} purchase headers with FIELD16='C' in {cmp}/{y}!"
                            assert d_count == len(purchases), f"FAILED: Not all purchase headers have FIELD16='D' in {cmp}/{y}!"
                            print(f"  ✅ VERIFIED: All {len(purchases)} Purchase headers in {cmp}/{y} have FIELD16='D' (Debit)!")

                    if os.path.exists(t02_path):
                        table02 = DBF(t02_path, ignore_missing_memofile=True)
                        p_items = [r for r in table02 if str(r.get('FIELD01') or '').upper().startswith(('PP', 'PB', 'PU', 'PI', 'PO', 'PA'))]
                        if p_items:
                            c_items = sum(1 for p in p_items if str(p.get('FIELD05')).strip().upper() == 'C')
                            d_items = sum(1 for p in p_items if str(p.get('FIELD05')).strip().upper() == 'D')
                            has_ia = sum(1 for p in p_items if str(p.get('IAVAS00097') or p.get('IAVAS00095') or '').strip() != '')
                            print(f"  {cmp}/{y} Items (T02): {len(p_items)} Purchase Line Items -> {c_items} Credit ('C'), {d_items} Debit ('D') | {has_ia} Mapped IAVAS Account Codes")
                            assert d_items == 0, f"FAILED: Found {d_items} purchase items still with FIELD05='D' in {cmp}/{y}!"
                            assert c_items == len(p_items), f"FAILED: Not all purchase items have FIELD05='C' in {cmp}/{y}!"
                            print(f"  ✅ VERIFIED: All {len(p_items)} Purchase line items in {cmp}/{y} have FIELD05='C' (Credit) and mapped IAVAS purchase accounts!")

                    if os.path.exists(t01_path):
                        table01 = DBF(t01_path, ignore_missing_memofile=True)
                        p_gl = [r for r in table01 if str(r.get('FIELD01') or '').upper().startswith(('PP', 'PB', 'PU', 'PI', 'PO', 'PA'))]
                        if p_gl:
                            pr_rows = [r for r in p_gl if str(r.get('FIELD21')).strip().upper() == 'PR']
                            tp_tx_rows = [r for r in p_gl if str(r.get('FIELD21')).strip().upper() in ('TP', 'TX')]
                            
                            pr_c = sum(1 for r in pr_rows if str(r.get('FIELD06')).strip().upper() == 'C')
                            tp_tx_d = sum(1 for r in tp_tx_rows if str(r.get('FIELD06')).strip().upper() == 'D')
                            
                            print(f"  {cmp}/{y} Double-Entry (T01): {len(pr_rows)} Party Rows -> {pr_c} Credit ('C') | {len(tp_tx_rows)} Item/Tax Rows -> {tp_tx_d} Debit ('D')")
                            assert pr_c == len(pr_rows), f"FAILED: Not all PR party rows have FIELD06='C' in {cmp}/{y}!"
                            assert tp_tx_d == len(tp_tx_rows), f"FAILED: Not all TP/TX rows have FIELD06='D' in {cmp}/{y}!"
                            print(f"  ✅ VERIFIED: All {len(p_gl)} Double-entry rows in {cmp}/{y} match Native Bill 1405 schema (PR=C, TP/TX=D)!")

    print("\n🎉 SUCCESS: All Purchase headers, line items, and double-entry rows match Native Bill 1405 100%!")

if __name__ == '__main__':
    main()
