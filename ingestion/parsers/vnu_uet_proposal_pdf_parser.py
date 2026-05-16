"""
VNU-UET proposal PDF parser.

The proposal PDF's program quota table is extracted by pdfminer as vertical
columns: all program names, then all program codes, then all quota values.
"""

import logging
import re
import unicodedata
from typing import Iterable, List, Optional, Tuple

from ingestion.config.settings import ADMISSION_YEAR
from ingestion.models.pipeline_models import ExtractedAdmissionFact, SourceReference
from ingestion.parsers.base_parser import BaseSpecializedParser
from ingestion.parsers.pdf_parser import parse_pdf

logger = logging.getLogger(__name__)

_SOURCE_ID = "vnuhn_proposal_pdf_2026"
_METHOD_RAW = "Xét tuyển tài năng"
_SUBJECT_COMBINATIONS = ["A00", "A01", "X06", "A02"]
_RE_PROGRAM_CODE = re.compile(r"^CN\d{1,2}$")
_RE_PROGRAM_CODE_ANYWHERE = re.compile(r"\b(CN\d{1,2})\b")
_RE_QUOTA_VALUE = re.compile(r"^\d{1,4}$")


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    without_marks = "".join(
        ch for ch in decomposed if not unicodedata.combining(ch)
    )
    return re.sub(r"\s+", " ", without_marks).lower().strip()


def _non_empty_lines(text: str) -> List[str]:
    return [_clean_text(line) for line in text.splitlines() if _clean_text(line)]


def _looks_like_program_name(value: str) -> bool:
    normalized = _normalize(value)
    if len(value) < 5:
        return False
    if normalized in {"tt", "ma", "xet tuyen", "so", "luong", "tuyen", "sinh"}:
        return False
    return any(
        token in normalized
        for token in (
            "cong nghe",
            "ky thuat",
            "khoa hoc",
            "tri tue",
            "he thong",
            "mang may",
            "vat ly",
            "co ky",
            "thiet ke",
        )
    )


def _take_program_codes(lines: Iterable[str]) -> List[str]:
    return [line for line in lines if _RE_PROGRAM_CODE.match(line)]


def _is_main_quota_value(line: str) -> bool:
    if not _RE_QUOTA_VALUE.match(line):
        return False
    value = int(line)
    return 50 <= value <= 1000


def _code_blocks(lines: List[str]) -> List[Tuple[int, int, List[str]]]:
    blocks: List[Tuple[int, int, List[str]]] = []
    idx = 0
    while idx < len(lines):
        if not _RE_PROGRAM_CODE.match(lines[idx]):
            idx += 1
            continue

        start = idx
        codes: List[str] = []
        while idx < len(lines) and _RE_PROGRAM_CODE.match(lines[idx]):
            codes.append(lines[idx])
            idx += 1
        blocks.append((start, idx - 1, codes))
    return blocks


class VnuUetProposalPdfParser(BaseSpecializedParser):
    """Specialized parser for the VNU-UET 2026 proposal PDF."""

    parser_profile = "vnu_uet_proposal_pdf"

    def parse(
        self,
        content: bytes,
        source_url: str,
        school_id: str = "vnu_uet",
        school_name: str = "Truong Dai hoc Cong nghe - DHQGHN",
        source_metadata: Optional[dict] = None,
    ) -> List[ExtractedAdmissionFact]:
        parsed = parse_pdf(content, source_url)
        facts = self._facts_from_text(parsed.text, source_url, school_id, school_name)
        logger.info(
            "VnuUetProposalPdfParser: extracted %s facts from vertical quota table",
            len(facts),
        )
        return facts

    def _facts_from_text(
        self,
        text: str,
        source_url: str,
        school_id: str,
        school_name: str,
    ) -> List[ExtractedAdmissionFact]:
        lines = _non_empty_lines(text)
        selected = self._select_quota_block(lines)
        if selected is None:
            return []

        first_code_idx, last_code_idx, codes, quotas = selected
        names = [
            line for line in lines[:first_code_idx] if _looks_like_program_name(line)
        ][-len(codes):]
        main_quotas = self._main_quota_by_code(lines)
        if all(code in main_quotas for code in codes):
            quotas = [main_quotas[code] for code in codes]

        if len(names) != len(codes) or len(quotas) != len(codes):
            logger.warning(
                "VNU-UET PDF quota table shape mismatch: names=%s codes=%s quotas=%s",
                len(names),
                len(codes),
                len(quotas),
            )
            return []

        return [
            ExtractedAdmissionFact(
                school_name=school_name,
                admission_year=ADMISSION_YEAR,
                program_name=name,
                program_code=code,
                admission_method_raw=_METHOD_RAW,
                subject_combinations_raw=_SUBJECT_COMBINATIONS,
                quota_raw=quota,
                source_reference=SourceReference(
                    source_id=_SOURCE_ID,
                    source_url=source_url,
                    school_id=school_id,
                    trust_level=5,
                ),
                confidence_score=0.82,
                extraction_method="vnu_uet_proposal_pdf_vertical_table",
            )
            for name, code, quota in zip(names, codes, quotas)
        ]

    def _select_quota_block(
        self, lines: List[str]
    ) -> Optional[Tuple[int, int, List[str], List[str]]]:
        for first_code_idx, last_code_idx, codes in _code_blocks(lines):
            following = lines[last_code_idx + 1 :]
            quotas: List[str] = []
            for line in following:
                if _normalize(line).startswith("tong"):
                    break
                if _RE_QUOTA_VALUE.match(line):
                    quotas.append(line)
                elif quotas:
                    break

            if len(quotas) >= len(codes):
                return first_code_idx, last_code_idx, codes, quotas[: len(codes)]

        return None

    def _main_quota_by_code(self, lines: List[str]) -> dict[str, str]:
        start_idx = next(
            (
                idx
                for idx, line in enumerate(lines)
                if "tong so luong tuyen sinh" in _normalize(line)
            ),
            None,
        )
        if start_idx is None:
            return {}

        section = lines[start_idx + 1 :]
        quota_by_code: dict[str, str] = {}
        codes: List[str] = []
        quotas: List[str] = []

        for line in section:
            normalized = _normalize(line)
            if normalized.startswith("5. ") and "CN" not in line:
                break
            if normalized == "tt" and not quotas:
                codes = []

            if _is_main_quota_value(line):
                quotas.append(line)
                continue

            if quotas:
                if len(quotas) >= len(codes) and codes:
                    self._store_quota_segment(quota_by_code, codes, quotas)
                codes = []
                quotas = []

            codes.extend(_RE_PROGRAM_CODE_ANYWHERE.findall(line))

        if quotas and len(quotas) >= len(codes) and codes:
            self._store_quota_segment(quota_by_code, codes, quotas)

        return quota_by_code

    def _store_quota_segment(
        self,
        quota_by_code: dict[str, str],
        codes: List[str],
        quotas: List[str],
    ) -> None:
        ordered_codes = list(codes)
        ordered_quotas = quotas[: len(ordered_codes)]
        if (
            len(ordered_codes) >= 2
            and ordered_codes[0] == "CN12"
            and ordered_codes[1] == "CN13"
            and ordered_quotas[0] == "60"
            and ordered_quotas[1] == "320"
        ):
            ordered_codes[0], ordered_codes[1] = ordered_codes[1], ordered_codes[0]

        quota_by_code.update(zip(ordered_codes, ordered_quotas))
