from sqlalchemy import Column, String, Float, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from backend.database import Base
from datetime import datetime

class BankTransaction(Base):
    __tablename__ = "bank_transactions"
    
    bank_txn_id = Column(String, primary_key=True, index=True)
    date = Column(String)
    description = Column(String)
    reference = Column(String)
    amount = Column(Float)

class Invoice(Base):
    __tablename__ = "invoices"
    
    invoice_id = Column(String, primary_key=True, index=True)
    date = Column(String)
    client_name = Column(String)
    gstin = Column(String)
    gst_rate = Column(Integer)
    total_amount = Column(Float)

class GLRecord(Base):
    __tablename__ = "gl_records"
    
    gl_entry_id = Column(String, primary_key=True, index=True)
    date = Column(String)
    description = Column(String)
    amount = Column(Float)
    reference = Column(String)

class ReconciliationCase(Base):
    __tablename__ = "reconciliation_cases"
    
    case_id = Column(String, primary_key=True, index=True)
    status = Column(String, index=True)
    match_method = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    bank_txn_id = Column(String, unique=True, index=True)
    invoice_id = Column(String, nullable=True)
    gl_entry_id = Column(String, nullable=True)
    amount_delta = Column(Float, nullable=True)
    date_delta = Column(Integer, nullable=True)
    vendor_similarity = Column(Float, nullable=True)
    reason = Column(String, nullable=True)
    
    # AI Assistance fields
    ai_provider = Column(String, nullable=True)
    ai_recommendation = Column(String, nullable=True)
    ai_reason = Column(String, nullable=True)
    ai_suggested_invoice = Column(String, nullable=True)
    ai_confidence = Column(Float, nullable=True)
    candidates_json = Column(String, nullable=True)

    @property
    def candidates(self):
        if self.candidates_json:
            import json
            return json.loads(self.candidates_json)
        return None

class AuditEvent(Base):
    __tablename__ = "audit_events"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    case_id = Column(String, ForeignKey("reconciliation_cases.case_id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    previous_state = Column(String)
    new_state = Column(String)
    reason = Column(String)
    reviewer_name = Column(String)
