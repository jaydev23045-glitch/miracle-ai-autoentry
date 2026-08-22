import sys
import os
import traceback

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'backend')))

try:
    from dbf_handler import MiracleDBFHandler
    from core.config import load_settings

    settings = load_settings()
    client_id = settings.get("active_client_id", "CMP0003")
    client_path = os.path.join(settings["miracle_base_path"], client_id)

    print(f"Testing update_party_ledger for client at: {client_path}")
    handler = MiracleDBFHandler(client_path)

    # Attempt test update call with user's exact inputs from screenshot
    code = handler.update_party_ledger(
        old_name="RAW_UNCREATED_BANK_TRANSACTION_NARRATION_999",
        new_name="PE PULSE PVT",
        print_name="PE PULSE PVT",
        group_code="G0000009",
        gstin=""
    )
    print(f"Result: SUCCESS! Updated code = '{code}'")
except Exception as e:
    print("Caught Exception during test:")
    traceback.print_exc()
