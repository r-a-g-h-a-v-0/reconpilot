"""Ground-truth evaluation for the deterministic reconciliation engine."""
from dataclasses import asdict, dataclass
from typing import Iterable, Mapping

from backend.matcher import MATCH_STATUSES
from backend.models import ReconciliationCase


@dataclass(frozen=True)
class EvaluationMetrics:
    total_cases: int
    automatic_matches: int
    correct_automatic_matches: int
    false_automatic_matches: int
    automatic_match_precision: float
    automatic_decision_accuracy: float
    coverage: float
    exception_rate: float
    review_rate: float
    false_match_ids: list[str]
    unresolved_case_ids: list[str]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _expected_pair_matches(case: ReconciliationCase, expected: Mapping[str, object]) -> bool:
    return case.invoice_id == expected["expected_invoice_id"] and case.gl_entry_id == expected["expected_gl_id"]


def evaluate_cases(cases: Iterable[ReconciliationCase], ground_truth: Mapping[str, Mapping[str, object]]) -> EvaluationMetrics:
    cases = list(cases)
    if {case.bank_txn_id for case in cases} != set(ground_truth):
        raise ValueError("Cases and ground truth must contain the same bank transaction IDs.")

    total_cases = len(cases)
    
    automatic_matches = 0
    correct_automatic_matches = 0
    false_automatic_matches = 0
    
    all_automatic_decisions = 0
    correct_automatic_decisions = 0
    
    unresolved_exceptions = 0
    human_review_cases = 0
    
    false_match_ids = []
    unresolved_case_ids = []

    for case in cases:
        expected = ground_truth[case.bank_txn_id]
        expected_status = expected["expected_status"]
        
        is_automatic_match = case.status in MATCH_STATUSES
        is_human_review = case.status == "needs_human_review"
        is_exception = not is_automatic_match and not is_human_review
        
        if is_human_review:
            human_review_cases += 1
            unresolved_case_ids.append(case.bank_txn_id)
        else:
            all_automatic_decisions += 1
            
            if is_automatic_match:
                automatic_matches += 1
                
                # Check if it's correct
                if case.status == expected_status and _expected_pair_matches(case, expected):
                    correct_automatic_matches += 1
                    correct_automatic_decisions += 1
                else:
                    false_automatic_matches += 1
                    false_match_ids.append(case.bank_txn_id)
                    
            elif is_exception:
                unresolved_exceptions += 1
                unresolved_case_ids.append(case.bank_txn_id)
                # Exception correctness
                if case.status == expected_status:
                    correct_automatic_decisions += 1

    return EvaluationMetrics(
        total_cases=total_cases,
        automatic_matches=automatic_matches,
        correct_automatic_matches=correct_automatic_matches,
        false_automatic_matches=false_automatic_matches,
        automatic_match_precision=correct_automatic_matches / automatic_matches if automatic_matches else 0.0,
        automatic_decision_accuracy=correct_automatic_decisions / all_automatic_decisions if all_automatic_decisions else 0.0,
        coverage=all_automatic_decisions / total_cases if total_cases else 0.0,
        exception_rate=unresolved_exceptions / total_cases if total_cases else 0.0,
        review_rate=human_review_cases / total_cases if total_cases else 0.0,
        false_match_ids=false_match_ids,
        unresolved_case_ids=unresolved_case_ids,
    )
