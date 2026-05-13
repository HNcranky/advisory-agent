from agents.explanation_agent import explanation_agent
from agents.models import (
    CandidateProgram,
    Evidence,
    PolicyDecision,
    RankedRecommendation,
    StudentProfile,
)
from state import AgentState


def test_explanation_agent_builds_final_answer_with_sources():
    state = AgentState(user_query="Tu van")
    state.student_profile = StudentProfile(
        total_score=27,
        subject_combination="A00",
        preferred_majors=["computer_science"],
    )
    state.retrieved_programs = [
        CandidateProgram(
            candidate_id="hust:1",
            school_id="hust",
            school_name="HUST",
            admission_year=2026,
            program_id="computer_science",
            program_name="Khoa hoc May tinh",
            admission_method="thpt_score",
            evidence=[
                Evidence(
                    source_url="https://example.com/hust",
                    school_name="HUST",
                    admission_year=2026,
                    field_name="record",
                )
            ],
        )
    ]
    state.ranked_recommendations = [
        RankedRecommendation(
            candidate_id="hust:1",
            band="safe",
            score=0.91,
            summary="fit",
            reasons=["Preferred major matches candidate program."],
            cautions=["Check official cutoff updates."],
        )
    ]
    state.policy_decision = PolicyDecision(
        warnings=["Conflicting records detected; verify official source before applying."],
        requires_follow_up=False,
    )

    output = explanation_agent(state)

    assert output.final_answer is not None
    assert "Goi y chuong trinh phu hop:" in output.final_answer
    assert "Nguon tham chieu:" in output.final_answer
    assert "https://example.com/hust" in output.final_answer
    assert "Canh bao:" in output.final_answer


def test_explanation_agent_adds_follow_up_prompt():
    state = AgentState(user_query="Tu van")
    state.student_profile = StudentProfile(missing_slots=["total_score", "subject_combination"])
    state.policy_decision = PolicyDecision(requires_follow_up=True)

    output = explanation_agent(state)

    assert "Thong tin can bo sung:" in output.final_answer
