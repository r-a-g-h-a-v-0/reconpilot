import csv
import json
import random
import re
import uuid
from datetime import datetime, timedelta

def format_date(dt):
    return dt.strftime("%d-%m-%Y")

def random_date(start_date=datetime(2026, 7, 1), max_days=30):
    return start_date + timedelta(days=random.randint(0, max_days))

INDIAN_NAMES = ["Rahul Traders", "Sharma Enterprises", "Gupta Logistics", "Mehta & Co", "Verma Solutions", "Singh Corp", "Kapur Industries", "Reddy Tech"]
GST_RATES = [0, 5, 12, 18, 28]

def generate_cases():
    random.seed(42)  # For deterministic output
    
    bank_records = []
    invoice_records = []
    gl_records = []
    ground_truth = {}
    
    bank_idx = 1
    inv_idx = 1
    gl_idx = 1
    
    def add_case(b_date, b_desc, b_ref, b_amt, i_date, i_name, i_amt, g_date, g_desc, g_amt, expected_status, has_inv=True, has_gl=True):
        nonlocal bank_idx, inv_idx, gl_idx
        
        b_id = f"B-2026-{bank_idx:03d}"
        i_id = f"INV-2026-{inv_idx:03d}" if has_inv else None
        g_id = f"GL-2026-{gl_idx:03d}" if has_gl else None
        
        bank_records.append({
            "bank_txn_id": b_id,
            "date": format_date(b_date),
            "description": b_desc,
            "reference": b_ref,
            "amount": round(b_amt, 2)
        })
        
        if has_inv:
            invoice_records.append({
                "invoice_id": i_id,
                "date": format_date(i_date),
                "client_name": i_name,
                "gstin": f"27AAAAA{random.randint(1000,9999)}A1Z5",
                "gst_rate": random.choice(GST_RATES),
                "total_amount": round(i_amt, 2)
            })
            
        if has_gl:
            gl_records.append({
                "gl_entry_id": g_id,
                "date": format_date(g_date),
                "description": g_desc,
                "amount": round(g_amt, 2),
                "reference": b_ref if expected_status in ['matched_exact', 'matched_timing'] else ""
            })
            
        ground_truth[b_id] = {
            "expected_status": expected_status,
            "expected_invoice_id": i_id,
            "expected_gl_id": g_id
        }
        
        bank_idx += 1
        if has_inv: inv_idx += 1
        if has_gl: gl_idx += 1
        return b_id, i_id, g_id

    # 1. 45 straightforward matches (Exact match)
    for _ in range(45):
        dt = random_date()
        amt = round(random.uniform(1000, 50000), 2)
        name = random.choice(INDIAN_NAMES)
        b_ref = f"UTR{random.randint(10000000, 99999999)}"
        b_desc = f"NEFT/{name}/PAYMENT"
        add_case(dt, b_desc, b_ref, amt, dt, name, amt, dt, f"Received from {name}", amt, "matched_exact")

    # 2. 10 fuzzy vendor/date matches
    for _ in range(10):
        dt = random_date()
        b_dt = dt + timedelta(days=random.randint(1, 4))
        amt = round(random.uniform(5000, 20000), 2)
        name = random.choice(INDIAN_NAMES)
        b_ref = f"UPI{random.randint(10000000, 99999999)}"
        # Mangle name slightly
        # Remove separators as they appear in compact UPI descriptions.  This
        # deliberately prevents punctuation-only normalisation from turning a
        # fuzzy case (for example, "MEHTA&CO") into an exact vendor match.
        mangled_name = re.sub(r"[^A-Za-z0-9]", "", name).upper()
        b_desc = f"UPI/{mangled_name}/TRANSFER"
        add_case(b_dt, b_desc, b_ref, amt, dt, name, amt, b_dt, f"Payment {name}", amt, "matched_fuzzy")

    # 3. 5 TDS or bank fee amount mismatches (Bank amount < Invoice amount)
    for idx in range(5):
        dt = random_date()
        inv_amt = round(random.uniform(10000, 30000), 2)
        # Ensure a mix: first 4 are TDS, last one is bank fee
        if idx < 4:
            b_amt = round(inv_amt * 0.90, 2)
            expected_status = "amount_mismatch_tds"
        else:
            b_amt = round(inv_amt - 59.0, 2)  # ₹59 fee
            expected_status = "amount_mismatch_bank_fee"
        name = random.choice(INDIAN_NAMES)
        b_ref = f"IMPS{random.randint(10000000, 99999999)}"
        add_case(dt, f"IMPS/{name}", b_ref, b_amt, dt, name, inv_amt, dt, f"Recv {name}", b_amt, expected_status)

    # 4. 4 duplicate payment cases (Bank has 2 identical payments for 1 invoice)
    for _ in range(4):
        dt = random_date()
        amt = round(random.uniform(2000, 8000), 2)
        name = random.choice(INDIAN_NAMES)
        b_ref1 = f"RTGS{random.randint(10000000, 99999999)}"
        b_ref2 = f"RTGS{random.randint(10000000, 99999999)}"
        
        # Add the first one, which will be matched
        b_id1, i_id, g_id = add_case(dt, f"RTGS/{name}", b_ref1, amt, dt, name, amt, dt, f"Recv {name}", amt, "matched_exact")
        
        # Add the second one, which is duplicate (same invoice, same amount, but new bank txn)
        b_id2 = f"B-2026-{bank_idx:03d}"
        bank_records.append({
            "bank_txn_id": b_id2,
            "date": format_date(dt + timedelta(days=1)),
            "description": f"RTGS/{name}/DUP",
            "reference": b_ref2,
            "amount": amt
        })
        ground_truth[b_id2] = {
            "expected_status": "duplicate_payment",
            "expected_invoice_id": i_id,  # Points to the same invoice
            "expected_gl_id": None
        }
        bank_idx += 1

    # 5. 4 missing invoice or missing ledger-entry cases
    for i in range(4):
        dt = random_date()
        amt = round(random.uniform(1000, 5000), 2)
        name = random.choice(INDIAN_NAMES)
        b_ref = f"UPI{random.randint(10000000, 99999999)}"
        
        if i % 2 == 0:
            # Missing invoice
            add_case(dt, f"UPI/{name}/NO-INV", b_ref, amt, dt, name, amt, dt, f"Recv {name}", amt, "missing_invoice", has_inv=False)
        else:
            # Missing GL
            add_case(dt, f"UPI/{name}/NO-GL", b_ref, amt, dt, name, amt, dt, f"Recv {name}", amt, "missing_gl_entry", has_gl=False)

    # 6. 4 UPI/UTR reference cases (Name is completely garbled but ref matches)
    for _ in range(4):
        dt = random_date()
        amt = round(random.uniform(5000, 15000), 2)
        name = random.choice(INDIAN_NAMES)
        # Invoice has one name, Bank has random individual's name but UTR matches
        b_ref = f"UTR{random.randint(10000000, 99999999)}"
        b_desc = f"NEFT/RAMESH KUMAR/PAYMENT"
        add_case(dt, b_desc, b_ref, amt, dt, name, amt, dt, f"Recv {name}", amt, "matched_exact") # Exact match on UTR and amount

    # 7. 4 Adversarial false-positive tests
    # Case A: Two different vendors have similar names -> needs_human_review
    dt = random_date()
    amt = 12000.00
    b_ref = f"UPI{random.randint(10000000, 99999999)}"
    b_id, i_id, g_id = add_case(dt, "UPI/SINGHCORP/TRANSFER", b_ref, amt, dt, "Singh Corp", amt, dt, "Recv", amt, "needs_human_review")
    # Add competing invoice
    invoice_records.append({
        "invoice_id": f"INV-2026-ADV1",
        "date": format_date(dt),
        "client_name": "Singh & Sons Corp",
        "gstin": "27AAAAA0000A1Z5",
        "gst_rate": 18,
        "total_amount": amt
    })
    
    # Case B: Same amount and close date belong to different vendors -> needs_human_review
    dt = random_date()
    amt = 8500.00
    b_ref = f"IMPS{random.randint(10000000, 99999999)}"
    b_id, i_id, g_id = add_case(dt, "IMPS/UNKNOWN/TRANSFER", b_ref, amt, dt, "Mehta & Co", amt, dt, "Recv", amt, "needs_human_review")
    invoice_records.append({
        "invoice_id": f"INV-2026-ADV2",
        "date": format_date(dt + timedelta(days=1)),
        "client_name": "Kapur Industries",
        "gstin": "27AAAAA0000A1Z5",
        "gst_rate": 18,
        "total_amount": amt
    })
    
    # Case C: Similar vendor name has a materially different amount -> unmatched
    dt = random_date()
    amt = 5000.00
    b_ref = f"UPI{random.randint(10000000, 99999999)}"
    b_id, i_id, g_id = add_case(dt, "UPI/GUPTALOGISTICS/TRANSFER", b_ref, amt, dt, "Gupta Logistics", 9000.00, dt, "Recv", 9000.00, "unmatched")
    
    # Case D: Duplicate invoice competes with the correct invoice -> needs_human_review
    dt = random_date()
    amt = 7000.00
    b_ref = f"RTGS{random.randint(10000000, 99999999)}"
    b_id, i_id, g_id = add_case(dt, "RTGS/REDDYTECH/TRANSFER", b_ref, amt, dt, "Reddy Tech", amt, dt, "Recv", amt, "needs_human_review")
    invoice_records.append({
        "invoice_id": f"INV-2026-ADV4",
        "date": format_date(dt),
        "client_name": "Reddy Tech",
        "gstin": "27AAAAA0000A1Z5",
        "gst_rate": 18,
        "total_amount": amt
    })

    # Total bank cases: 45 + 10 + 5 + 8 (four duplicate pairs) + 4 + 4 + 4 = 80
    
    with open('backend/data/bank.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["bank_txn_id", "date", "description", "reference", "amount"])
        writer.writeheader()
        writer.writerows(bank_records)
        
    with open('backend/data/invoices.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["invoice_id", "date", "client_name", "gstin", "gst_rate", "total_amount"])
        writer.writeheader()
        writer.writerows(invoice_records)
        
    with open('backend/data/gl.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["gl_entry_id", "date", "description", "amount", "reference"])
        writer.writeheader()
        writer.writerows(gl_records)
        
    with open('backend/tests/ground_truth.json', 'w') as f:
        json.dump(ground_truth, f, indent=2)

    print(f"Generated 80 bank cases successfully.")
    print(f"Bank records: {len(bank_records)}")
    print(f"Invoice records: {len(invoice_records)}")
    print(f"GL records: {len(gl_records)}")

if __name__ == "__main__":
    generate_cases()
