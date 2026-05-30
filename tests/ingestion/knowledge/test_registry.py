import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ingestion.knowledge.registry.knowledge_registry import KnowledgeRegistry


def test_default_seed_loads_three_schools_each_with_two_doc_types():
    reg = KnowledgeRegistry()
    schools = reg.schools()
    assert set(schools) >= {"HUST", "NEU", "VNU-UET"}
    for school in ("HUST", "NEU", "VNU-UET"):
        sources = reg.get_sources_by_school(school)
        doc_types = {s.document_type for s in sources}
        assert len(doc_types) >= 2, f"{school} has < 2 document_types"


def test_all_sources_returns_models():
    reg = KnowledgeRegistry()
    sources = reg.all_sources()
    assert len(sources) >= 6
    assert sources[0].topic in {
        "tuition", "curriculum", "scholarship", "dormitory",
        "career", "admission_policy", "program_overview",
    }


def test_custom_seed_path(tmp_path):
    seed = tmp_path / "seed.json"
    seed.write_text(json.dumps([
        {"school": "X", "source_url": "https://x/t",
         "document_type": "tuition_page", "topic": "tuition"},
    ]), encoding="utf-8")
    reg = KnowledgeRegistry(seed_path=seed)
    assert reg.schools() == ["X"]


def test_invalid_entry_in_seed_raises(tmp_path):
    seed = tmp_path / "bad.json"
    seed.write_text(json.dumps([
        {"school": "X", "source_url": "https://x/t",
         "document_type": "tuition_page", "topic": "BOGUS"},
    ]), encoding="utf-8")
    with pytest.raises(ValidationError):
        KnowledgeRegistry(seed_path=seed)
