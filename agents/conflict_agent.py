# agents/conflict_agent.py

from state import AgentState


def conflict_agent(state: AgentState):

    conflicts = []

    seen = {}

    for program in state.retrieved_programs:

        key = (program.university, program.program)

        if key not in seen:
            seen[key] = program.quota
        else:
            if seen[key] != program.quota:
                conflicts.append(
                    f"Quota conflict for {program.program} at {program.university}"
                )

    state.conflicts = conflicts

    return state