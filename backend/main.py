import csv
import re
from datetime import datetime
from io import StringIO
from typing import List, Dict

from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import pydantic
import os
from dotenv import load_dotenv
load_dotenv()

from backend import models, schemas
from backend.database import engine, get_db, Base
from backend.matcher import reconcile_records, get_candidates_for_bank
from backend.ai_provider import get_ai_provider

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="ReconPilot API")

# Allow CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BANK_ALIASES = {
    "bank_txn_id": ["bank_txn_id", "transaction_id", "txn_id"],
    "date": ["date", "transaction_date", "txn_date", "payment_date", "value_date"],
    "description": ["description", "narration", "transaction_description", "remarks"],
    "reference": ["reference", "ref", "utr", "transaction_reference"],
    "amount": ["amount", "transaction_amount", "txn_amount", "debit_amount", "credit_amount"]
}

INVOICE_ALIASES = {
    "invoice_id": ["invoice_id", "invoice_number", "invoice_no", "bill_no"],
    "date": ["date", "invoice_date", "bill_date"],
    "client_name": ["client_name", "customer", "customer_name", "vendor", "vendor_name", "party_name"],
    "gstin": ["gstin", "gst_number", "tax_id"],
    "gst_rate": ["gst_rate", "tax_rate", "gst_percentage"],
    "total_amount": ["total_amount", "amount", "invoice_amount", "invoice_value"]
}

GL_ALIASES = {
    "gl_entry_id": ["gl_entry_id", "entry_id", "journal_id", "transaction_id"],
    "date": ["date", "posting_date", "entry_date"],
    "description": ["description", "narration", "particulars", "remarks"],
    "amount": ["amount", "transaction_amount", "debit", "credit"],
    "reference": ["reference", "ref", "document_reference"]
}

def parse_and_format_date(val: str) -> str:
    val = val.strip()

    try:
        datetime.strptime(val, "%d-%m-%Y")
        return val
    except ValueError:
        pass

    m = re.match(r"^(\d{2})[-/](\d{2})[-/]\d{4}$", val)
    if m:
        p1, p2 = int(m.group(1)), int(m.group(2))
        if p1 <= 12 and p2 <= 12 and p1 != p2:
            raise HTTPException(400, f"Ambiguous date detected: '{val}'. Cannot safely determine day vs month.")

    formats = ["%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d", "%b %d %Y", "%m-%d-%Y"]
    for fmt in formats:
        try:
            d = datetime.strptime(val, fmt)
            return d.strftime("%d-%m-%Y")
        except ValueError:
            pass
    raise HTTPException(400, f"Invalid or unparseable date: '{val}'. Please use a standard format like YYYY-MM-DD.")

def clean_amount(val: str):
    cleaned = re.sub(r"[^\d\.-]", "", val)
    try:
        return float(cleaned)
    except ValueError:
        return val

def normalize_csv(file: UploadFile, aliases: dict) -> List[Dict]:
    content = file.file.read().decode("utf-8")
    reader = csv.DictReader(StringIO(content))
    raw_headers = reader.fieldnames or []

    header_map = {}
    for h in raw_headers:
        norm_h = re.sub(r"[\s\-]+", "_", h.strip().lower())
        header_map[h] = norm_h

    canonical_map = {}
    mapped_canonicals = set()
    for raw_h in raw_headers:
        norm_h = header_map[raw_h]
        for canonical, alias_list in aliases.items():
            if norm_h in alias_list:
                if canonical in mapped_canonicals and canonical_map.get(raw_h) != canonical:
                    raise HTTPException(400, f"Ambiguous columns detected: multiple columns map to '{canonical}'.")
                canonical_map[raw_h] = canonical
                mapped_canonicals.add(canonical)
                break

    records = []
    for row in reader:
        new_row = {}
        for raw_h, val in row.items():
            canonical = canonical_map.get(raw_h)
            if canonical:
                v = val.strip() if isinstance(val, str) else val
                if canonical in ("amount", "total_amount"):
                    v = clean_amount(v)
                elif canonical == "date":
                    v = parse_and_format_date(v)
                new_row[canonical] = v
        records.append(new_row)

    return records

@app.post("/api/upload")
async def upload_files(
    bank_csv: UploadFile = File(...),
    invoice_csv: UploadFile = File(...),
    gl_csv: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Clears existing data, parses and saves new raw data. DOES NOT run reconciliation.
    """
    db.query(models.AuditEvent).delete()
    db.query(models.ReconciliationCase).delete()
    db.query(models.BankTransaction).delete()
    db.query(models.Invoice).delete()
    db.query(models.GLRecord).delete()
    db.commit()

    data_dir = os.getenv("DATA_DIR", "./backend/data")
    os.makedirs(data_dir, exist_ok=True)

    bank_content = bank_csv.file.read()
    invoice_content = invoice_csv.file.read()
    gl_content = gl_csv.file.read()

    with open(os.path.join(data_dir, "uploaded_bank.csv"), "wb") as f:
        f.write(bank_content)
    with open(os.path.join(data_dir, "uploaded_invoice.csv"), "wb") as f:
        f.write(invoice_content)
    with open(os.path.join(data_dir, "uploaded_gl.csv"), "wb") as f:
        f.write(gl_content)

    bank_csv.file.seek(0)
    invoice_csv.file.seek(0)
    gl_csv.file.seek(0)

    bank_data = normalize_csv(bank_csv, BANK_ALIASES)
    invoice_data = normalize_csv(invoice_csv, INVOICE_ALIASES)
    gl_data = normalize_csv(gl_csv, GL_ALIASES)

    try:
        # Use schemas for validation
        bank_records = [schemas.BankTransaction(**row) for row in bank_data]
        invoice_records = [schemas.Invoice(**row) for row in invoice_data]
        gl_records = [schemas.GLRecord(**row) for row in gl_data]
    except pydantic.ValidationError as e:
        missing_fields = [str(err["loc"][0]) for err in e.errors() if err["type"] == "missing"]
        if missing_fields:
            raise HTTPException(status_code=400, detail=f"Missing required field(s): {', '.join(missing_fields)}.")
        raise HTTPException(status_code=400, detail="CSV Validation Error. Please check column headers and data types.")

    for r in bank_records: db.add(models.BankTransaction(**r.model_dump()))
    for r in invoice_records: db.add(models.Invoice(**r.model_dump()))
    for r in gl_records: db.add(models.GLRecord(**r.model_dump()))
    db.commit()

    return {
        "message": "Upload successful and validated.",
        "records_uploaded": {
            "bank": len(bank_records),
            "invoices": len(invoice_records),
            "gl": len(gl_records)
        }
    }

@app.post("/api/reconcile")
def run_reconciliation(db: Session = Depends(get_db)):
    """
    Runs deterministic matcher over existing DB records and replaces cases.
    """
    db.query(models.ReconciliationCase).delete()
    db.query(models.AuditEvent).delete()
    db.commit()

    # Raw ORM models aren't directly compatible with reconciliation engine input type hints
    # but the engine just accesses attributes.
    bank_records = db.query(models.BankTransaction).all()
    invoice_records = db.query(models.Invoice).all()
    gl_records = db.query(models.GLRecord).all()

    if not bank_records:
        raise HTTPException(status_code=400, detail="No bank records found. Please upload data first.")

    cases = reconcile_records(bank_records, invoice_records, gl_records)

    ai_provider = get_ai_provider()

    for c in cases:
        if c.status == "needs_human_review":
            bank = next((b for b in bank_records if b.bank_txn_id == c.bank_txn_id), None)
            if bank:
                cands = get_candidates_for_bank(bank, invoice_records, window=5)
                case_info = {
                    "bank_transaction": {
                        "date": bank.date,
                        "description": bank.description,
                        "amount": bank.amount,
                        "reference": bank.reference
                    },
                    "candidates": [
                        {"invoice_id": inv.invoice_id, "score": score, "client_name": inv.client_name, "amount": inv.total_amount, "date": inv.date}
                        for score, inv in cands
                    ],
                    "deterministic_reason": c.reason
                }

                recommendation = ai_provider.analyze(case_info)

                # Deterministic Policy Layer
                c.ai_provider = os.environ.get("AI_PROVIDER", "mock").lower()
                c.ai_confidence = recommendation.confidence
                c.ai_reason = recommendation.reason
                c.ai_recommendation = recommendation.recommendation
                c.ai_suggested_invoice = recommendation.suggested_invoice_id

                # Apply policy safely without converting to an automatic match
                if recommendation.recommendation == "recommend_match":
                    c.invoice_id = recommendation.suggested_invoice_id
                    c.match_method = "ai_assistance"
                    # KEEP status as needs_human_review so human confirms it
                elif recommendation.recommendation == "reject":
                    # Reject doesn't silently unmatch
                    c.match_method = "ai_assistance"

                c_dump = c.model_dump()
                candidates = c_dump.pop("candidates", None)
                c_db = models.ReconciliationCase(**c_dump)
                if candidates is not None:
                    import json
                    c_db.candidates_json = json.dumps(candidates)
                db.add(c_db)

                # Add audit event for AI assistance
                db.add(models.AuditEvent(
                    case_id=c.case_id,
                    previous_state="deterministic_ambiguity",
                    new_state=c.status,
                    reason=f"AI Provider ({c.ai_provider}) analyzed: {recommendation.reason}",
                    reviewer_name="AI System"
                ))
            else:
                c_dump = c.model_dump()
                candidates = c_dump.pop("candidates", None)
                c_db = models.ReconciliationCase(**c_dump)
                if candidates is not None:
                    import json
                    c_db.candidates_json = json.dumps(candidates)
                db.add(c_db)
        else:
            c_dump = c.model_dump()
            candidates = c_dump.pop("candidates", None)
            c_db = models.ReconciliationCase(**c_dump)
            if candidates is not None:
                import json
                c_db.candidates_json = json.dumps(candidates)
            db.add(c_db)

    db.commit()

    return {
        "status": "success",
        "cases_generated": len(cases)
    }

@app.get("/api/metrics")
def get_metrics(db: Session = Depends(get_db)):
    """
    Returns operational metrics based on the current state of reconciliation cases.

    Terminology:
    - review_cases: Cases explicitly pending human review ("needs_human_review").
    - review_rate: review_cases / total_cases.
    - unresolved_exceptions: Cases that are permanently unresolved (e.g. duplicate payments,
      missing documents, amount mismatches) or reviews that have been explicitly rejected ("unmatched").
      This EXCLUDES pending human review and any successfully matched cases.
    - exception_rate: unresolved_exceptions / total_cases.
    """
    cases = db.query(models.ReconciliationCase).all()
    total = len(cases)
    if total == 0:
        return {
            "total_cases": 0,
            "automatic_decisions": 0,
            "automatic_matches": 0,
            "review_cases": 0,
            "unresolved_exceptions": 0,
            "coverage": 0.0,
            "review_rate": 0.0,
            "exception_rate": 0.0
        }

    auto_decisions = [c for c in cases if c.status != "needs_human_review"]
    review_cases = [c for c in cases if c.status == "needs_human_review"]
    auto_matches = [c for c in cases if c.status in ["matched_exact", "matched_timing", "matched_fuzzy"]]

    unresolved_exception_statuses = [
        "duplicate_payment", "missing_invoice", "missing_gl_entry",
        "amount_mismatch_tds", "amount_mismatch_bank_fee", "unmatched"
    ]
    exceptions = [c for c in cases if c.status in unresolved_exception_statuses]

    return {
        "total_cases": total,
        "automatic_decisions": len(auto_decisions),
        "automatic_matches": len(auto_matches),
        "review_cases": len(review_cases),
        "unresolved_exceptions": len(exceptions),
        "coverage": len(auto_decisions) / total,
        "review_rate": len(review_cases) / total,
        "exception_rate": len(exceptions) / total
    }

@app.get("/api/matches")
def get_matches(db: Session = Depends(get_db)):
    match_statuses = ["matched_exact", "matched_timing", "matched_fuzzy", "matched_manual_review"]
    cases = db.query(models.ReconciliationCase).filter(models.ReconciliationCase.status.in_(match_statuses)).all()
    results = []
    for c in cases:
        bank = db.query(models.BankTransaction).filter(models.BankTransaction.bank_txn_id == c.bank_txn_id).first()
        invoice = db.query(models.Invoice).filter(models.Invoice.invoice_id == c.invoice_id).first() if c.invoice_id else None
        gl = db.query(models.GLRecord).filter(models.GLRecord.gl_entry_id == c.gl_entry_id).first() if c.gl_entry_id else None
        results.append({
            "case": c,
            "bank": bank,
            "invoice": invoice,
            "gl": gl
        })
    return results

@app.get("/api/exceptions")
def get_exceptions(db: Session = Depends(get_db)):
    exception_statuses = [
        "needs_human_review", "duplicate_payment", "missing_invoice",
        "missing_gl_entry", "amount_mismatch_tds", "amount_mismatch_bank_fee", "unmatched"
    ]
    cases = db.query(models.ReconciliationCase).filter(models.ReconciliationCase.status.in_(exception_statuses)).all()
    results = []
    for c in cases:
        bank = db.query(models.BankTransaction).filter(models.BankTransaction.bank_txn_id == c.bank_txn_id).first()
        invoice = db.query(models.Invoice).filter(models.Invoice.invoice_id == c.invoice_id).first() if c.invoice_id else None
        gl = db.query(models.GLRecord).filter(models.GLRecord.gl_entry_id == c.gl_entry_id).first() if c.gl_entry_id else None
        results.append({
            "case": c,
            "bank": bank,
            "invoice": invoice,
            "gl": gl
        })
    return results

@app.post("/api/review")
def manual_review(req: schemas.ReviewRequest, db: Session = Depends(get_db)):
    case = db.query(models.ReconciliationCase).filter(models.ReconciliationCase.case_id == req.case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if case.status != "needs_human_review":
        raise HTTPException(status_code=400, detail=f"Case is not pending review. Current status: {case.status}")

    previous_state = case.status
    if req.action == "approve":
        case.status = "matched_manual_review"
    elif req.action == "reject":
        case.status = "unmatched"
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    audit = models.AuditEvent(
        case_id=req.case_id,
        previous_state=previous_state,
        new_state=case.status,
        reason=req.reason,
        reviewer_name="Demo Accountant"
    )
    db.add(audit)
    db.commit()
    return {"status": "success", "new_state": case.status}

@app.get("/api/audit-events")
def get_audit_events(db: Session = Depends(get_db)):
    events = db.query(models.AuditEvent).order_by(models.AuditEvent.timestamp.desc()).all()
    return events

@app.get("/api/health")
def health_check():
    return {"status": "ok"}

@app.get("/api/cash_position")
def get_cash_position(db: Session = Depends(get_db)):
    opening_balance = 100000.00
    cases = db.query(models.ReconciliationCase).filter(
        models.ReconciliationCase.status.in_(["matched_exact", "matched_timing", "matched_fuzzy", "matched_manual_review"])
    ).all()

    reconciled_credits = sum(
        db.query(models.BankTransaction.amount).filter(models.BankTransaction.bank_txn_id == c.bank_txn_id).scalar() or 0
        for c in cases
    )

    return {
        "opening_balance": opening_balance,
        "reconciled_credits": reconciled_credits,
        "reconciled_debits": 0,
        "current_balance": opening_balance + reconciled_credits
    }
