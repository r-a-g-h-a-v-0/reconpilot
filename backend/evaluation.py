"""Ground-truth evaluation for the deterministic reconciliation engine."""
from dataclasses import asdict, dataclass
from typing import Iterable, Mapping

from backend.matcher import MATCH_STATUSES
from backend.models import ReconciliationCase


@dataclass(frozen=True)
class EvaluationMetrics:
    total_cases: int
    match_accuracy: float
    coverage: float
    exception_rate: float
    review_rate: float
    correct_automatic_matches: int
    false_automatic_matches: int
    correct_exceptions: int
    missed_matches: int
    cases_sent_to_human_review: int

    def as_dict(self) -> dict[str, int | float]:
        return asdict(self)


def _expected_pair_matches(case: ReconciliationCase, expected: Mapping[str, object]) -> bool:
    return case.invoice_id == expected["expected_invoice_id"] and case.gl_entry_id == expected["expected_gl_id"]


def evaluate_cases(cases: Iterable[ReconciliationCase], ground_truth: Mapping[str, Mapping[str, object]]) -> EvaluationMetrics:
    """Measure outcomes against independently declared bank-transaction truth.

    Automatic matches must have the expected match status and both expected
    counterpart IDs. Exception correctness is status-based because a missing
    source record cannot have an ID on the reconciliation case.
    """
    cases = list(cases)
    if {case.bank_txn_id for case in cases} != set(ground_truth):
        raise ValueError("Cases and ground truth must contain the same bank transaction IDs.")

    correct_matches = false_matches = correct_exceptions = missed_matches = reviews = exceptions = 0
    automatic = 0
    for case in cases:
        expected = ground_truth[case.bank_txn_id]
        expected_status = expected["expected_status"]
        predicted_match = case.status in MATCH_STATUSES
        expected_match = expected_status in MATCH_STATUSES

        if case.status == "needs_human_review":
            reviews += 1
        else:
            automatic += 1

        if predicted_match:
            if case.status == expected_status and _expected_pair_matches(case, expected):
                correct_matches += 1
            else:
                false_matches += 1
        elif case.status != "needs_human_review":
            exceptions += 1
            if case.status == expected_status:
                correct_exceptions += 1

        if expected_match and not (predicted_match and case.status == expected_status and _expected_pair_matches(case, expected)):
            missed_matches += 1

    total = len(cases)
    predicted_matches = correct_matches + false_matches
    return EvaluationMetrics(
        total_cases=total,
        match_accuracy=correct_matches / predicted_matches if predicted_matches else 0.0,
        coverage=automatic / total if total else 0.0,
        exception_rate=exceptions / total if total else 0.0,
        review_rate=reviews / total if total else 0.0,
        correct_automatic_matches=correct_matches,
        false_automatic_matches=false_matches,
        correct_exceptions=correct_exceptions,
        missed_matches=missed_matches,
        cases_sent_to_human_review=reviews,
    )
