# graph.py

from langgraph.graph import StateGraph

from state import AgentState

from agents.profile_agent import profile_agent
from agents.retrieval_agent import retrieval_agent
from agents.conflict_agent import conflict_agent
from agents.advisory_agent import advisory_agent


builder = StateGraph(AgentState)

builder.add_node("profile", profile_agent)
builder.add_node("retrieve", retrieval_agent)
builder.add_node("conflict_check", conflict_agent)
builder.add_node("advisory", advisory_agent)


builder.set_entry_point("profile")

builder.add_edge("profile", "retrieve")
builder.add_edge("retrieve", "conflict_check")
builder.add_edge("conflict_check", "advisory")


graph = builder.compile()