from pydantic import BaseModel, Field
from typing import List, Optional

class InvoiceItemSchema(BaseModel):
    name: str = ""
    qty: float = 1.0
    rate: float = 0.0
    gst_pct: float = 18.0
    taxable_amount: float = 0.0
    gst_amount: float = 0.0
    hsn: str = ""
    uom: str = "UNT"
    discount: float = 0.0

class InvoiceSchema(BaseModel):
    bill_no: str = ""
    date: str = ""
    party_name: str = ""
    party_gstin: str = ""
    taxable_amount: float = 0.0
    cgst: float = 0.0
    sgst: float = 0.0
    igst: float = 0.0
    gst: float = 0.0
    discount: float = 0.0
    freight: float = 0.0
    tcs: float = 0.0
    tds: float = 0.0
    total: float = 0.0
    items: List[InvoiceItemSchema] = []
    confidence_score: float = 100.0
    flags: List[str] = []

class BankTransactionSchema(BaseModel):
    date: str = ""
    reference_no: str = ""
    narration: str = ""
    amount: float = 0.0
    transaction_type: str = "Payment"  # "Payment", "Receipt"
    deposit: float = 0.0
    withdrawal: float = 0.0
    balance: float = 0.0
    mapped_ledger: str = ""
    group_hint: str = ""
    confidence_score: float = 100.0
    flags: List[str] = []
