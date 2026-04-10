from services.profile_service import build_profile
from state import AgentState


def profile_agent(state: AgentState):
    state.student_profile = build_profile(state.user_query)
    state.retrieval_missing_data = list(state.student_profile.missing_slots)
    return state
