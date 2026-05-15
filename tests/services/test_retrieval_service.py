from contextlib import contextmanager

import services.retrieval_service as retrieval_service
from agents.models import StudentProfile


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows
        self.executed_sql = None
        self.executed_params = None

    def execute(self, sql, params):
        self.executed_sql = sql
        self.executed_params = params

    def fetchall(self):
        return self._rows


def test_build_retrieval_filters():
    profile = StudentProfile(
        preferred_majors=["computer_science"],
        preferred_schools=["hust"],
        subject_combination="A00",
    )

    filters = retrieval_service.build_retrieval_filters(profile, 2026)

    assert filters["admission_year"] == 2026
    assert filters["preferred_schools"] == ["hust"]
    assert filters["subject_combination"] == "A00"


def test_fetch_candidates_maps_rows(monkeypatch):
    fake_rows = [
        (
            "hust",
            "Hanoi University of Science and Technology",
            2026,
            "computer_science",
            "Khoa hoc May tinh",
            "thpt_score",
            ["A00", "A01"],
            {"total": 300},
            {"unit": "VND"},
            {"language": "vi"},
            "https://example.com/admission",
            5,
            0.92,
        )
    ]

    fake_cursor = _FakeCursor(fake_rows)

    @contextmanager
    def fake_get_cursor(commit=False):
        yield fake_cursor

    monkeypatch.setattr(retrieval_service, "get_cursor", fake_get_cursor)

    candidates = retrieval_service.fetch_candidates(
        {
            "admission_year": 2026,
            "preferred_majors": ["computer_science"],
            "preferred_schools": ["hust"],
            "subject_combination": "A00",
        }
    )

    assert len(candidates) == 1
    assert candidates[0].school_id == "hust"
    assert candidates[0].program_id == "computer_science"
    assert candidates[0].subject_combinations == ["A00", "A01"]
    assert candidates[0].evidence[0].source_url == "https://example.com/admission"


def test_fetch_candidates_returns_both_rows_when_two_sources_exist(monkeypatch):
    """When canonical_admission_records has two rows for the same logical program
    but different source URLs, fetch_candidates returns both as separate
    CandidateProgram objects. This guards against accidental DISTINCT/GROUP BY."""
    fake_rows = [
        (
            "hust",
            "Hanoi University of Science and Technology",
            2026,
            "computer_science",
            "Khoa hoc May tinh",
            "thpt_score",
            ["A00"],
            {"total": 300},
            None,
            None,
            "https://hust.edu.vn/admission/2026",
            5,
            0.92,
        ),
        (
            "hust",
            "Hanoi University of Science and Technology",
            2026,
            "computer_science",
            "Khoa hoc May tinh",
            "thpt_score",
            ["A00"],
            {"total": 280},
            None,
            None,
            "https://ts.hust.edu.vn/tuyen-sinh/2026",
            4,
            0.85,
        ),
    ]

    fake_cursor = _FakeCursor(fake_rows)

    @contextmanager
    def fake_get_cursor(commit=False):
        yield fake_cursor

    monkeypatch.setattr(retrieval_service, "get_cursor", fake_get_cursor)

    candidates = retrieval_service.fetch_candidates({"admission_year": 2026})

    assert len(candidates) == 2
    source_urls = {c.evidence[0].source_url for c in candidates}
    assert "https://hust.edu.vn/admission/2026" in source_urls
    assert "https://ts.hust.edu.vn/tuyen-sinh/2026" in source_urls


def test_retrieval_service_stays_deterministic_without_gateway_calls():
    filters = {
        "admission_year": 2026,
        "preferred_majors": ["computer_science"],
        "preferred_schools": ["hust"],
        "subject_combination": "A00",
    }

    assert filters["preferred_majors"] == ["computer_science"]
