from agents.conflict_agent import conflict_agent
from agents.models import CandidateProgram, Evidence
from state import AgentState


def candidate(source_url, quota, trust):
    return CandidateProgram(
        candidate_id="vnu_uet:2026:cntt:thpt_score",
        school_id="vnu_uet",
        school_name="Dai hoc Cong nghe - DHQGHN",
        admission_year=2026,
        program_id="cntt",
        program_name="Cong nghe thong tin",
        admission_method="thpt_score",
        quota={"value": quota, "unit": "students"},
        evidence=[
            Evidence(
                source_url=source_url,
                school_name="Dai hoc Cong nghe - DHQGHN",
                admission_year=2026,
                field_name="quota",
                normalized_value={"value": quota, "unit": "students"},
                trust_level=trust,
                confidence_score=0.9,
            )
        ],
    )


def test_conflict_agent_resolves_decisive_quota_conflict():
    state = AgentState(
        user_query="Tu van",
        retrieved_programs=[
            candidate("mock://uet/program-page", 120, 2),
            candidate("mock://vnu/proposal-pdf", 150, 3),
        ],
    )

    output = conflict_agent(state)

    assert len(output.conflict_records) == 1
    assert len(output.resolution_outcomes) == 1
    assert output.resolution_outcomes[0].status == "resolved"
    assert output.resolution_outcomes[0].resolved_value == 150
    assert output.conflicts == []


def test_conflict_agent_marks_unresolved_candidates_uncertain(monkeypatch):
    state = AgentState(
        user_query="Tu van",
        retrieved_programs=[
            candidate("mock://a", 120, 2),
            candidate("mock://b", 150, 2),
        ],
    )

    output = conflict_agent(state)

    assert output.resolution_outcomes[0].status == "unresolved"
    assert output.conflicts
    assert any(
        "quota" in candidate.data_uncertain_fields
        for candidate in output.retrieved_programs
    )
