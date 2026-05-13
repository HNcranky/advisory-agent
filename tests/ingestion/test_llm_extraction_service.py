from services.inference.models import InferenceResult
from ingestion.extractors.llm_extraction_service import extract_admission_facts_with_gateway


class FakeGateway:
    def run(self, request):
        return InferenceResult(
            agent_name=request.agent_name,
            model="gemini-2.5-flash-lite",
            provider="fake",
            content='{"facts":[{"program_name":"Khoa hoc May tinh","admission_method":"thpt_score","subject_combinations":["A00","A01"]}]}',
            parsed_data={
                "facts": [
                    {
                        "program_name": "Khoa hoc May tinh",
                        "admission_method": "thpt_score",
                        "subject_combinations": ["A00", "A01"],
                    }
                ]
            },
        )


def test_extract_admission_facts_with_gateway_returns_fact_list():
    facts = extract_admission_facts_with_gateway(
        source_text="Chi tieu nganh Khoa hoc May tinh to hop A00 A01",
        gateway=FakeGateway(),
    )

    assert facts[0]["program_name"] == "Khoa hoc May tinh"