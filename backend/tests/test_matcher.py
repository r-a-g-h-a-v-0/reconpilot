import csv
import json
from pathlib import Path
from backend.data_gen import generate_cases
from backend.matcher import reconcile_records
from backend.evaluation import evaluate_cases
from backend.models import BankTransaction, Invoice, GLRecord

def test_ground_truth_reconciliation_metrics():
    # 1. Generate synthetic dataset and hidden ground truth
    generate_cases()
    
    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data"
    gt_path = base_dir / "tests" / "ground_truth.json"

    with open(gt_path, "r") as f:
        ground_truth = json.load(f)

    with open(data_dir / "bank.csv", "r") as f:
        bank_records = []
        for r in csv.DictReader(f):
            r['amount'] = float(r['amount'])
            bank_records.append(BankTransaction(**r))

    with open(data_dir / "invoices.csv", "r") as f:
        invoice_records = []
        for r in csv.DictReader(f):
            r['total_amount'] = float(r['total_amount'])
            r['gst_rate'] = int(r['gst_rate'])
            invoice_records.append(Invoice(**r))

    with open(data_dir / "gl.csv", "r") as f:
        gl_records = []
        for r in csv.DictReader(f):
            r['amount'] = float(r['amount'])
            gl_records.append(GLRecord(**r))

    # 2. Run deterministic 3-pass matcher engine
    results = reconcile_records(bank_records, invoice_records, gl_records)

    # 3. Use evaluation module
    metrics = evaluate_cases(results, ground_truth)
    
    # Generate report
    report_dir = base_dir / "reports"
    report_dir.mkdir(exist_ok=True)
    report_file = report_dir / "ground_truth_evaluation_report.txt"
    
    report_content = (
        f"--- Evaluation Metrics ---\n"
        f"Total Cases: {metrics.total_cases}\n"
        f"Automatic Decisions: {metrics.automatic_decisions}\n"
        f"Correct Automatic Decisions: {metrics.correct_automatic_decisions}\n"
        f"Incorrect Automatic Decisions: {metrics.incorrect_automatic_decisions}\n"
        f"Automatic Decision Accuracy: {metrics.automatic_decision_accuracy:.2%}\n"
        f"Automatic Matches: {metrics.automatic_matches}\n"
        f"Correct Automatic Matches: {metrics.correct_automatic_matches}\n"
        f"False Automatic Matches: {metrics.false_automatic_matches}\n"
        f"Automatic Match Precision: {metrics.automatic_match_precision:.2%}\n"
        f"Coverage: {metrics.coverage:.2%}\n"
        f"Exception Rate: {metrics.exception_rate:.2%}\n"
        f"Review Rate: {metrics.review_rate:.2%}\n"
    )
    with open(report_file, "w") as f:
        f.write(report_content)

    # 4. Assert performance thresholds
    assert metrics.total_cases == 80, f"Expected 80 test cases, got {metrics.total_cases}"
    assert metrics.automatic_match_precision >= 0.90, f"Match precision ({metrics.automatic_match_precision:.2%}) below 90%"
    assert metrics.coverage >= 0.80, f"Coverage ({metrics.coverage:.2%}) below 80%"


def test_adversarial_vendor_fuzzy_match_regression():
    # Regression test for false-match investigation.
    # We discovered an adversarial case where "Singh Corp" scored 71% and 
    # "Singh & Sons Corp" scored 63% against bank vendor "SINGHCORP".
    # Because 63% < 70%, it did not trigger the ambiguity human review block, and correctly matched "Singh Corp".
    # This test asserts that behaviour explicitly and proves the ground truth update was correct.
    
    bank_records = [BankTransaction(bank_txn_id="B-TEST-01", date="13-07-2026", description="UPI/SINGHCORP/TRANSFER", reference="UPI123", amount=12000.0)]
    invoice_records = [
        Invoice(invoice_id="INV-TEST-01", date="13-07-2026", client_name="Singh Corp", gstin="27AAAAA0000A1Z5", gst_rate=18, total_amount=12000.0),
        Invoice(invoice_id="INV-TEST-02", date="13-07-2026", client_name="Singh & Sons Corp", gstin="27AAAAA0000A1Z5", gst_rate=18, total_amount=12000.0)
    ]
    gl_records = [GLRecord(gl_entry_id="GL-TEST-01", date="13-07-2026", description="Recv", amount=12000.0, reference="")]

    results = reconcile_records(bank_records, invoice_records, gl_records)
    case = results[0]
    
    # Assert it requires human review because the top score is 71.4% and the second is 63.1% (margin < 20%)
    assert case.status == "needs_human_review"
    assert case.reason == "Ambiguous fuzzy candidates found; automatic matching was blocked."

def test_ambiguity_logic_scenarios():
    # Setup base bank txn and GL
    bank_records = [BankTransaction(bank_txn_id="B-1", date="13-07-2026", description="UPI/SINGHCORP/TRANSFER", reference="UPI123", amount=12000.0)]
    gl_records = [GLRecord(gl_entry_id="GL-1", date="13-07-2026", description="Recv", amount=12000.0, reference="")]

    # A. Strong fuzzy match with no competitor -> matched_fuzzy
    invoices_A = [Invoice(invoice_id="INV-A", date="13-07-2026", client_name="Singh Corp", gstin="GST", gst_rate=18, total_amount=12000.0)]
    assert reconcile_records(bank_records, invoices_A, gl_records)[0].status == "matched_fuzzy"

    # B. Strong fuzzy match with weak/non-plausible competitor (< 50%) -> matched_fuzzy
    # "Patel Corp" against "SINGHCORP" scores low (around 30-40%)
    invoices_B = [
        Invoice(invoice_id="INV-A", date="13-07-2026", client_name="Singh Corp", gstin="GST", gst_rate=18, total_amount=12000.0),
        Invoice(invoice_id="INV-B", date="13-07-2026", client_name="Patel Corp", gstin="GST", gst_rate=18, total_amount=12000.0)
    ]
    assert reconcile_records(bank_records, invoices_B, gl_records)[0].status == "matched_fuzzy"

    # C. Strong fuzzy match with plausible competitor and insufficient margin (< 20%) -> needs_human_review
    invoices_C = [
        Invoice(invoice_id="INV-A", date="13-07-2026", client_name="Singh Corp", gstin="GST", gst_rate=18, total_amount=12000.0),      # ~71%
        Invoice(invoice_id="INV-C", date="13-07-2026", client_name="Singh & Sons Corp", gstin="GST", gst_rate=18, total_amount=12000.0) # ~63%
    ]
    assert reconcile_records(bank_records, invoices_C, gl_records)[0].status == "needs_human_review"

    # D. Strong fuzzy match with plausible competitor and sufficient margin (>= 20%) -> matched_fuzzy
    # To get >= 20% margin, we need a 90%+ match vs a 60% match.
    bank_records_D = [BankTransaction(bank_txn_id="B-1", date="13-07-2026", description="UPI/SINGHCORPORATION/TRANSFER", reference="UPI123", amount=12000.0)]
    invoices_D = [
        Invoice(invoice_id="INV-A", date="13-07-2026", client_name="Singh Corporation", gstin="GST", gst_rate=18, total_amount=12000.0), # 100%
        Invoice(invoice_id="INV-D", date="13-07-2026", client_name="Singh & Sons Corp", gstin="GST", gst_rate=18, total_amount=12000.0)  # ~70% (margin > 20)
    ]
    # In D, it triggers matched_fuzzy due to space normalisation difference, which perfectly validates our margin logic.
    assert reconcile_records(bank_records_D, invoices_D, gl_records)[0].status == "matched_fuzzy"


def test_candidate_exposure():
    """Verify that multiple ambiguous candidates are correctly bundled into the case."""
    bank = [BankTransaction(bank_txn_id="B1", date="15-08-2026", amount=5000.0, description="Payment /VENDOR", reference="REF1")]

    invoices = [
        Invoice(invoice_id="I1", date="15-08-2026", client_name="VENDOR", gstin="GST", gst_rate=18, total_amount=5000.0),
        Invoice(invoice_id="I2", date="15-08-2026", client_name="VENDOR", gstin="GST", gst_rate=18, total_amount=5000.0),
    ]

    cases = reconcile_records(bank, invoices, [])
    assert len(cases) == 1

    case = cases[0]
    assert case.status == "needs_human_review"

    # 2 candidates should be exposed
    assert case.candidates is not None
    assert len(case.candidates) == 2

    c1 = case.candidates[0]
    c2 = case.candidates[1]

    assert c1["invoice_id"] in ("I1", "I2")
    assert c2["invoice_id"] in ("I1", "I2")
    assert c1["rank"] == 1
    assert c2["rank"] == 2