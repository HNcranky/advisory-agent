from services.conflict_resolution_service import resolve_conflicts_with_gateway
from services.inference.models import InferenceResult


class FakeGateway:
    def run(self, request):
        return InferenceResult(
            agent_name=request.agent_name,
            model="gemini-2.5-flash",
            provider="fake",
            content='{"resolution":"Prefer higher-trust HUST source.","uncertainty_reasons":[]}',
            parsed_data={
                "resolution": "Prefer higher-trust HUST source.",
                "uncertainty_reasons": [],
            },
        )


def test_resolve_conflicts_with_gateway_returns_resolution():
    parsed = resolve_conflicts_with_gateway(
        conflicts=["Quota conflict for Khoa hoc May tinh at HUST"],
        gateway=FakeGateway(),
    )

    assert parsed["resolution"] == "Prefer higher-trust HUST source."