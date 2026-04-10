import json
from pathlib import Path

import agents.retrieval_agent as retrieval_agent
from agents.models import CandidateProgram, Evidence
from graph import graph
from state import AgentState


FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "advisory_queries.json"


def _mock_candidates():
    return [
        CandidateProgram(
            candidate_id="hust:2026:computer_science:thpt_score",
            school_id="hust",
            school_name="HUST",
            admission_year=2026,
            program_id="computer_science",
            program_name="Khoa hoc May tinh",
            admission_method="thpt_score",
            subject_combinations=["A00", "A01"],
            evidence=[
                Evidence(
                    source_url="https://example.com/hust-cs",
                    school_name="HUST",
                    admission_year=2026,
                    field_name="record",
                )
            ],
        ),
        CandidateProgram(
            candidate_id="hust:2026:software_engineering:thpt_score",
            school_id="hust",
            school_name="HUST",
            admission_year=2026,
            program_id="software_engineering",
            program_name="Ky thuat phan mem",
            admission_method="thpt_score",
            subject_combinations=["A00", "A01"],
            evidence=[
                Evidence(
                    source_url="https://example.com/hust-se",
                    school_name="HUST",
                    admission_year=2026,
                    field_name="record",
                )
            ],
        ),
    ]


def test_advisory_flow_from_fixture_cases(monkeypatch):
    with open(FIXTURE_PATH, "r", encoding="utf-8") as handle:
        cases = json.load(handle)

    for case in cases:
        if case["id"] == "no_result_case":
            monkeypatch.setattr(
                retrieval_agent, "fetch_candidates", lambda filters, limit=100: []
            )
        else:
            monkeypatch.setattr(
                retrieval_agent, "fetch_candidates", lambda filters, limit=100: _mock_candidates()
            )
        monkeypatch.setattr(retrieval_agent, "detect_conflicts", lambda candidates: [])

        state = AgentState(user_query=case["query"], admission_year=2026)
        result = graph.invoke(state)

        assert result["final_answer"]
        assert "Profile:" in result["final_answer"]

        policy = result.get("policy_decision")
        assert policy is not None
        assert policy.allow_answer is True

        if case["expect_follow_up"]:
            assert policy.requires_follow_up is True
            assert "Thong tin can bo sung" in result["final_answer"]
        else:
            assert isinstance(policy.requires_follow_up, bool)

        if case["id"] == "definitive_claim_prompt":
            assert "no_definitive_admission_answer" in policy.blocked_claims


def test_advisory_flow_handles_empty_retrieval(monkeypatch):
    monkeypatch.setattr(retrieval_agent, "fetch_candidates", lambda filters, limit=100: [])
    monkeypatch.setattr(retrieval_agent, "detect_conflicts", lambda candidates: [])

    state = AgentState(
        user_query="Em duoc 27 diem A00 muon hoc Cong nghe thong tin o HUST",
        admission_year=2026,
    )
    result = graph.invoke(state)

    assert "Chua co de xuat phu hop" in result["final_answer"]
    assert result["policy_decision"] is not None
    assert "empty_retrieval" in result["policy_decision"].policy_flags
