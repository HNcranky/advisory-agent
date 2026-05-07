from agents.models import StudentProfile
from services.chat.models import ChatProfileState
from services.chat.profile_state_service import (
    merge_profile_state,
    next_follow_up_question,
)


def test_merge_profile_state_keeps_previous_values_and_orders_missing_slots():
    current = ChatProfileState(
        admission_year=2026,
        preferred_majors=["computer_science"],
    )
    extracted = StudentProfile(
        total_score=27.0,
        location_preference="Ha Noi",
    )

    merged = merge_profile_state(
        current,
        extracted,
        "Em duoc khoang 27 diem va muon hoc tai Ha Noi",
    )

    assert merged.admission_year == 2026
    assert merged.total_score == 27.0
    assert merged.preferred_majors == ["computer_science"]
    assert merged.location_preference == "Ha Noi"
    assert merged.missing_slots == []
    assert next_follow_up_question(merged) is None


def test_merge_profile_state_returns_first_missing_slot_prompt():
    merged = merge_profile_state(
        ChatProfileState(),
        StudentProfile(preferred_majors=["kinh_te"]),
        "Em muon hoc khoi kinh te",
    )

    assert merged.missing_slots == [
        "admission_year",
        "total_score",
        "location_preference",
    ]
    assert next_follow_up_question(merged) == "Ban dang xet tuyen cho nam nao?"