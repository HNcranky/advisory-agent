from agents.profile_agent import profile_agent
from state import AgentState


def test_profile_agent_extracts_score_combo_and_major():
    state = AgentState(
        user_query="Em duoc 27 diem A00 muon hoc Cong nghe thong tin o HUST",
        admission_year=2026,
    )

    output = profile_agent(state)

    assert output.student_profile.total_score == 27
    assert output.student_profile.subject_combination == "A00"
    assert "computer_science" in output.student_profile.preferred_majors
    assert "hust" in output.student_profile.preferred_schools


def test_profile_agent_marks_missing_slots():
    state = AgentState(user_query="Em muon hoc nganh kinh te", admission_year=2026)

    output = profile_agent(state)

    assert "total_score" in output.student_profile.missing_slots
    assert "subject_combination" in output.student_profile.missing_slots

def main():
    test_profile_agent_extracts_score_combo_and_major()
    test_profile_agent_marks_missing_slots()
    print("All tests passed!")