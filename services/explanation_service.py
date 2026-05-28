from typing import Dict, List, Optional

from agents.models import CandidateProgram, PolicyDecision, RankedRecommendation, StudentProfile
from services.conflict.models import ResolutionOutcome
from services.conflict.source_labels import label_for_source


def _profile_summary(profile: StudentProfile) -> str:
    parts: List[str] = []
    if profile.total_score is not None:
        parts.append(f"diem={profile.total_score}")
    if profile.subject_combination:
        parts.append(f"to_hop={profile.subject_combination}")
    if profile.preferred_majors:
        parts.append("nganh_uu_tien=" + ", ".join(profile.preferred_majors[:3]))
    if profile.preferred_schools:
        parts.append("truong_uu_tien=" + ", ".join(profile.preferred_schools[:3]))
    if not parts:
        return "Chua thu thap du du lieu profile."
    return "Profile: " + " | ".join(parts)


def build_explanation(
    profile: StudentProfile,
    recommendations: List[RankedRecommendation],
    candidates: List[CandidateProgram],
    policy: Optional[PolicyDecision],
    resolution_outcomes: Optional[List[ResolutionOutcome]] = None,
) -> str:
    lines: List[str] = []
    lines.append(_profile_summary(profile))

    candidates_by_id: Dict[str, List[CandidateProgram]] = {}
    for candidate in candidates:
        candidates_by_id.setdefault(candidate.candidate_id, []).append(candidate)

    if recommendations:
        lines.append("Goi y chuong trinh phu hop:")
        displayed_recommendations: List[RankedRecommendation] = []
        displayed_ids = set()
        for recommendation in recommendations:
            if recommendation.candidate_id in displayed_ids:
                continue
            displayed_recommendations.append(recommendation)
            displayed_ids.add(recommendation.candidate_id)

        for idx, recommendation in enumerate(displayed_recommendations[:5], start=1):
            candidate_group = candidates_by_id.get(recommendation.candidate_id, [])
            candidate = candidate_group[0] if candidate_group else None
            if not candidate:
                continue
            lines.append(
                f"{idx}. {candidate.program_name} - {candidate.school_name} "
                f"[{recommendation.band}, score={recommendation.score}]"
            )
            if recommendation.reasons:
                lines.append("Ly do: " + "; ".join(recommendation.reasons[:3]))
            if recommendation.cautions:
                lines.append("Luu y: " + "; ".join(recommendation.cautions[:3]))
    else:
        lines.append("Chua co de xuat phu hop tu du lieu hien tai.")

    cited_sources: List[str] = []
    cited_ids = set()
    for recommendation in recommendations:
        if recommendation.candidate_id in cited_ids:
            continue
        cited_ids.add(recommendation.candidate_id)
        for candidate in candidates_by_id.get(recommendation.candidate_id, []):
            for evidence in candidate.evidence:
                if evidence.source_url:
                    cited_sources.append(evidence.source_url)

    if cited_sources:
        lines.append("Nguon tham chieu:")
        for idx, source in enumerate(list(dict.fromkeys(cited_sources))[:5], start=1):
            lines.append(f"- [{idx}] {source}")

    if policy and policy.warnings:
        lines.append("Canh bao:")
        for warning in policy.warnings:
            lines.append(f"- {warning}")

    if policy and policy.requires_follow_up:
        lines.append(
            "Thong tin can bo sung: diem, to hop mon, nganh/truong uu tien de nang do chinh xac."
        )

    lines.extend(_verification_lines(resolution_outcomes or []))

    return "\n".join(lines)


def _verification_lines(outcomes: List[ResolutionOutcome]) -> List[str]:
    if not outcomes:
        return []
    lines = ["## Xac minh du lieu"]
    for outcome in outcomes:
        if outcome.status == "resolved" and outcome.chosen_evidence:
            lines.append(
                f"- Han ngach nganh {outcome.program_name} tai {outcome.school_name}: "
                f"he thong tim thay nhieu nguon khac nhau. Su dung gia tri "
                f"{outcome.resolved_value} tu {label_for_source(outcome.chosen_evidence.source_url)} "
                f"vi {', '.join(outcome.decision_axes) or outcome.rationale}."
            )
        else:
            lines.append(
                f"- Han ngach nganh {outcome.program_name} tai {outcome.school_name}: "
                "thong tin mau thuan giua cac nguon. Ban nen xac minh truc tiep voi truong truoc khi dang ky."
            )
    return lines
