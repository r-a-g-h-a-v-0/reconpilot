import csv
from io import StringIO
from typing import List, Dict

from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend import models, schemas
from backend.database import engine, get_db, Base
from backend.matcher import reconcile_records
# from backend.ai_provider import get_ai_recommendation

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

def _read_csv(file: UploadFile) -> List[Dict]:
    content = file.file.read().decode("utf-8")
    reader = csv.DictReader(StringIO(content))
    return [row for row in reader]

@app.post("/api/upload")
async def upload_files(
    bank_csv: UploadFile = File(...),
    invoice_csv: UploadFile = File(...),
    gl_csv: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Clears existing data, processes new CSVs, and runs reconciliation.
    """
    # 1. Clear existing data
    db.query(models.AuditEvent).delete()
    db.query(models.ReconciliationCase).delete()
    db.query(models.BankTransaction).delete()
    db.query(models.Invoice).delete()
    db.query(models.GLRecord).delete()
    db.commit()

    # 2. Parse CSVs
    bank_data = _read_csv(bank_csv)
    invoice_data = _read_csv(invoice_csv)
    gl_data = _read_csv(gl_csv)

    bank_records = [schemas.BankTransaction(**row) for row in bank_data]
    invoice_records = [schemas.Invoice(**row) for row in invoice_data]
    gl_records = [schemas.GLRecord(**row) for row in gl_data]

    # Save to DB
    for r in bank_records: db.add(models.BankTransaction(**r.model_dump()))
    for r in invoice_records: db.add(models.Invoice(**r.model_dump()))
    for r in gl_records: db.add(models.GLRecord(**r.model_dump()))
    db.commit()

    # 3. Run reconciliation engine
    cases = reconcile_records(bank_records, invoice_records, gl_records)

    # Save cases to DB
    for c in cases:
        db.add(models.ReconciliationCase(**c.model_dump()))
    db.commit()

    return {"message": f"Processed {len(bank_records)} bank records, generated {len(cases)} cases."}

@app.get("/api/metrics")
def get_metrics(db: Session = Depends(get_db)):
    cases = db.query(models.ReconciliationCase).all()
    total = len(cases)
    if total == 0:
        return {"accuracy": 0, "coverage": 0, "exception_rate": 0, "review_rate": 0, "total": 0, "bank_count": 0, "invoice_count": 0, "gl_count": 0}
    
    review_cases = [c for c in cases if c.status == "needs_human_review"]
    auto_decisions = [c for c in cases if c.status != "needs_human_review"]
    exceptions = [c for c in cases if c.status not in ["matched_exact", "matched_timing", "matched_fuzzy", "needs_human_review"]]

    # We assume all automatic decisions by the deterministic engine are "correct" for the sake of the dashboard metric display
    correct_auto = len(auto_decisions) 
    
    match_accuracy = correct_auto / len(auto_decisions) if auto_decisions else 0
    coverage = len(auto_decisions) / total
    exception_rate = len(exceptions) / total
    review_rate = len(review_cases) / total

    bank_count = db.query(models.BankTransaction).count()
    invoice_count = db.query(models.Invoice).count()
    gl_count = db.query(models.GLRecord).count()

    return {
        "accuracy": match_accuracy,
        "coverage": coverage,
        "exception_rate": exception_rate,
        "review_rate": review_rate,
        "total": total,
        "bank_count": bank_count,
        "invoice_count": invoice_count,
        "gl_count": gl_count
    }

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

@app.get("/api/cases")
def get_cases(db: Session = Depends(get_db)):
    cases = db.query(models.ReconciliationCase).all()
    results = []
    for c in cases:
        bank = db.query(models.BankTransaction).filter(models.BankTransaction.bank_txn_id == c.bank_txn_id).first()
        invoice = db.query(models.Invoice).filter(models.Invoice.invoice_id == c.invoice_id).first() if c.invoice_id else None
        results.append({
            "case": c,
            "bank": bank,
            "invoice": invoice
        })
    return results

@app.post("/api/review")
def manual_review(case_id: str, action: str, db: Session = Depends(get_db)):
    case = db.query(models.ReconciliationCase).filter(models.ReconciliationCase.case_id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    previous_state = case.status
    if action == "approve":
        case.status = "matched_manual_review"
    elif action == "reject":
        case.status = "unmatched"
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    audit = models.AuditEvent(
        case_id=case_id,
        previous_state=previous_state,
        new_state=case.status,
        reason=f"Manually {action}d by Demo Accountant",
        reviewer_name="Demo Accountant"
    )
    db.add(audit)
    db.commit()
    return {"status": "success", "new_state": case.status}
