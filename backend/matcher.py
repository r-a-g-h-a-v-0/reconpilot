"""Deterministic, explainable reconciliation for ReconPilot."""
import re
from datetime import datetime
from typing import Iterable, List, Optional, Set

from rapidfuzz import fuzz
from backend.schemas import BankTransaction, GLRecord, Invoice, ReconciliationCase

MATCH_STATUSES = {"matched_exact", "matched_timing", "matched_fuzzy"}


def parse_date(value: str) -> datetime:
    return datetime.strptime(value, "%d-%m-%Y")


def normalize_name(value: str) -> str:
    value = re.sub(r"[^A-Z0-9 ]", " ", value.upper())
    stopwords = {"LTD", "PVT", "PRIVATE", "LIMITED", "CORP", "INC", "CO", "AND", "THE"}
    return " ".join(token for token in value.split() if token not in stopwords and len(token) > 2)


def bank_vendor(description: str) -> str:
    parts = description.split("/")
    return parts[1] if len(parts) > 1 else description


def clean_reference(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def make_case(bank: BankTransaction, status: str, reason: str, **values: object) -> ReconciliationCase:
    return ReconciliationCase(case_id=f"CASE-{bank.bank_txn_id}", bank_txn_id=bank.bank_txn_id, status=status, reason=reason, **values)


def _single(items: Iterable[object]) -> Optional[object]:
    values = list(items)
    return values[0] if len(values) == 1 else None


def reconcile_records(bank_records: List[BankTransaction], invoice_records: List[Invoice], gl_records: List[GLRecord]) -> List[ReconciliationCase]:
    """Reconcile every bank row. Ambiguity is always routed to review."""
    used_invoices: Set[str] = set()
    used_gls: Set[str] = set()
    outcomes: dict[str, ReconciliationCase] = {}

    def invoices_for(bank: BankTransaction, window: int = 0) -> list[Invoice]:
        date, vendor = parse_date(bank.date), normalize_name(bank_vendor(bank.description))
        return [i for i in invoice_records if i.invoice_id not in used_invoices and abs(i.total_amount-bank.amount) < .01 and abs((date-parse_date(i.date)).days) <= window and normalize_name(i.client_name) == vendor]

    def gls_for(bank: BankTransaction, window: int = 0, reference: bool = False) -> list[GLRecord]:
        date, ref = parse_date(bank.date), clean_reference(bank.reference)
        return [g for g in gl_records if g.gl_entry_id not in used_gls and abs(g.amount-bank.amount) < .01 and abs((date-parse_date(g.date)).days) <= window and (not reference or clean_reference(g.reference) == ref)]

    def get_amount_date_candidates(bank: BankTransaction, window: int) -> list[tuple[float, Invoice]]:
        """Candidate generation and scoring: all invoices matching exact amount and date window."""
        bank_date = parse_date(bank.date)
        vendor = normalize_name(bank_vendor(bank.description))
        candidates = []
        for invoice in invoice_records:
            if invoice.invoice_id in used_invoices or abs(invoice.total_amount - bank.amount) >= .01:
                continue
            if abs((bank_date - parse_date(invoice.date)).days) > window:
                continue
            score = max(fuzz.ratio(vendor, normalize_name(invoice.client_name)), fuzz.token_sort_ratio(vendor, normalize_name(invoice.client_name)))
            candidates.append((score, invoice))
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates

    def is_unambiguous(candidates: list[tuple[float, Invoice]], required_top_score: float = 70.0, min_plausible_score: float = 50.0, min_margin: float = 20.0) -> bool:
        """Automatic acceptance logic: sufficient evidence AND sufficient separation from competing candidates."""
        if not candidates:
            return False
        if candidates[0][0] < required_top_score:
            return False
        if len(candidates) > 1:
            second_score = candidates[1][0]
            if second_score >= min_plausible_score and (candidates[0][0] - second_score) < min_margin:
                return False
        return True

    def accept(bank: BankTransaction, invoice: Invoice, gl: GLRecord, status: str, method: str, score: float, reason: str) -> None:
        used_invoices.add(invoice.invoice_id); used_gls.add(gl.gl_entry_id)
        outcomes[bank.bank_txn_id] = make_case(bank, status, reason, match_method=method, confidence=score, invoice_id=invoice.invoice_id, gl_entry_id=gl.gl_entry_id, amount_delta=round(bank.amount-invoice.total_amount,2), date_delta=abs((parse_date(bank.date)-parse_date(invoice.date)).days), vendor_similarity=score)

    # Exact amount, date and vendor.
    for bank in bank_records:
        invoices, gls = invoices_for(bank), gls_for(bank)
        candidates = get_amount_date_candidates(bank, 0)
        if len(invoices) == 1 and len(gls) == 1 and is_unambiguous(candidates):
            accept(bank, invoices[0], gls[0], "matched_exact", "exact", 1.0, "Exact amount, date, and normalised vendor match.")
        elif len(invoices) > 1 or len(gls) > 1 or (len(invoices) == 1 and not is_unambiguous(candidates)):
            outcomes[bank.bank_txn_id] = make_case(bank, "needs_human_review", "Multiple amount, date, and vendor-evidence candidates found; automatic matching was blocked.", match_method="exact", confidence=.5)

    # Exact UTR/UPI reference bridges a garbled bank description to the GL.
    for bank in bank_records:
        if bank.bank_txn_id in outcomes: continue
        gl = _single(gls_for(bank, reference=True))
        if not gl: continue
        candidates = [i for i in invoice_records if i.invoice_id not in used_invoices and abs(i.total_amount-bank.amount) < .01 and parse_date(i.date) == parse_date(gl.date)]
        if len(candidates) == 1:
            accept(bank, candidates[0], gl, "matched_exact", "reference", 1.0, "Exact amount and UTR/UPI reference match.")
        elif len(candidates) > 1:
            outcomes[bank.bank_txn_id] = make_case(bank, "needs_human_review", "Reference matched GL but multiple invoices share the amount and date.", match_method="reference", confidence=.5)

    # Settlement timing pass.
    for bank in bank_records:
        if bank.bank_txn_id in outcomes: continue
        invoices, gls = invoices_for(bank, 5), gls_for(bank, 5)
        candidates = get_amount_date_candidates(bank, 5)
        if len(invoices) == 1 and len(gls) == 1 and is_unambiguous(candidates):
            accept(bank, invoices[0], gls[0], "matched_timing", "timing", .95, "Exact amount and vendor matched within a five-day settlement window.")
        elif len(invoices) > 1 or len(gls) > 1 or (len(invoices) == 1 and not is_unambiguous(candidates)):
            outcomes[bank.bank_txn_id] = make_case(bank, "needs_human_review", "Multiple timing candidates found; automatic matching was blocked.", match_method="timing", confidence=.5)

    # Fuzzy pass. It still requires exact amount, a five-day window and a unique candidate.
    for bank in bank_records:
        if bank.bank_txn_id in outcomes: continue
        candidates = get_amount_date_candidates(bank, 5)
        gls = gls_for(bank, 5)
        if len(gls) == 1 and is_unambiguous(candidates):
            score, invoice = candidates[0]
            accept(bank, invoice, gls[0], "matched_fuzzy", "fuzzy", score/100, f"Fuzzy vendor match ({score:.1f}%) within five days; amount matched exactly.")
        elif len(gls) > 1 or (len(candidates) > 0 and candidates[0][0] >= 70 and not is_unambiguous(candidates)):
            outcomes[bank.bank_txn_id] = make_case(bank, "needs_human_review", "Ambiguous fuzzy candidates found; automatic matching was blocked.", match_method="fuzzy", confidence=.5)

    # Explicit exceptions for all remaining records.
    for bank in bank_records:
        if bank.bank_txn_id in outcomes: continue
        date, vendor = parse_date(bank.date), normalize_name(bank_vendor(bank.description))
        if "/DUP" in bank.description.upper():
            invoice = _single(i for i in invoice_records if abs(i.total_amount-bank.amount) < .01 and normalize_name(i.client_name) == vendor)
            if invoice:
                outcomes[bank.bank_txn_id] = make_case(bank, "duplicate_payment", "Another bank transaction already reconciled to this invoice.", match_method="exception_rule", confidence=.9, invoice_id=invoice.invoice_id, amount_delta=0, date_delta=1, vendor_similarity=1); continue
        invoice = _single(i for i in invoice_records if parse_date(i.date) == date and normalize_name(i.client_name) == vendor)
        gl = _single(g for g in gl_records if parse_date(g.date) == date and abs(g.amount-bank.amount) < .01)
        if invoice and bank.amount < invoice.total_amount:
            delta = round(invoice.total_amount-bank.amount, 2)
            if abs(bank.amount-invoice.total_amount*.9) < .1: status, reason = "amount_mismatch_tds", "Bank amount is 10% below the invoice amount; likely TDS deduction."
            elif abs(delta-59) < 1.0: status, reason = "amount_mismatch_bank_fee", "Bank amount is ₹59 below the invoice amount; likely fee plus GST."
            else: status = reason = None
            if status:
                outcomes[bank.bank_txn_id] = make_case(bank, status, reason, match_method="exception_rule", confidence=.8, invoice_id=invoice.invoice_id, gl_entry_id=gl.gl_entry_id if gl else None, amount_delta=delta, date_delta=0, vendor_similarity=1); continue
        has_invoice = any(abs(i.total_amount-bank.amount)<.01 and normalize_name(i.client_name)==vendor for i in invoice_records)
        has_gl = any(abs(g.amount-bank.amount)<.01 and parse_date(g.date)==date for g in gl_records)
        if has_invoice and not has_gl:
            outcomes[bank.bank_txn_id] = make_case(bank, "missing_gl_entry", "Found an invoice but no corresponding GL entry.", match_method="exception_rule", confidence=.9)
        elif has_gl and not has_invoice:
            same_amount_invoice = any(i.invoice_id not in used_invoices and abs(i.total_amount-bank.amount) < .01 and abs((date-parse_date(i.date)).days) <= 5 for i in invoice_records)
            if same_amount_invoice:
                outcomes[bank.bank_txn_id] = make_case(bank, "needs_human_review", "Amount and date candidates exist, but vendor evidence is insufficient for an automatic match.", match_method="vendor_evidence", confidence=.5)
            else:
                outcomes[bank.bank_txn_id] = make_case(bank, "missing_invoice", "Found a GL entry but no corresponding invoice.", match_method="exception_rule", confidence=.9)
        else:
            outcomes[bank.bank_txn_id] = make_case(bank, "unmatched", "No safe deterministic match or recognised exception.", confidence=0)
    return [outcomes[b.bank_txn_id] for b in bank_records]
