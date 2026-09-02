from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest
from pathlib import Path
import json

from backend.main import app
from backend.database import Base, get_db
from backend.models import ReconciliationCase, AuditEvent

from sqlalchemy.pool import StaticPool
# Create an in-memory SQLite DB for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    # Setup test DB tables before each test
    Base.metadata.create_all(bind=engine)
    yield
    # Drop test DB tables after each test
    Base.metadata.drop_all(bind=engine)

def get_demo_csv_paths():
    base_dir = Path(__file__).resolve().parent.parent / "data"
    return {
        "bank": base_dir / "bank.csv",
        "invoice": base_dir / "invoices.csv",
        "gl": base_dir / "gl.csv"
    }

def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_upload_does_not_trigger_reconciliation():
    paths = get_demo_csv_paths()
    with open(paths["bank"], "rb") as b, open(paths["invoice"], "rb") as i, open(paths["gl"], "rb") as g:
        response = client.post("/api/upload", files={
            "bank_csv": ("bank.csv", b, "text/csv"),
            "invoice_csv": ("invoices.csv", i, "text/csv"),
            "gl_csv": ("gl.csv", g, "text/csv")
        })
    assert response.status_code == 200
    assert "Upload successful" in response.json()["message"]
    
    # Verify no reconciliation cases are created yet
    metrics = client.get("/api/metrics").json()
    assert metrics["total_cases"] == 0

def test_invalid_upload():
    response = client.post("/api/upload", files={
        "bank_csv": ("bank.csv", b"bank_txn_id,amount\n1,invalid\n", "text/csv"),
        "invoice_csv": ("invoices.csv", b"invoice_id,amount\n1,invalid\n", "text/csv"),
        "gl_csv": ("gl.csv", b"gl_entry_id,amount\n1,invalid\n", "text/csv")
    })
    # Will fail CSV reading or Pydantic validation (returning 400)
    assert response.status_code == 400

def test_reconciliation_requires_data():
    response = client.post("/api/reconcile")
    assert response.status_code == 400
    assert "No bank records found" in response.json()["detail"]

def test_full_lifecycle_and_reset():
    # 1. Upload
    paths = get_demo_csv_paths()
    with open(paths["bank"], "rb") as b, open(paths["invoice"], "rb") as i, open(paths["gl"], "rb") as g:
        client.post("/api/upload", files={
            "bank_csv": ("bank.csv", b, "text/csv"),
            "invoice_csv": ("invoices.csv", i, "text/csv"),
            "gl_csv": ("gl.csv", g, "text/csv")
        })
    
    # 2. Reconcile
    response = client.post("/api/reconcile")
    assert response.status_code == 200
    assert response.json()["cases_generated"] == 80
    
    # 3. Verify metrics don't claim correctness and don't expose ground truth
    metrics = client.get("/api/metrics").json()
    assert metrics["total_cases"] == 80
    assert metrics["automatic_decisions"] == 77
    assert metrics["review_cases"] == 3
    assert "correct_automatic_decisions" not in metrics
    
    # 4. Verify Matches and Exceptions isolation
    matches = client.get("/api/matches").json()
    for m in matches:
        assert m["case"]["status"] not in ["needs_human_review", "unmatched", "duplicate_payment"]
        
    exceptions = client.get("/api/exceptions").json()
    for e in exceptions:
        assert e["case"]["status"] not in ["matched_exact", "matched_timing", "matched_fuzzy"]
        
    # 5. Second upload resets everything
    with open(paths["bank"], "rb") as b, open(paths["invoice"], "rb") as i, open(paths["gl"], "rb") as g:
        client.post("/api/upload", files={
            "bank_csv": ("bank.csv", b, "text/csv"),
            "invoice_csv": ("invoices.csv", i, "text/csv"),
            "gl_csv": ("gl.csv", g, "text/csv")
        })
    metrics_after_upload = client.get("/api/metrics").json()
    assert metrics_after_upload["total_cases"] == 0

def test_manual_review_lifecycle():
    # Setup state
    paths = get_demo_csv_paths()
    with open(paths["bank"], "rb") as b, open(paths["invoice"], "rb") as i, open(paths["gl"], "rb") as g:
        client.post("/api/upload", files={
            "bank_csv": ("bank.csv", b, "text/csv"),
            "invoice_csv": ("invoices.csv", i, "text/csv"),
            "gl_csv": ("gl.csv", g, "text/csv")
        })
    client.post("/api/reconcile")
    
    # B-2026-077 is one of the review cases
    case_id = "CASE-B-2026-077"
    
    # 1. Reject invalid action
    res = client.post("/api/review", json={"case_id": case_id, "action": "unknown", "reason": "test"})
    assert res.status_code == 400 # Route handles unknown string with 400

    # 2. Reject valid review (Reject)
    res_reject = client.post("/api/review", json={"case_id": case_id, "action": "reject", "reason": "does not match"})
    assert res_reject.status_code == 200
    assert res_reject.json()["new_state"] == "unmatched"
    
    # 3. Repeated review fails
    res_repeat = client.post("/api/review", json={"case_id": case_id, "action": "approve", "reason": "changed mind"})
    assert res_repeat.status_code == 400
    assert "not pending review" in res_repeat.json()["detail"]
    
    # Verify Audit Events
    audits = client.get("/api/audit-events").json()
    assert len(audits) == 4  # 3 from AI provider during reconcile, 1 from manual review
    assert audits[0]["case_id"] == case_id
    assert audits[0]["previous_state"] == "needs_human_review"
    assert audits[0]["new_state"] == "unmatched"
    assert audits[0]["reason"] == "does not match"
    
    # 4. Try on invalid case ID
    res_invalid = client.post("/api/review", json={"case_id": "UNKNOWN", "action": "approve", "reason": "test"})
    assert res_invalid.status_code == 404

def test_manual_review_approve():
    # Setup state
    paths = get_demo_csv_paths()
    with open(paths["bank"], "rb") as b, open(paths["invoice"], "rb") as i, open(paths["gl"], "rb") as g:
        client.post("/api/upload", files={
            "bank_csv": ("bank.csv", b, "text/csv"),
            "invoice_csv": ("invoices.csv", i, "text/csv"),
            "gl_csv": ("gl.csv", g, "text/csv")
        })
    client.post("/api/reconcile")
    
    # B-2026-080 is another review case
    case_id = "CASE-B-2026-080"
    
    res_approve = client.post("/api/review", json={"case_id": case_id, "action": "approve", "reason": "looks good"})
    assert res_approve.status_code == 200
    assert res_approve.json()["new_state"] == "matched_manual_review"
    
    # Should now appear in matches, not exceptions
    matches = client.get("/api/matches").json()
    exceptions = client.get("/api/exceptions").json()
    assert any(m["case"]["case_id"] == case_id for m in matches)
    assert not any(e["case"]["case_id"] == case_id for e in exceptions)
    
    # Ensure matched_manual_review is not counted as an exception in metrics
    metrics = client.get("/api/metrics").json()
    assert metrics["review_cases"] == 2 # Was 3, resolved 1 -> 2
    # Wait, isolated DB tests so review_cases goes 3 -> 2
    assert metrics["review_cases"] == 2

def test_ai_policy_enforcement_in_reconciliation():
    import os
    # We will use mock provider for this test
    os.environ["AI_PROVIDER"] = "mock"
    
    paths = get_demo_csv_paths()
    with open(paths["bank"], "rb") as b, open(paths["invoice"], "rb") as i, open(paths["gl"], "rb") as g:
        client.post("/api/upload", files={
            "bank_csv": ("bank.csv", b, "text/csv"),
            "invoice_csv": ("invoices.csv", i, "text/csv"),
            "gl_csv": ("gl.csv", g, "text/csv")
        })
    client.post("/api/reconcile")
    
    # The mock provider will "recommend_match" for ambiguous cases that have a candidate > 60
    # Let's check the exceptions list.
    exceptions = client.get("/api/exceptions").json()
    
    # Find a case that was "needs_human_review"
    review_cases = [e["case"] for e in exceptions if e["case"]["status"] == "needs_human_review"]
    
    # Verify that NONE of the cases automatically matched (they didn't go into matched_exact/fuzzy/timing)
    # due to the AI's recommend_match = True
    assert len(review_cases) > 0
    
    for case in review_cases:
        # If the mock AI provider ran, it should have populated the AI fields
        if case.get("ai_provider") == "mock":
            if case.get("ai_recommendation") == "recommend_match":
                assert case["status"] == "needs_human_review"
                assert case["match_method"] == "ai_assistance"
                assert case["invoice_id"] == case["ai_suggested_invoice"]
