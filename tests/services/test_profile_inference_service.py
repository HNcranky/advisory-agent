from services.chat.profile_state_service import CRITICAL_SLOT_ORDER
from services.profile_inference_service import (
    PROFILE_SYSTEM_PROMPT,
    build_profile_with_gateway,
)
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


def test_profile_system_prompt_covers_every_chat_critical_slot():
    # admission_year is extracted by regex in the chat layer, not by the LLM,
    # so the extraction prompt only needs to mention the slots the LLM owns.
    llm_owned_slots = [slot for slot in CRITICAL_SLOT_ORDER if slot != "admission_year"]
    for slot in llm_owned_slots:
        assert slot in PROFILE_SYSTEM_PROMPT, (
            f"PROFILE_SYSTEM_PROMPT must mention '{slot}' so live Gemini can fill it "
            "(otherwise the chat layer loops asking for that slot)."
        )


def test_profile_system_prompt_guides_gemini_to_infer_related_majors_from_interests():
    assert "infer suitable related majors" in PROFILE_SYSTEM_PROMPT
    assert "programming" in PROFILE_SYSTEM_PROMPT
    assert "artificial_intelligence_uet" in PROFILE_SYSTEM_PROMPT


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


def test_build_profile_with_gateway_normalizes_natural_interests_to_related_major_ids():
    class NaturalInterestGateway:
        def run(self, request):
            return InferenceResult(
                agent_name=request.agent_name,
                model="gemini-2.5-flash-lite",
                provider="fake",
                content='{"total_score":26.5,"subject_combination":"A00","preferred_majors":["lập trình","trí tuệ nhân tạo"],"preferred_schools":["vnu_uet"],"missing_slots":[]}',
                parsed_data={
                    "total_score": 26.5,
                    "subject_combination": "A00",
                    "preferred_majors": ["lập trình", "trí tuệ nhân tạo"],
                    "preferred_schools": ["vnu_uet"],
                    "missing_slots": [],
                },
            )

    profile = build_profile_with_gateway(
        user_query="Em thích lập trình và trí tuệ nhân tạo, muốn học ở UET",
        gateway=NaturalInterestGateway(),
    )

    assert "cntt" in profile.preferred_majors
    assert "computer_science" in profile.preferred_majors
    assert "software_engineering" in profile.preferred_majors
    assert "data_science" in profile.preferred_majors
    assert "artificial_intelligence_uet" in profile.preferred_majors
