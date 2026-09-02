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
        f"Match Accuracy: {metrics.match_accuracy:.2%}\n"
        f"Coverage: {metrics.coverage:.2%}\n"
        f"Exception Rate: {metrics.exception_rate:.2%}\n"
        f"Review Rate: {metrics.review_rate:.2%}\n"
        f"Correct Automatic Matches: {metrics.correct_automatic_matches}\n"
        f"False Automatic Matches: {metrics.false_automatic_matches}\n"
        f"Correct Exceptions: {metrics.correct_exceptions}\n"
        f"Missed Matches: {metrics.missed_matches}\n"
        f"Cases Sent to Human Review: {metrics.cases_sent_to_human_review}\n"
    )
    with open(report_file, "w") as f:
        f.write(report_content)

    # 4. Assert performance thresholds
    assert metrics.total_cases == 80, f"Expected 80 test cases, got {metrics.total_cases}"
    assert metrics.match_accuracy >= 0.90, f"Match accuracy ({metrics.match_accuracy:.2%}) below 90%"
    assert metrics.coverage >= 0.80, f"Coverage ({metrics.coverage:.2%}) below 80%"