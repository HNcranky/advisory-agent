from agents.reasoning_agent import reasoning_agent
from agents.models import CandidateProgram, Evidence, StudentProfile
from state import AgentState


def test_reasoning_agent_ranks_candidates():
    state = AgentState(user_query="test")
    state.student_profile = StudentProfile(
        total_score=27,
        subject_combination="A00",
        preferred_majors=["computer_science"],
        preferred_schools=["hust"],
    )
    state.retrieved_programs = [
        CandidateProgram(
            candidate_id="hust:2026:computer_science:thpt_score",
            school_id="hust",
            school_name="Hanoi University of Science and Technology",
            admission_year=2026,
            program_id="computer_science",
            program_name="Khoa hoc May tinh",
            admission_method="thpt_score",
            subject_combinations=["A00", "A01"],
            evidence=[
                Evidence(
                    source_url="https://example.com",
                    school_name="HUST",
                    admission_year=2026,
                    field_name="record",
                    confidence_score=0.9,
                )
            ],
        )
    ]

    output = reasoning_agent(state)

    assert len(output.eligibility_checks) == 1
    assert len(output.ranked_recommendations) == 1
    assert output.ranked_recommendations[0].band in ("safe", "match")
    assert output.ranked_recommendations[0].score > 0


def test_reasoning_agent_marks_unknown_when_missing_critical():
    state = AgentState(user_query="test")
    state.student_profile = StudentProfile(
        preferred_majors=["computer_science"],
        missing_slots=["total_score", "subject_combination"],
    )
    state.retrieved_programs = [
        CandidateProgram(
            candidate_id="hust:2026:computer_science:thpt_score",
            school_id="hust",
            school_name="HUST",
            admission_year=2026,
            program_id="computer_science",
            program_name="Khoa hoc May tinh",
            admission_method="thpt_score",
            subject_combinations=["A00"],
        )
    ]

    output = reasoning_agent(state)

    assert output.ranked_recommendations[0].band == "unknown"
