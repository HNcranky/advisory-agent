import json

from services.inference.models import InferenceRequest


RESOLUTION_SYSTEM_PROMPT = """
Resolve admission-evidence conflicts conservatively.
Return JSON with keys: resolution and uncertainty_reasons.
Prefer authoritative evidence and return uncertainty when evidence stays unresolved.
"""


def resolve_conflicts_with_gateway(conflicts, gateway):
    result = gateway.run(
        InferenceRequest(
            agent_name="resolution_agent",
            task_type="conflict_resolution",
            system_prompt=RESOLUTION_SYSTEM_PROMPT.strip(),
            user_prompt=json.dumps({"conflicts": conflicts}, ensure_ascii=False),
            output_mode="json",
            temperature=0.0,
        )
    )
    return result.parsed_data or {"resolution": "", "uncertainty_reasons": ["resolution_failed"]}