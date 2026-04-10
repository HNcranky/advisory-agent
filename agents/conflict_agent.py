from services.retrieval_service import detect_conflicts
from state import AgentState


def conflict_agent(state: AgentState):
    detected = detect_conflicts(state.retrieved_programs)
    state.conflicts = list(dict.fromkeys(state.conflicts + detected))
    return state
