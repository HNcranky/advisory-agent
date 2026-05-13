from agents.models import StudentProfile
from services.inference.models import InferenceRequest


PROFILE_SYSTEM_PROMPT = """
Extract a Vietnamese admission-advisory student profile.
Return JSON with keys: total_score, subject_combination, preferred_majors, preferred_schools, missing_slots.
Use null for unknown scalar values and [] for unknown list values.
"""


def build_profile_with_gateway(user_query: str, gateway) -> StudentProfile:
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