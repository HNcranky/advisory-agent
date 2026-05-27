from agents.models import CandidateProgram, Evidence, StudentProfile
from services.inference.models import InferenceResult
# from services.reasoning_inference_service import reason_candidates_with_gateway


class FakeGateway:
    def run(self, request):
        return InferenceResult(
            agent_name=request.agent_name,
            model="gemini-2.5-flash-lite",
            provider="fake",
            content='{"eligibility_checks":[{"candidate_id":"hust:1","eligible":true,"reasons":["Subject combination matches."],"risks":[],"confidence":0.9}],"ranked_recommendations":[{"candidate_id":"hust:1","band":"safe","score":0.91,"summary":"Strong fit.","reasons":["Preferred major matches."],"cautions":[]}]}',
            parsed_data={
                "eligibility_checks": [
                    {
                        "candidate_id": "hust:1",
                        "eligible": True,
                        "reasons": ["Subject combination matches."],
                        "risks": [],
                        "confidence": 0.9,
                    }
                ],
                "ranked_recommendations": [
                    {
                        "candidate_id": "hust:1",
                        "band": "safe",
                        "score": 0.91,
                        "summary": "Strong fit.",
                        "reasons": ["Preferred major matches."],
                        "cautions": [],
                    }
                ],
            },
        )


# def test_reason_candidates_with_gateway_returns_ranked_output():
#     profile = StudentProfile(total_score=27, subject_combination="A00", preferred_majors=["computer_science"])
#     candidates = [
#         CandidateProgram(
#             candidate_id="hust:1",
#             school_id="hust",
#             school_name="HUST",
#             admission_year=2026,
#             program_id="computer_science",
#             program_name="Khoa hoc May tinh",
#             subject_combinations=["A00"],
#             evidence=[Evidence(source_url="https://example.com", school_name="HUST", admission_year=2026, field_name="record")],
#         )
#     ]

#     checks, recommendations = reason_candidates_with_gateway(profile=profile, candidates=candidates, gateway=FakeGateway())

#     assert checks[0].candidate_id == "hust:1"
#     assert recommendations[0].band == "safe"