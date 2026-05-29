from agents.models import StudentProfile
from services.inference.models import InferenceError, InferenceRequest
from services.profile_service import build_profile, normalize_text


MAJOR_ID_GUIDE = [
    "cntt",
    "computer_science",
    "software_engineering",
    "information_technology_uet",
    "data_science",
    "artificial_intelligence_uet",
    "information_systems",
    "computer_engineering",
    "information_security",
    "cyber_security",
    "computer_networking",
    "computer_networks_data_communication",
    "robotics",
    "embedded_systems",
    "iot_engineering",
    "semiconductor_technology",
    "electronics_telecom",
    "business_administration",
    "economics",
    "accounting",
    "finance_banking",
    "marketing",
    "logistics",
    "law",
    "english_language",
]

INTEREST_MAJOR_MAP = {
    "lap trinh": [
        "cntt",
        "computer_science",
        "software_engineering",
        "information_technology_uet",
    ],
    "programming": [
        "cntt",
        "computer_science",
        "software_engineering",
        "information_technology_uet",
    ],
    "viet code": [
        "cntt",
        "computer_science",
        "software_engineering",
        "information_technology_uet",
    ],
    "lam app": ["software_engineering", "information_technology_uet"],
    "web": ["software_engineering", "computer_science"],
    "tri tue nhan tao": ["data_science", "artificial_intelligence_uet", "computer_science"],
    "artificial intelligence": ["data_science", "artificial_intelligence_uet", "computer_science"],
    "ai": ["data_science", "artificial_intelligence_uet", "computer_science"],
    "machine learning": ["data_science", "artificial_intelligence_uet"],
    "du lieu": ["data_science", "information_systems"],
    "data": ["data_science", "information_systems"],
    "bao mat": ["information_security", "cyber_security"],
    "an ninh mang": ["information_security", "cyber_security"],
    "cybersecurity": ["information_security", "cyber_security"],
    "robot": ["robotics", "computer_engineering"],
    "iot": ["iot_engineering", "embedded_systems"],
    "vi mach": ["semiconductor_technology", "electronics_telecom"],
}


PROFILE_SYSTEM_PROMPT = """
Extract a Vietnamese admission-advisory student profile.
Return JSON with these keys:
- total_score: number or null
- subject_combination: short code such as "A00", "A01", "D01" or null
- preferred_majors: list of canonical major ids, not only exact major names
- preferred_schools: list of named universities the student mentions
- location_preference: city or region the student wants to study in (e.g. "Ha Noi", "Mien Bac"), or null. This is distinct from preferred_schools.
- tuition_budget: free-form budget string the student mentions, or null
- constraints: list of other constraints the student mentions (family, scholarship, work obligations), or []
- missing_slots: list of the above keys the student has not yet provided
Use null for unknown scalar values and [] for unknown list values.

For preferred_majors, infer suitable related majors from interests, hobbies, or career goals even when the student does not know exact Vietnamese program names. Use these canonical ids when relevant:
{major_ids}

Examples:
- programming, coding, app/web/game development -> computer_science, software_engineering, information_technology_uet, cntt
- artificial intelligence, AI, machine learning -> data_science, artificial_intelligence_uet, computer_science
- data analysis or big data -> data_science, information_systems
- cybersecurity or network security -> information_security, cyber_security
- robotics, IoT, embedded systems -> robotics, iot_engineering, embedded_systems, computer_engineering
"""


def _normalize_major_ids(raw_majors):
    normalized: list[str] = []
    known_ids = set(MAJOR_ID_GUIDE)

    for raw_major in raw_majors or []:
        text = str(raw_major).strip()
        if not text:
            continue
        normalized_text = normalize_text(text)
        if text in known_ids:
            normalized.append(text)
        if normalized_text in known_ids:
            normalized.append(normalized_text)
        for interest, major_ids in INTEREST_MAJOR_MAP.items():
            if interest in normalized_text:
                normalized.extend(major_ids)

    return list(dict.fromkeys(normalized))


def _normalize_profile(profile: StudentProfile) -> StudentProfile:
    normalized_majors = _normalize_major_ids(profile.preferred_majors)
    if not normalized_majors:
        return profile

    missing_slots = [
        slot for slot in profile.missing_slots if slot != "preferred_majors"
    ]
    return profile.model_copy(
        update={
            "preferred_majors": normalized_majors,
            "missing_slots": missing_slots,
        }
    )


def build_profile_with_gateway(user_query: str, gateway) -> StudentProfile:
    if hasattr(gateway, "is_available") and not gateway.is_available():
        return build_profile(user_query)

    try:
        result = gateway.run(
            InferenceRequest(
                agent_name="profile_agent",
                task_type="profile_extraction",
                system_prompt=PROFILE_SYSTEM_PROMPT.format(
                    major_ids=", ".join(MAJOR_ID_GUIDE)
                ).strip(),
                user_prompt=user_query,
                output_mode="json",
                temperature=0.0,
            )
        )
    except InferenceError:
        return build_profile(user_query)
    return _normalize_profile(StudentProfile(**(result.parsed_data or {})))
