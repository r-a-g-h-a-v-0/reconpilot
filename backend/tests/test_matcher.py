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
        bank_records = [BankTransaction(**r) for r in csv.DictReader(f)]

    with open(data_dir / "invoices.csv", "r") as f:
        invoice_records = [Invoice(**r) for r in csv.DictReader(f)]

    with open(data_dir / "gl.csv", "r") as f:
        gl_records = [GLRecord(**r) for r in csv.DictReader(f)]

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
        f"Automatic Matches: {metrics.automatic_matches}\n"
        f"Correct Automatic Matches: {metrics.correct_automatic_matches}\n"
        f"False Automatic Matches: {metrics.false_automatic_matches}\n"
        f"Automatic Match Precision: {metrics.automatic_match_precision:.2%}\n"
        f"Automatic Decision Accuracy: {metrics.automatic_decision_accuracy:.2%}\n"
        f"Coverage: {metrics.coverage:.2%}\n"
        f"Exception Rate: {metrics.exception_rate:.2%}\n"
        f"Review Rate: {metrics.review_rate:.2%}\n"
        f"False Match IDs: {', '.join(metrics.false_match_ids) if metrics.false_match_ids else 'None'}\n"
        f"Unresolved Case IDs: {', '.join(metrics.unresolved_case_ids) if metrics.unresolved_case_ids else 'None'}\n"
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
    
    # Assert it matches the 71% one, not needs_human_review, because the 63% one is below threshold
    assert case.status == "matched_fuzzy"
    assert case.invoice_id == "INV-TEST-01"