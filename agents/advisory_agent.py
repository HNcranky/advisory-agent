from services.reasoning_service import index_candidates_by_id
from state import AgentState


def advisory_agent(state: AgentState):
    programs = state.retrieved_programs
    policy = state.policy_decision

    advice = []
    by_id = index_candidates_by_id(programs)
    if state.ranked_recommendations:
        for recommendation in state.ranked_recommendations:
            candidate = by_id.get(recommendation.candidate_id)
            if candidate is None:
                continue
            advice.append(
                f"{candidate.program_name} at {candidate.school_name}: {recommendation.band} "
                f"(score={recommendation.score})."
            )
            for caution in recommendation.cautions:
                advice.append(f"Note: {caution}")
    else:
        for program in programs[:5]:
            advice.append(
                f"{program.program_name} at {program.school_name} can be considered after more profile details."
            )

    if not advice:
        advice.append("Chua tim thay nganh phu hop voi profile hien tai.")
    if policy and policy.warnings:
        advice.extend([f"Warning: {warning}" for warning in policy.warnings])
    if policy and policy.requires_follow_up:
        advice.append(
            "Follow-up: vui long bo sung diem, to hop mon, va nganh uu tien de tu van chinh xac hon."
        )

    state.advisory = "\n".join(advice)
    state.final_answer = state.advisory
    state.citations = [ev for program in programs for ev in program.evidence]
    return state
