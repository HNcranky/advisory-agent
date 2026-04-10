from typing import List

from agents.models import CandidateProgram, PolicyDecision, StudentProfile


def evaluate_basic_policy(
    profile: StudentProfile, candidates: List[CandidateProgram]
) -> PolicyDecision:
    warnings = []
    blocked_claims = []

    if profile.missing_slots:
        warnings.append(
            "Missing profile inputs: " + ", ".join(sorted(set(profile.missing_slots)))
        )
    if not candidates:
        warnings.append("No matching programs found in current canonical records.")
    if profile.total_score is None:
        blocked_claims.append("do_not_claim_admission_probability")

    return PolicyDecision(
        allow_answer=True,
        blocked_claims=blocked_claims,
        warnings=warnings,
    )
