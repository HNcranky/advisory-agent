from typing import Dict, List, Tuple

from agents.models import CandidateProgram, EligibilityCheck, RankedRecommendation, StudentProfile


def _major_matches(profile: StudentProfile, candidate: CandidateProgram) -> bool:
    if not profile.preferred_majors:
        return False
    lowered_name = candidate.program_name.lower()
    for major_id in profile.preferred_majors:
        if major_id == candidate.program_id:
            return True
        if major_id.replace("_", " ") in lowered_name:
            return True
    return False


def _school_matches(profile: StudentProfile, candidate: CandidateProgram) -> bool:
    if not profile.preferred_schools:
        return False
    return candidate.school_id in profile.preferred_schools


def _score_to_band(score: float, has_missing_critical: bool) -> str:
    if has_missing_critical:
        return "unknown"
    if score >= 0.75:
        return "safe"
    if score >= 0.50:
        return "match"
    return "reach"


def reason_candidates(
    profile: StudentProfile, candidates: List[CandidateProgram]
) -> Tuple[List[EligibilityCheck], List[RankedRecommendation]]:
    checks: List[EligibilityCheck] = []
    recommendations: List[RankedRecommendation] = []

    for candidate in candidates:
        score = 0.0
        reasons: List[str] = []
        risks: List[str] = []
        cautions: List[str] = []
        eligible = True

        if profile.subject_combination:
            if (
                not candidate.subject_combinations
                or profile.subject_combination in candidate.subject_combinations
            ):
                score += 0.40
                reasons.append("Subject combination appears compatible.")
            else:
                eligible = False
                risks.append("Subject combination does not match listed combinations.")
        else:
            eligible = None
            risks.append("Missing subject combination in profile.")

        if _major_matches(profile, candidate):
            score += 0.35
            reasons.append("Preferred major matches candidate program.")

        if _school_matches(profile, candidate):
            score += 0.15
            reasons.append("Preferred school matches candidate school.")

        if profile.total_score is not None:
            if profile.total_score >= 26:
                score += 0.10
                reasons.append("Profile score is in a strong range.")
            elif profile.total_score >= 24:
                score += 0.05
                reasons.append("Profile score is in a moderate range.")
            else:
                cautions.append("Profile score may be below highly competitive ranges.")
        else:
            cautions.append("Missing score; cannot estimate competitiveness reliably.")

        has_missing_critical = bool(profile.missing_slots)
        band = _score_to_band(score, has_missing_critical)
        summary = f"{candidate.program_name} at {candidate.school_name}: {band} fit."

        checks.append(
            EligibilityCheck(
                candidate_id=candidate.candidate_id,
                eligible=eligible,
                reasons=reasons,
                risks=risks,
                confidence=max(
                    [ev.confidence_score for ev in candidate.evidence if ev.confidence_score is not None]
                    or [None]
                ),
            )
        )
        recommendations.append(
            RankedRecommendation(
                candidate_id=candidate.candidate_id,
                band=band,
                score=round(score, 3),
                summary=summary,
                reasons=reasons,
                cautions=risks + cautions,
            )
        )

    order = {"safe": 0, "match": 1, "reach": 2, "unknown": 3}
    recommendations.sort(key=lambda rec: (order.get(rec.band, 99), -rec.score))
    return checks, recommendations


def index_candidates_by_id(candidates: List[CandidateProgram]) -> Dict[str, CandidateProgram]:
    return {candidate.candidate_id: candidate for candidate in candidates}
