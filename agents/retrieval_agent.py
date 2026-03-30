# agents/retrieval_agent.py

from state import AgentState, ProgramInfo


def retrieval_agent(state: AgentState):

    major = state.student_profile.preferred_major

    database = [
        ProgramInfo(
            university="Hanoi University of Science and Technology",
            program="Computer Science",
            admission_method="exam_score",
            quota=300,
            subject_combination=["A00"]
        ),
        ProgramInfo(
            university="Vietnam National University Hanoi",
            program="Computer Science",
            admission_method="exam_score",
            quota=200,
            subject_combination=["A00"]
        )
    ]

    results = []

    for program in database:
        if program.program == major:
            results.append(program)

    state.retrieved_programs = results

    return state