from typing import Dict, List, Optional

from agents.models import CandidateProgram, PolicyDecision, RankedRecommendation, StudentProfile


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
) -> str:
    lines: List[str] = []
    lines.append(_profile_summary(profile))

    candidate_map: Dict[str, CandidateProgram] = {
        candidate.candidate_id: candidate for candidate in candidates
    }

    if recommendations:
        lines.append("Goi y chuong trinh phu hop:")
        for idx, recommendation in enumerate(recommendations[:5], start=1):
            candidate = candidate_map.get(recommendation.candidate_id)
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
    for recommendation in recommendations:
        candidate = candidate_map.get(recommendation.candidate_id)
        if not candidate:
            continue
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

    return "\n".join(lines)
