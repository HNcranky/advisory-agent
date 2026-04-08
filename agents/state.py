from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import BaseMessage

# Define the State for the Advisory Graph
class AdvisoryState(TypedDict):
    user_query: str
    user_profile: Dict[str, Any]  # e.g., {"score": 26, "major": "IT", "location": "Hanoi"}
    retrieved_context: List[str]  # Data from VectorDB/Knowledge Graph
    reasoning_analysis: str       # The core logic/matching result
    policy_check_status: str      # E.g., "Passed", "Flagged for missing disclaimer"
    final_response: str           # What the user actually sees