from agents.models import StudentProfile
from services.chat.models import ChatProfileState
from services.chat.profile_state_service import (
    merge_profile_state,
    next_follow_up_question,
)


def test_merge_profile_state_updates_fields_and_computes_missing_slots():
    current = ChatProfileState()
    extracted = StudentProfile(
        total_score=27.0,
        preferred_majors=["computer_science"],
        location_preference="Ha Noi",
    )

    merged = merge_profile_state(current, extracted, "Em xet tuyen nam 2026")

    assert merged.admission_year == 2026
    assert merged.total_score == 27.0
    assert merged.preferred_majors == ["computer_science"]
    assert merged.location_preference == "Ha Noi"
    assert merged.missing_slots == []
    assert next_follow_up_question(merged) is None