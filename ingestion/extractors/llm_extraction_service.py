import json

from services.inference.models import InferenceRequest


EXTRACTION_SYSTEM_PROMPT = """
Extract Vietnamese admission facts from noisy source text.
Return JSON with key facts. Each fact must include program_name, admission_method, and subject_combinations.
"""


def extract_admission_facts_with_gateway(source_text: str, gateway):
    result = gateway.run(
        InferenceRequest(
            agent_name="extraction_agent",
            task_type="document_extraction",
            system_prompt=EXTRACTION_SYSTEM_PROMPT.strip(),
            user_prompt=json.dumps({"source_text": source_text}, ensure_ascii=False),
            output_mode="json",
            temperature=0.0,
        )
    )
    return (result.parsed_data or {}).get("facts", [])