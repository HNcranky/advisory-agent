from services.reasoning_service import index_candidates_by_id
from services.policy_service import evaluate_basic_policy
from state import AgentState


def advisory_agent(state: AgentState):
    profile = state.student_profile
    programs = state.retrieved_programs
    policy = evaluate_basic_policy(profile, programs)
    state.policy_decision = policy

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
            if recommendation.cautions:
                for caution in recommendation.cautions:
                    advice.append(f"Note: {caution}")
    else:
        for program in programs:
            if profile.total_score is not None and profile.total_score >= 26:
                advice.append(
                    f"You have a strong profile for {program.program_name} at {program.school_name}."
                )
            else:
                advice.append(
                    f"{program.program_name} at {program.school_name} is potentially competitive."
                )

    if not advice:
        advice.append("Chua tim thay nganh phu hop voi profile hien tai.")
    if policy.warnings:
        advice.extend([f"Warning: {warning}" for warning in policy.warnings])

    state.advisory = "\n".join(advice)
    state.final_answer = state.advisory
    state.citations = [ev for program in programs for ev in program.evidence]
    return state
