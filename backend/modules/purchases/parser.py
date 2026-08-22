from modules.sales.parser import SalesParser

class PurchaseParser(SalesParser):
    def __init__(self, api_key: str | None = None, model_name: str = "gemini-3.1-flash-lite"):
        super().__init__(api_key, model_name)

    def clean_invoice_data(self, result_json: dict, client_memory: dict, module: str = "Purchases") -> dict:
        return super().clean_invoice_data(result_json, client_memory, module=module)
