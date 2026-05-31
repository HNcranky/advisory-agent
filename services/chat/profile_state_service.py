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


def parse_pending_slot_answer(pending_slot: str, raw_message: str):
    """Best-effort parse of a bare reply to the slot we just asked about.

    Context-free extraction drops bare answers like "29" because there's no
    keyword tying the number to a score. When we already KNOW the pending slot
    is ``total_score``, a lone number in the valid range is unambiguous. Returns
    the parsed value, or ``None`` when the reply doesn't fit the slot.
    """
    if pending_slot == "total_score":
        match = re.search(r"\d{1,2}(?:[.,]\d+)?", raw_message)
        if match:
            value = float(match.group(0).replace(",", "."))
            if 0 <= value <= 40:
                return value
    return None

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

def missing_critical_slots(state: ChatProfileState) -> list:
    """Recompute the missing critical slots straight from the fields.

    Independent of `state.missing_slots`, which may be empty/stale on a freshly
    loaded profile.
    """
    return [slot for slot in CRITICAL_SLOT_ORDER if not getattr(state, slot)]


def next_follow_up_question(state: ChatProfileState):
    prompts = {
        "admission_year": "Bạn đang xét tuyển cho năm nào?",
        "total_score": "Tổng điểm hoặc mức điểm ước tính của bạn là bao nhiêu?",
        "preferred_majors": "Bạn quan tâm nhất đến ngành nào?",
        "location_preference": "Bạn muốn học ở khu vực hoặc thành phố nào?",
    }
    return prompts.get(state.missing_slots[0]) if state.missing_slots else None
