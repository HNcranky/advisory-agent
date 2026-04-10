# graph.py

from langgraph.graph import StateGraph

from state import AgentState

from agents.profile_agent import profile_agent
from agents.retrieval_agent import retrieval_agent
from agents.reasoning_agent import reasoning_agent
from agents.policy_agent import policy_agent
from agents.advisory_agent import advisory_agent


builder = StateGraph(AgentState)

builder.add_node("profile", profile_agent)
builder.add_node("retrieve", retrieval_agent)
builder.add_node("reason", reasoning_agent)
builder.add_node("policy", policy_agent)
builder.add_node("advisory", advisory_agent)


builder.set_entry_point("profile")

builder.add_edge("profile", "retrieve")
builder.add_edge("retrieve", "reason")
builder.add_edge("reason", "policy")
builder.add_edge("policy", "advisory")


graph = builder.compile()
