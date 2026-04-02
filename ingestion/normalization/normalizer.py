# normalization/normalizer.py
"""
Normalization orchestrator.
Transforms ExtractedAdmissionFact → NormalizedAdmissionRecord
"""

import logging
from typing import List

from ingestion.models.pipeline_models import (
    ExtractedAdmissionFact,
    NormalizedAdmissionRecord,
)
from ingestion.normalization.program_mapper import map_program
from ingestion.normalization.method_mapper import map_method
from ingestion.normalization.subject_combination_mapper import map_combinations
from ingestion.normalization.quota_parser import parse_quota

logger = logging.getLogger(__name__)


def normalize_fact(
    fact: ExtractedAdmissionFact,
) -> NormalizedAdmissionRecord:
    """
    Normalize a single extracted fact into a canonical record.

    Args:
        fact: Raw extracted admission fact

    Returns:
        Normalized admission record
    """
    # Map program
    program_id, program_canonical = map_program(
        fact.program_name, fact.program_code
    )

    # Map admission method
    method = map_method(fact.admission_method_raw)

    # Map subject combinations
    combos = map_combinations(fact.subject_combinations_raw)

    # Parse quota
    quota = parse_quota(fact.quota_raw)

    record = NormalizedAdmissionRecord(
        school_id=fact.source_reference.school_id,
        school_name_canonical=fact.school_name,
        admission_year=fact.admission_year,
        program_id=program_id,
        program_name_canonical=program_canonical,
        program_name_raw=fact.program_name,
        admission_method=method,
        admission_method_raw=fact.admission_method_raw,
        subject_combinations=combos,
        quota=quota,
        conditions=(
            {"raw": fact.additional_conditions_raw}
            if fact.additional_conditions_raw else None
        ),
        tuition=(
            {"raw": fact.tuition_raw}
            if fact.tuition_raw else None
        ),
        source_url=fact.source_reference.source_url,
        source_trust_level=fact.source_reference.trust_level,
        confidence_score=fact.confidence_score,
    )

    return record


def normalize_facts(
    facts: List[ExtractedAdmissionFact],
) -> List[NormalizedAdmissionRecord]:
    """
    Normalize a batch of facts.

    Args:
        facts: List of raw extracted facts

    Returns:
        List of normalized records
    """
    records = []
    for fact in facts:
        try:
            record = normalize_fact(fact)
            records.append(record)
        except Exception as e:
            logger.error(
                f"Failed to normalize fact for "
                f"'{fact.program_name}': {e}"
            )

    logger.info(f"Normalized {len(records)}/{len(facts)} facts")
    return records
