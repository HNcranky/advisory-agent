# main.py

from graph import graph
from state import AgentState

state = AgentState(
    user_query="Em được 27 điểm A00 muốn học công nghệ thông tin"
)

result = graph.invoke(state)

print(result["advisory"])