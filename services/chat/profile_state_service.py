import re

from agents.models import StudentProfile
from services.chat.models import ChatProfileState

CRITICAL_SLOT_ORDER = [
    "admission_year",
    "total_score",
    "preferred_majors",
    "location_preference"
]

def _extract_admission_year(raw_message: str):
    match = re.search(r"\b20\d{2}\b", raw_message)
    return int(match.group(0)) if match else None

def merge_profile_state(current: ChatProfileState, extracted: StudentProfile, raw_message: str) -> ChatProfileState:
    merged = ChatProfileState(
        admission_year=_extract_admission_year(raw_message) or current.admission_year,
        total_score=extracted.total_score or current.total_score,
        subject_combination=extracted.subject_combination or current.subject_combination,
        preferred_majors=extracted.preferred_majors or current.preferred_majors,
        preferred_schools=extracted.preferred_schools or current.preferred_schools,
        location_preference=extracted.location_preference or current.location_preference,
        tuition_budget=extracted.tuition_budget or current.tuition_budget,
        constraints=extracted.constraints or current.constraints,
    )
    merged.missing_slots = [
        slot
        for slot in CRITICAL_SLOT_ORDER
        if not getattr(merged, slot)
    ]
    return merged

def next_follow_up_question(state: ChatProfileState):
    prompts = {
        "admission_year": "Ban dang xet tuyen cho nam nao?",
        "total_score": "Tong diem hoac muc diem uoc tinh cua ban la bao nhieu?",
        "preferred_majors": "Ban quan tam nhat den nganh nao?",
        "location_preference": "Ban muon hoc o khu vuv hay thanh pho nao?",
    }
    return prompts.get(state.missing_slots[0]) if state.missing_slots else None