import json

from services.inference.models import InferenceRequest


POLICY_SYSTEM_PROMPT = """
Interpret only ambiguous policy text or conflicting evidence.
Return JSON with keys: warnings and requires_human_verification.
Never promise admission certainty.
"""


def interpret_policy_ambiguity(user_query: str, conflicts, gateway):
    payload = {"user_query": user_query, "conflicts": conflicts}
    result = gateway.run(
        InferenceRequest(
            agent_name="policy_agent",
            task_type="policy_ambiguity",
            system_prompt=POLICY_SYSTEM_PROMPT.strip(),
            user_prompt=json.dumps(payload, ensure_ascii=False),
            output_mode="json",
            temperature=0.0,
        )
    )
    return result.parsed_data or {"warnings": [], "requires_human_verification": False}