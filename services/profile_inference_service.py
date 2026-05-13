from agents.models import StudentProfile
from services.inference.models import InferenceRequest
from services.profile_service import build_profile


PROFILE_SYSTEM_PROMPT = """
Extract a Vietnamese admission-advisory student profile.
Return JSON with these keys:
- total_score: number or null
- subject_combination: short code such as "A00", "A01", "D01" or null
- preferred_majors: list of major names the student is interested in
- preferred_schools: list of named universities the student mentions
- location_preference: city or region the student wants to study in (e.g. "Ha Noi", "Mien Bac"), or null. This is distinct from preferred_schools.
- tuition_budget: free-form budget string the student mentions, or null
- constraints: list of other constraints the student mentions (family, scholarship, work obligations), or []
- missing_slots: list of the above keys the student has not yet provided
Use null for unknown scalar values and [] for unknown list values.
"""


def build_profile_with_gateway(user_query: str, gateway) -> StudentProfile:
    if hasattr(gateway, "is_available") and not gateway.is_available():
        return build_profile(user_query)

    result = gateway.run(
        InferenceRequest(
            agent_name="profile_agent",
            task_type="profile_extraction",
            system_prompt=PROFILE_SYSTEM_PROMPT.strip(),
            user_prompt=user_query,
            output_mode="json",
            temperature=0.0,
        )
    )
    return StudentProfile(**(result.parsed_data or {}))
