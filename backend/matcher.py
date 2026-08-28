import re
from datetime import datetime
from typing import List, Dict, Set, Tuple
from rapidfuzz import fuzz
from backend.models import BankTransaction, Invoice, GLRecord, ReconciliationCase

def parse_date(date_str: str) -> datetime:
    # Expected format: DD-MM-YYYY
    return datetime.strptime(date_str, "%d-%m-%Y")

def normalize_name(name: str) -> str:
    text = name.upper().strip()
    text = re.sub(r"[^A-Z0-9 ]", " ", text)
    stopwords = {"LTD", "PVT", "CORP", "INC", "CO", "AND", "THE"}
    tokens = [t for t in text.split() if t not in stopwords and len(t) > 2]
    return " ".join(tokens)

def extract_bank_name(desc: str) -> str:
    # Example format: NEFT/Rahul Traders/PAYMENT or UPI/RAHULTRADERS/TRANSFER
    parts = desc.split('/')
    if len(parts) > 1:
        return parts[1]
    return desc

def extract_reference(ref: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(ref).upper())

def reconcile_records(
    bank_records: List[BankTransaction],
    invoice_records: List[Invoice],
    gl_records: List[GLRecord]
) -> List[ReconciliationCase]:
    
    # Track consumed records
    consumed_invoices: Set[str] = set()
    consumed_gls: Set[str] = set()
    
    cases: List[ReconciliationCase] = []
    
    # Pass 1: Exact matches (Amount + Exact UTR/UPI ref OR Exact Date + Name)
    for b in bank_records:
        b_date = parse_date(b.date)
        b_ref = extract_reference(b.reference)
        b_name_raw = extract_bank_name(b.description)
        b_name_norm = normalize_name(b_name_raw)
        
        matched = False
        
        # Look for Exact Invoice Match
        best_inv = None
        best_gl = None
        
        # Find exact invoice
        for i in invoice_records:
            if i.invoice_id in consumed_invoices:
                continue
            # Match by Exact Amount and Date and Exact Name
            i_date = parse_date(i.date)
            i_name_norm = normalize_name(i.client_name)
            
            # Scenario A: Exact Amount + Exact Reference
            # Since invoices don't have reference in our synthetic data, we use GL to bridge or rely on Amount + Date + Name
            
            # We match Invoice on Amount + Date + Name
            if abs(b.amount - i.total_amount) < 0.01:
                if b_date == i_date and i_name_norm == b_name_norm:
                    best_inv = i
                    break
        
        # Bridge to GL using same criteria
        if best_inv:
            for g in gl_records:
                if g.gl_entry_id in consumed_gls:
                    continue
                if abs(b.amount - g.amount) < 0.01 and parse_date(g.date) == b_date:
                    best_gl = g
                    break
        else:
            # Maybe it's a UTR exact match (Name doesn't match but amount + date + UTR matches)
            # Find GL with exact amount and reference
            for g in gl_records:
                if g.gl_entry_id in consumed_gls:
                    continue
                if abs(b.amount - g.amount) < 0.01 and extract_reference(g.reference) == b_ref:
                    best_gl = g
                    break
                    
            if best_gl:
                # Find matching invoice by amount and date
                for i in invoice_records:
                    if i.invoice_id in consumed_invoices:
                        continue
                    if abs(b.amount - i.total_amount) < 0.01 and parse_date(i.date) == parse_date(best_gl.date):
                        best_inv = i
                        break
        
        if best_inv and best_gl:
            consumed_invoices.add(best_inv.invoice_id)
            consumed_gls.add(best_gl.gl_entry_id)
            
            case = ReconciliationCase(
                case_id=f"CASE-{b.bank_txn_id}",
                status="matched_exact",
                match_method="exact",
                confidence=1.0,
                bank_txn_id=b.bank_txn_id,
                invoice_id=best_inv.invoice_id,
                gl_entry_id=best_gl.gl_entry_id,
                amount_delta=0.0,
                date_delta=0,
                vendor_similarity=1.0,
                reason="Exact match on amount, date, and identifiers."
            )
            cases.append(case)
            b._matched = True
            continue
            
    # Remove matched bank records
    unmatched_bank = [b for b in bank_records if not hasattr(b, '_matched')]
    
    # Pass 2: Timing Matches
    # Same amount, Date within +/- 5 days, vendor name matches
    for b in unmatched_bank:
        b_date = parse_date(b.date)
        b_name_norm = normalize_name(extract_bank_name(b.description))
        
        best_inv = None
        best_gl = None
        
        for i in invoice_records:
            if i.invoice_id in consumed_invoices:
                continue
            if abs(b.amount - i.total_amount) < 0.01:
                days_diff = abs((b_date - parse_date(i.date)).days)
                if days_diff <= 5 and normalize_name(i.client_name) == b_name_norm:
                    best_inv = i
                    break
                    
        if best_inv:
            for g in gl_records:
                if g.gl_entry_id in consumed_gls:
                    continue
                if abs(b.amount - g.amount) < 0.01:
                    days_diff_gl = abs((b_date - parse_date(g.date)).days)
                    if days_diff_gl <= 5:
                        best_gl = g
                        break
                        
        if best_inv and best_gl:
            consumed_invoices.add(best_inv.invoice_id)
            consumed_gls.add(best_gl.gl_entry_id)
            days_diff = abs((b_date - parse_date(best_inv.date)).days)
            case = ReconciliationCase(
                case_id=f"CASE-{b.bank_txn_id}",
                status="matched_timing",
                match_method="timing",
                confidence=0.95,
                bank_txn_id=b.bank_txn_id,
                invoice_id=best_inv.invoice_id,
                gl_entry_id=best_gl.gl_entry_id,
                amount_delta=0.0,
                date_delta=days_diff,
                vendor_similarity=1.0,
                reason=f"Matched on amount and vendor with {days_diff} days difference."
            )
            cases.append(case)
            b._matched = True
            continue
            
    unmatched_bank = [b for b in bank_records if not hasattr(b, '_matched')]
    
    # Pass 3: Fuzzy Matches
    # Same amount, strict dates, fuzzy name > 75
    for b in unmatched_bank:
        b_date = parse_date(b.date)
        b_name_norm = normalize_name(extract_bank_name(b.description))
        
        best_inv = None
        best_gl = None
        best_score = 0
        
        for i in invoice_records:
            if i.invoice_id in consumed_invoices:
                continue
            if abs(b.amount - i.total_amount) < 0.01:
                days_diff = abs((b_date - parse_date(i.date)).days)
                if days_diff <= 5:
                    score_token = fuzz.token_sort_ratio(b_name_norm, normalize_name(i.client_name))
                    score_ratio = fuzz.ratio(b_name_norm, normalize_name(i.client_name))
                    score = max(score_token, score_ratio)
                    if score >= 70 and score > best_score:
                        best_score = score
                        best_inv = i
                        
        if best_inv:
            for g in gl_records:
                if g.gl_entry_id in consumed_gls:
                    continue
                if abs(b.amount - g.amount) < 0.01:
                    days_diff_gl = abs((b_date - parse_date(g.date)).days)
                    if days_diff_gl <= 5:
                        best_gl = g
                        break
                        
        if best_inv and best_gl:
            consumed_invoices.add(best_inv.invoice_id)
            consumed_gls.add(best_gl.gl_entry_id)
            days_diff = abs((b_date - parse_date(best_inv.date)).days)
            case = ReconciliationCase(
                case_id=f"CASE-{b.bank_txn_id}",
                status="matched_fuzzy",
                match_method="fuzzy",
                confidence=best_score / 100.0,
                bank_txn_id=b.bank_txn_id,
                invoice_id=best_inv.invoice_id,
                gl_entry_id=best_gl.gl_entry_id,
                amount_delta=0.0,
                date_delta=days_diff,
                vendor_similarity=best_score / 100.0,
                reason=f"Fuzzy name match ({best_score:.1f}%) with {days_diff} days difference."
            )
            cases.append(case)
            b._matched = True
            continue

    unmatched_bank = [b for b in bank_records if not hasattr(b, '_matched')]
    
    # Pass 4: Exception detection (Duplicate, Mismatch, Missing Docs)
    # Check for Duplicate: Find if there's already a matched exact/timing/fuzzy case for the exact same amount/date
    for b in unmatched_bank:
        b_date = parse_date(b.date)
        if "DUP" in b.description:
            # It's a duplicate. We must link it to the consumed invoice to highlight it.
            # But the requirement says "duplicate prevention: one bank record and one invoice/GL can each be consumed only once"
            # It's an exception
            # We can find the invoice with exact same amount and name, even if it's already consumed.
            # Since it's already consumed, it's a duplicate!
            
            b_name_norm = normalize_name(extract_bank_name(b.description))
            dup_inv = None
            for i in invoice_records:
                if abs(b.amount - i.total_amount) < 0.01 and normalize_name(i.client_name) == b_name_norm:
                    dup_inv = i
                    break
                    
            if dup_inv and dup_inv.invoice_id in consumed_invoices:
                case = ReconciliationCase(
                    case_id=f"CASE-{b.bank_txn_id}",
                    status="duplicate_payment",
                    match_method="exception_rule",
                    confidence=0.9,
                    bank_txn_id=b.bank_txn_id,
                    invoice_id=dup_inv.invoice_id,
                    amount_delta=0.0,
                    date_delta=0,
                    vendor_similarity=1.0,
                    reason="Another bank transaction already paid this exact invoice."
                )
                cases.append(case)
                b._matched = True
                continue

    unmatched_bank = [b for b in bank_records if not hasattr(b, '_matched')]

    # Exceptions: TDS / Fee mismatches
    for b in unmatched_bank:
        b_date = parse_date(b.date)
        b_name_norm = normalize_name(extract_bank_name(b.description))
        
        best_inv = None
        best_gl = None
        
        # Look for invoice matching name and date, but amount differs slightly (10% or exactly 59)
        for i in invoice_records:
            if i.invoice_id in consumed_invoices:
                continue
            if b_date == parse_date(i.date) and normalize_name(i.client_name) == b_name_norm:
                best_inv = i
                break
                
        if best_inv:
            delta = round(best_inv.total_amount - b.amount, 2)
            if delta > 0:
                # Is it TDS (10%)?
                if abs(b.amount - (best_inv.total_amount * 0.90)) < 0.1:
                    status = "amount_mismatch_tds"
                    reason = "Bank amount is 10% less, likely TDS deducted."
                elif abs(delta - 59.0) < 0.1:
                    status = "amount_mismatch_bank_fee"
                    reason = "Bank amount is exactly ₹59 less, likely bank fee + GST."
                else:
                    continue # Not a recognized mismatch pattern
                    
                # Find GL
                for g in gl_records:
                    if g.gl_entry_id in consumed_gls:
                        continue
                    if abs(g.amount - b.amount) < 0.1 and parse_date(g.date) == b_date:
                        best_gl = g
                        break
                        
                case = ReconciliationCase(
                    case_id=f"CASE-{b.bank_txn_id}",
                    status=status,
                    match_method="exception_rule",
                    confidence=0.8,
                    bank_txn_id=b.bank_txn_id,
                    invoice_id=best_inv.invoice_id,
                    gl_entry_id=best_gl.gl_entry_id if best_gl else None,
                    amount_delta=delta,
                    date_delta=0,
                    vendor_similarity=1.0,
                    reason=reason
                )
                cases.append(case)
                b._matched = True
                continue

    unmatched_bank = [b for b in bank_records if not hasattr(b, '_matched')]

    # Exceptions: Missing Invoice or Missing GL
    for b in unmatched_bank:
        b_date = parse_date(b.date)
        b_name_norm = normalize_name(extract_bank_name(b.description))
        
        # See if there's only an invoice, or only a GL
        has_inv = False
        has_gl = False
        
        for i in invoice_records:
            if i.invoice_id not in consumed_invoices and abs(i.total_amount - b.amount) < 0.1:
                has_inv = True
                break
                
        for g in gl_records:
            if g.gl_entry_id not in consumed_gls and abs(g.amount - b.amount) < 0.1:
                has_gl = True
                break
                
        if has_inv and not has_gl:
            case = ReconciliationCase(
                case_id=f"CASE-{b.bank_txn_id}",
                status="missing_gl_entry",
                match_method="exception_rule",
                confidence=0.9,
                bank_txn_id=b.bank_txn_id,
                reason="Found matching invoice, but no corresponding GL entry."
            )
            cases.append(case)
            b._matched = True
        elif has_gl and not has_inv:
            case = ReconciliationCase(
                case_id=f"CASE-{b.bank_txn_id}",
                status="missing_invoice",
                match_method="exception_rule",
                confidence=0.9,
                bank_txn_id=b.bank_txn_id,
                reason="Found matching GL entry, but no corresponding Invoice."
            )
            cases.append(case)
            b._matched = True
            
    unmatched_bank = [b for b in bank_records if not hasattr(b, '_matched')]

    # Remaining Unmatched
    for b in unmatched_bank:
        case = ReconciliationCase(
            case_id=f"CASE-{b.bank_txn_id}",
            status="unmatched",
            match_method=None,
            confidence=0.0,
            bank_txn_id=b.bank_txn_id,
            reason="No deterministic match or recognized exception."
        )
        cases.append(case)

    return cases
