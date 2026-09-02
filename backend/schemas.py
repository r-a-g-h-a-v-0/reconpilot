from typing import Optional
from pydantic import BaseModel

# Input Models
class BankTransaction(BaseModel):
    bank_txn_id: str
    date: str
    description: str
    reference: str
    amount: float

class Invoice(BaseModel):
    invoice_id: str
    date: str
    client_name: str
    gstin: str
    gst_rate: int
    total_amount: float

class GLRecord(BaseModel):
    gl_entry_id: str
    date: str
    description: str
    amount: float
    reference: str

# Output Model
class ReconciliationCase(BaseModel):
    case_id: str
    status: str
    match_method: Optional[str] = None
    confidence: Optional[float] = None
    bank_txn_id: str
    invoice_id: Optional[str] = None
    gl_entry_id: Optional[str] = None
    amount_delta: Optional[float] = None
    date_delta: Optional[int] = None
    vendor_similarity: Optional[float] = None
    reason: Optional[str] = None
    ai_provider: Optional[str] = None
    ai_recommendation: Optional[str] = None
    ai_reason: Optional[str] = None
    ai_suggested_invoice: Optional[str] = None
    ai_confidence: Optional[float] = None

class ReviewRequest(BaseModel):
    case_id: str
    action: str  # "approve" or "reject"
    reason: str
