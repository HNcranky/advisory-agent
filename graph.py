from langgraph.graph import StateGraph

from state import AgentState

from agents.profile_agent import profile_agent
from agents.retrieval_agent import retrieval_agent
from agents.conflict_agent import conflict_agent
from agents.reasoning_agent import reasoning_agent
from agents.policy_agent import policy_agent
from agents.explanation_agent import explanation_agent


builder = StateGraph(AgentState)

builder.add_node("profile", profile_agent)
builder.add_node("retrieve", retrieval_agent)
builder.add_node("conflict", conflict_agent)
builder.add_node("reason", reasoning_agent)
builder.add_node("policy", policy_agent)
builder.add_node("explain", explanation_agent)


builder.set_entry_point("profile")

builder.add_edge("profile", "retrieve")
builder.add_edge("retrieve", "conflict")
builder.add_edge("conflict", "reason")
builder.add_edge("reason", "policy")
builder.add_edge("policy", "explain")


graph = builder.compile()
