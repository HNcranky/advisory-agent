# agents/advisory_agent.py

from state import AgentState


def advisory_agent(state: AgentState):

    profile = state.student_profile
    programs = state.retrieved_programs

    advice = []

    for program in programs:

        if profile.score and profile.score >= 26:
            advice.append(
                f"You have a strong chance for {program.program} at {program.university}"
            )
        else:
            advice.append(
                f"{program.program} at {program.university} might be competitive"
            )

    state.advisory = "\n".join(advice)

    return state