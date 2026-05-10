from services.profile_inference_service import build_profile_with_gateway
from services.inference.models import InferenceResult


class FakeGateway:
    def run(self, request):
        return InferenceResult(
            agent_name=request.agent_name,
            model="gemini-2.5-flash-lite",
            provider="fake",
            content='{"total_score":27,"subject_combination":"A00","preferred_majors":["computer_science"],"preferred_schools":["hust"],"missing_slots":[]}',
            parsed_data={
                "total_score": 27,
                "subject_combination": "A00",
                "preferred_majors": ["computer_science"],
                "preferred_schools": ["hust"],
                "missing_slots": [],
            },
        )


def test_build_profile_with_gateway_returns_student_profile():
    profile = build_profile_with_gateway(
        user_query="Em duoc 27 diem A00 muon hoc Cong nghe thong tin o HUST",
        gateway=FakeGateway(),
    )

    assert profile.total_score == 27
    assert profile.subject_combination == "A00"
    assert profile.preferred_majors == ["computer_science"]
    assert profile.preferred_schools == ["hust"]


def test_build_profile_with_gateway_falls_back_when_gateway_is_unavailable():
    class UnavailableGateway:
        def is_available(self):
            return False

        def run(self, request):
            raise AssertionError("gateway.run should not be called when unavailable")

    profile = build_profile_with_gateway(
        user_query="Em duoc 27 diem A00 muon hoc Cong nghe thong tin o HUST",
        gateway=UnavailableGateway(),
    )

    assert profile.total_score == 27
    assert profile.subject_combination == "A00"
    assert profile.preferred_majors == ["computer_science"]
    assert profile.preferred_schools == ["hust"]
    assert profile.missing_slots == []
