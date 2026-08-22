import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

from dbf_handler import MiracleDBFHandler
from core.config import load_settings

settings = load_settings()
client_id = settings.get("active_client_id", "CMP0003")
client_path = os.path.join(settings["miracle_base_path"], client_id)

print(f"Testing read_products_all_years for client at: {client_path}")
handler = MiracleDBFHandler(client_path)
products = handler.read_products_all_years()

print(f"Total products fetched across all years: {len(products)}")
for p in products[:10]:
    print(f" - [{p.get('category', 'General')}] {p.get('name')} ({p.get('code')}) HSN: {p.get('hsn_code')}")
