from pathlib import Path

from ingestion.parsers.vnu_uet_admission_parser import (
    _SELECTOR_PRIORITY,
    VnuUetAdmissionParser,
)


FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "ingestion"
    / "parsers"
    / "_fixtures"
    / "vnu_uet_admission_page.html"
)


def test_vnu_uet_parser_extracts_program_facts_from_fixture():
    parser = VnuUetAdmissionParser()

    facts = parser.parse(
        content=FIXTURE.read_bytes(),
        source_url="https://uet.vnu.edu.vn/tuyen-sinh/",
        school_id="vnu_uet",
        school_name="Truong Dai hoc Cong nghe - DHQGHN",
    )

    quota_facts = [fact for fact in facts if fact.quota_raw and fact.quota_raw.isdigit()]
    facts_by_code = {fact.program_code: fact for fact in facts}

    assert len(facts) == 20
    assert len(quota_facts) == 20
    assert any(fact.admission_method_raw for fact in facts)
    assert any(fact.subject_combinations_raw for fact in facts)
    assert facts[0].source_reference.source_id == "vnu_uet_admission_homepage_2026"
    assert facts[0].source_reference.source_url == "https://uet.vnu.edu.vn/tuyen-sinh/"
    assert facts[0].source_reference.school_id == "vnu_uet"
    assert facts[0].source_reference.trust_level == 4

    assert facts_by_code["CN1"].program_name == "C\u00f4ng ngh\u1ec7 th\u00f4ng tin"
    assert facts_by_code["CN1"].quota_raw == "3"
    assert facts_by_code["CN2"].program_name == "K\u1ef9 thu\u1eadt m\u00e1y t\u00ednh"
    assert facts_by_code["CN2"].quota_raw == "3"
    assert facts_by_code["CN20"].program_name == "Khoa h\u1ecdc d\u1eef li\u1ec7u"
    assert facts_by_code["CN20"].quota_raw == "1"

    assert facts_by_code["CN1"].subject_combinations_raw == [
        "A00",
        "A01",
        "X06",
        "A02",
    ]
    for fact in facts:
        assert "X26" not in (fact.subject_combinations_raw or [])
        assert "D01" not in (fact.subject_combinations_raw or [])
        assert "B00" not in (fact.subject_combinations_raw or [])


def test_vnu_uet_parser_prefers_fixture_confirmed_selector():
    assert _SELECTOR_PRIORITY[0] == "div.dev-faq-content table"
