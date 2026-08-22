import dbf
import json
import os
import datetime
from decimal import Decimal

def default_serializer(obj):
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, bytes):
        return obj.decode('utf-8', errors='ignore')
    return str(obj)

def get_record_dict(record, table):
    if dbf.is_deleted(record): return None
    return {k: str(record[k]).strip() if isinstance(record[k], str) else record[k] for k in table.field_names}

def dump_vouchers(yr_folder):
    t41 = dbf.Table(f"{yr_folder}/RKACCT41.DBF").open(mode=dbf.READ_ONLY)
    t02 = dbf.Table(f"{yr_folder}/RKACCT02.DBF").open(mode=dbf.READ_ONLY)
    t52 = dbf.Table(f"{yr_folder}/RKACCT52.DBF").open(mode=dbf.READ_ONLY)
    
    sales_v_id = None
    purchase_v_id = None
    
    for r in t41:
        if dbf.is_deleted(r): continue
        v_id = str(r['FIELD01']).strip()
        f98 = str(r['FIELD98']).strip()
        if f98 == 'SS' and not sales_v_id and len(v_id) == 12:
            sales_v_id = v_id
        if f98 == 'PP' and not purchase_v_id and len(v_id) == 12:
            purchase_v_id = v_id
        if sales_v_id and purchase_v_id: break
        
    print(f"Found Sales: {sales_v_id}, Purchase: {purchase_v_id}")
    
    for v_id, name in [(sales_v_id, "golden_sales"), (purchase_v_id, "golden_purchase")]:
        if not v_id: continue
        
        data = {"header": None, "details": [], "tax_summary": []}
        
        for r in t41:
            if dbf.is_deleted(r): continue
            if str(r['FIELD01']).strip() == v_id:
                data["header"] = get_record_dict(r, t41)
                break
                
        for r in t02:
            if dbf.is_deleted(r): continue
            if str(r['FIELD01']).strip() == v_id:
                data["details"].append(get_record_dict(r, t02))
                
        for r in t52:
            if dbf.is_deleted(r): continue
            if str(r['T52F01']).strip() == v_id:
                data["tax_summary"].append(get_record_dict(r, t52))
                
        with open(f"docs/examples/{name}.json", "w") as f:
            json.dump(data, f, indent=2, default=default_serializer)
            
    t41.close(); t02.close(); t52.close()

dump_vouchers('CMP0006/YR26')
