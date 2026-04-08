from langgraph.graph import StateGraph, START, END

from .advisory_state import AdvisoryState
from .agents import (
    profile_agent,
    retrieval_agent,
    reasoning_agent,
    policy_agent,
    explanation_agent,
)

# Initialize the graph with our state schema
workflow = StateGraph(AdvisoryState)

# Add nodes (The agents)
workflow.add_node("profile_agent", profile_agent)
workflow.add_node("retrieval_agent", retrieval_agent)
workflow.add_node("reasoning_agent", reasoning_agent)
workflow.add_node("policy_agent", policy_agent)
workflow.add_node("explanation_agent", explanation_agent)

# Define the edges (The flow of data)
workflow.add_edge(START, "profile_agent")
workflow.add_edge("profile_agent", "retrieval_agent")
workflow.add_edge("retrieval_agent", "reasoning_agent")
workflow.add_edge("reasoning_agent", "policy_agent")
workflow.add_edge("policy_agent", "explanation_agent")
workflow.add_edge("explanation_agent", END)

# Compile the graph
advisory_app = workflow.compile()