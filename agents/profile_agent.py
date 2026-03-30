# agents/profile_agent.py

from state import AgentState, StudentProfile


def profile_agent(state: AgentState):

    query = state.user_query.lower()

    profile = StudentProfile()

    if "toán" in query:
        profile.subjects = ["math"]

    if "27 điểm" in query:
        profile.score = 27

    if "công nghệ thông tin" in query:
        profile.preferred_major = "Computer Science"

    state.student_profile = profile

    return state