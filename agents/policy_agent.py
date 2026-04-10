from services.policy_service import evaluate_policy_guardrails
from state import AgentState


def policy_agent(state: AgentState):
    decision, filtered_recommendations = evaluate_policy_guardrails(
        user_query=state.user_query,
        profile=state.student_profile,
        candidates=state.retrieved_programs,
        recommendations=state.ranked_recommendations,
        conflicts=state.conflicts,
    )
    state.policy_decision = decision
    state.ranked_recommendations = filtered_recommendations
    return state
