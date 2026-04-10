from services.policy_service import evaluate_basic_policy
from state import AgentState


def advisory_agent(state: AgentState):
    profile = state.student_profile
    programs = state.retrieved_programs
    policy = evaluate_basic_policy(profile, programs)
    state.policy_decision = policy

    advice = []
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
