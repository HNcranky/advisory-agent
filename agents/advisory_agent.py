from agents.explanation_agent import explanation_agent
from state import AgentState


def advisory_agent(state: AgentState):
    """Backward-compatible wrapper. Preferred node is explanation_agent."""
    return explanation_agent(state)
