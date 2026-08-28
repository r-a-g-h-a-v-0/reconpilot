import csv
import json
import os
from pathlib import Path

def test_synthetic_dataset_validation():
    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data"
    gt_path = base_dir / "tests" / "ground_truth.json"

    assert gt_path.exists(), "Ground truth file missing"
    assert (data_dir / "bank.csv").exists(), "Bank CSV missing"
    assert (data_dir / "invoices.csv").exists(), "Invoices CSV missing"
    assert (data_dir / "gl.csv").exists(), "GL CSV missing"

    with open(gt_path, "r") as f:
        ground_truth = json.load(f)

    with open(data_dir / "bank.csv", "r") as f:
        bank_records = list(csv.DictReader(f))

    with open(data_dir / "invoices.csv", "r") as f:
        inv_records = list(csv.DictReader(f))

    with open(data_dir / "gl.csv", "r") as f:
        gl_records = list(csv.DictReader(f))

    # Assert exactly 76 bank transaction rows
    assert len(bank_records) == 76, f"Expected 76 bank records, found {len(bank_records)}"

    # Identify primary cases vs secondary duplicates
    # Since ground truth is keyed by bank_txn_id, and every row in bank has a bank_txn_id
    primary_cases = 0
    duplicate_cases = 0
    
    category_counts = {
        "matched_exact": 0,
        "matched_fuzzy": 0,
        "amount_mismatch_tds": 0,
        "amount_mismatch_bank_fee": 0,
        "duplicate_payment": 0,
        "missing_invoice": 0,
        "missing_gl_entry": 0
    }

    for b in bank_records:
        txn_id = b["bank_txn_id"]
        assert txn_id in ground_truth, f"Txn ID {txn_id} missing from ground truth"
        gt = ground_truth[txn_id]
        status = gt["expected_status"]
        category_counts[status] += 1
        
        if status == "duplicate_payment":
            duplicate_cases += 1
        else:
            primary_cases += 1

    # Assert exactly 72 primary unique reconciliation cases (76 - 4 duplicates = 72)
    assert primary_cases == 72, f"Expected 72 primary cases, found {primary_cases}"
    assert duplicate_cases == 4, f"Expected 4 duplicate cases, found {duplicate_cases}"

    # Verify specific category counts
    # The requirement says 45 straightforward (matched_exact is 45 + 4 UTR cases = 49 exact matches, plus 1 original for duplicate = 50 total exact matches in the test script)
    # Let's count them based on the script:
    # 45 straightforward (matched_exact)
    # 4 duplicate cases (they have an original matched_exact)
    # 4 UTR cases (matched_exact)
    # Total matched_exact should be 45 + 4 + 4 = 53
    # Wait, the requirements said:
    # - 45 straightforward
    # - 10 fuzzy vendor/date (matched_fuzzy)
    # - 5 TDS or bank-fee (amount_mismatch_tds/amount_mismatch_bank_fee)
    # - 4 duplicate-payment (duplicate_payment)
    # - 4 missing-document (missing_invoice/missing_gl_entry)
    # - 4 UPI/UTR (matched_exact, but specific scenario)
    
    # In data_gen.py:
    # Loop 1: 45 'matched_exact'
    # Loop 2: 10 'matched_fuzzy'
    # Loop 3: 5 (mix of 'amount_mismatch_tds' and 'amount_mismatch_bank_fee')
    # Loop 4: 4 original 'matched_exact' + 4 'duplicate_payment'
    # Loop 5: 4 (2 'missing_invoice', 2 'missing_gl_entry')
    # Loop 6: 4 'matched_exact' (UTR cases)
    
    assert category_counts["matched_fuzzy"] == 10
    assert category_counts["amount_mismatch_tds"] + category_counts["amount_mismatch_bank_fee"] == 5
    assert category_counts["duplicate_payment"] == 4
    assert category_counts["missing_invoice"] + category_counts["missing_gl_entry"] == 4
    assert category_counts["matched_exact"] == 45 + 4 + 4

    # Every expected counterpart ID exists when required
    inv_ids = {r["invoice_id"] for r in inv_records}
    gl_ids = {r["gl_entry_id"] for r in gl_records}
    
    for txn_id, gt in ground_truth.items():
        if gt["expected_invoice_id"]:
            assert gt["expected_invoice_id"] in inv_ids, f"Missing expected invoice {gt['expected_invoice_id']}"
        if gt["expected_gl_id"]:
            assert gt["expected_gl_id"] in gl_ids, f"Missing expected GL {gt['expected_gl_id']}"

    # Verify hidden GT is not in CSV files (just ensure it's not present as a column)
    assert "expected_status" not in bank_records[0]
    assert "expected_status" not in inv_records[0]
    assert "expected_status" not in gl_records[0]
    
    # Verify synthetic values - check if any real credentials leaked (basic check)
    with open(data_dir / "bank.csv", "r") as f:
        content = f.read()
        # Ensure no actual API keys or secrets are embedded
        assert "OPENAI_API_KEY" not in content
        assert "GEMINI_API_KEY" not in content

