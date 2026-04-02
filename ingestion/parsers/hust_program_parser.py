# parsers/hust_program_parser.py
"""
HUST-specific parser for the program listing page:
https://ts.hust.edu.vn/training-cate/nganh-dao-tao-dai-hoc

Extracts structured program information directly from the HTML
rather than from plain text, because the listing page has
a consistent structure we can exploit.
"""

import re
import logging
from typing import List, Optional, Dict
from bs4 import BeautifulSoup, Tag

from ingestion.models.pipeline_models import (
    ExtractedAdmissionFact,
    SourceReference,
)
from ingestion.config.settings import ADMISSION_YEAR

logger = logging.getLogger(__name__)


def parse_hust_programs(
    content: bytes,
    source_url: str,
    source_id: str = "hust_program_listing",
    school_id: str = "hust",
) -> List[ExtractedAdmissionFact]:
    """
    Parse the HUST program listing page and extract all programs.

    The page has repeating blocks like:
      ### [01 - ( BF-E12 ) Kỹ thuật thực phẩm (CT tiên tiến)]
      Ngôn ngữ đào tạo: Tiếng Anh
      Mã xét tuyển: BF-E12
      [K00 ...] [A00 ...] [B00 ...]
      Chỉ tiêu tuyển sinh: 40
      Trường Hóa và Khoa học sự sống
      [Chi tiết](link)

    Args:
        content: Raw HTML bytes
        source_url: URL of the listing page
        source_id: Source registry ID
        school_id: School identifier

    Returns:
        List of ExtractedAdmissionFact for each program
    """
    try:
        html_str = content.decode("utf-8")
    except UnicodeDecodeError:
        html_str = content.decode("utf-8", errors="replace")

    soup = BeautifulSoup(html_str, "html.parser")

    # Find all program card elements
    # The HUST site uses .training-result__item or similar card-like divs
    program_cards = _find_program_cards(soup)

    if not program_cards:
        logger.warning(
            "No program cards found with CSS selectors, "
            "falling back to text-based extraction"
        )
        return _fallback_text_extraction(html_str, source_url, source_id, school_id)

    facts = []
    for card in program_cards:
        fact = _parse_card(card, source_url, source_id, school_id)
        if fact:
            facts.append(fact)

    logger.info(f"Extracted {len(facts)} programs from HUST listing")
    return facts


def _find_program_cards(soup: BeautifulSoup) -> list:
    """Find all program card elements in the HTML."""
    # Try multiple selectors for robustness
    selectors = [
        "div.training-result__item",
        "div.training-item",
        "div.program-item",
        "div.card",
    ]

    for selector in selectors:
        cards = soup.select(selector)
        if cards:
            logger.debug(f"Found {len(cards)} cards with selector '{selector}'")
            return cards

    # Fallback: look for repeating structures that contain "Mã xét tuyển"
    all_divs = soup.find_all("div")
    card_divs = []
    for div in all_divs:
        text = div.get_text()
        if "Mã xét tuyển" in text and "Chỉ tiêu" in text:
            # Check it's not a parent of other matching divs
            children_match = div.find_all(
                "div", string=lambda s: s and "Mã xét tuyển" in s
            )
            if not children_match:
                card_divs.append(div)

    return card_divs


def _parse_card(
    card: Tag,
    source_url: str,
    source_id: str,
    school_id: str,
) -> Optional[ExtractedAdmissionFact]:
    """Parse a single program card into an ExtractedAdmissionFact."""
    text = card.get_text(separator="\n", strip=True)

    # ─── Extract program name and code ──────────────────────────
    # Pattern: "01 - ( BF-E12 ) Kỹ thuật thực phẩm (CT tiên tiến)"
    header_pattern = r"(\d+)\s*-\s*\(\s*([A-Za-z0-9\-]+)\s*\)\s*(.+?)(?:\n|$)"
    header_match = re.search(header_pattern, text)

    program_name = None
    program_code = None

    if header_match:
        program_code = header_match.group(2).strip()
        program_name = header_match.group(3).strip()
    else:
        # Try alternative: "Mã xét tuyển: XXX"
        code_match = re.search(r"Mã xét tuyển:\s*([A-Za-z0-9\-]+)", text)
        if code_match:
            program_code = code_match.group(1).strip()

        # Try to get program name from heading or first link
        heading = card.find(["h3", "h4", "h5", "a"])
        if heading:
            name_text = heading.get_text(strip=True)
            # Remove the numbering prefix
            name_text = re.sub(r"^\d+\s*-\s*\(.*?\)\s*", "", name_text)
            if name_text:
                program_name = name_text

    if not program_name and not program_code:
        return None

    # ─── Extract subject combinations ───────────────────────────
    subject_combinations = _extract_subject_combinations(text)

    # ─── Extract quota ──────────────────────────────────────────
    quota_raw = None
    quota_match = re.search(
        r"Chỉ tiêu(?:\s+tuyển sinh)?:\s*(\d+)", text
    )
    if quota_match:
        quota_raw = quota_match.group(1)
    elif "Chỉ tiêu" in text:
        quota_raw = "chưa công bố"

    # ─── Extract language ───────────────────────────────────────
    language = None
    lang_match = re.search(r"Ngôn ngữ đào tạo:\s*(.+?)(?:\n|$)", text)
    if lang_match:
        language = lang_match.group(1).strip()

    # ─── Extract faculty/school ─────────────────────────────────
    faculty = None
    # Faculty is usually the last meaningful line before "Chi tiết"
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    for line in reversed(lines):
        if line in ("Chi tiết",):
            continue
        if any(kw in line for kw in ["Trường ", "Khoa ", "Viện "]):
            faculty = line
            break

    # ─── Extract detail URL ─────────────────────────────────────
    detail_link = card.find("a", string=re.compile(r"Chi tiết", re.I))
    detail_url = None
    if detail_link and detail_link.get("href"):
        detail_url = detail_link["href"]
        if not detail_url.startswith("http"):
            detail_url = f"https://ts.hust.edu.vn{detail_url}"

    # ─── Build admission methods string ─────────────────────────
    # HUST has 3 methods: Xét tuyển tài năng, ĐGTD (TSA), TN THPT
    # The program listing shows subject combinations for ĐGTD and THPT
    methods = []
    if any(c.startswith("K0") for c in subject_combinations):
        methods.append("Đánh giá tư duy (TSA)")
    thpt_combos = [c for c in subject_combinations if not c.startswith("K0")]
    if thpt_combos:
        methods.append("Xét điểm thi TN THPT")

    admission_method_raw = "; ".join(methods) if methods else None

    # ─── Build additional conditions ────────────────────────────
    conditions = {}
    if language:
        conditions["language"] = language
    if faculty:
        conditions["faculty"] = faculty
    if detail_url:
        conditions["detail_url"] = detail_url

    source_ref = SourceReference(
        source_id=source_id,
        source_url=source_url,
        school_id=school_id,
        trust_level=5,
    )

    return ExtractedAdmissionFact(
        school_name="Đại học Bách khoa Hà Nội",
        admission_year=ADMISSION_YEAR,
        program_name=program_name,
        program_code=program_code,
        admission_method_raw=admission_method_raw,
        subject_combinations_raw=subject_combinations,
        quota_raw=quota_raw,
        additional_conditions_raw=(
            str(conditions) if conditions else None
        ),
        source_reference=source_ref,
        confidence_score=0.85,
        extraction_method="hust_program_parser",
    )


def _extract_subject_combinations(text: str) -> List[str]:
    """
    Extract subject combination codes from text.

    Only matches genuine Vietnamese subject combination codes:
    A00-A16, B00-B08, C00-C04, D01-D15, K00-K01, V00-V01, DD2

    Does NOT match HUST program codes like E12, E19, E8, EP, etc.
    """
    # Known valid subject combination prefixes
    VALID_COMBO_PREFIXES = {"A", "B", "C", "D", "K", "V"}

    # Match codes like A00, B00, D07, K01, DD2
    pattern = r"\b([A-Z]{1,2}\d{2})\b"
    codes = re.findall(pattern, text)

    # Filter: only keep codes whose first letter is a valid combo prefix
    # This excludes HUST program codes like E12, E19, E8 (from BF-E12, etc.)
    # Also exclude codes that appear right after "(" which are program codes
    seen = set()
    unique = []
    for code in codes:
        prefix = code[0]
        if prefix not in VALID_COMBO_PREFIXES:
            continue
        if code not in seen:
            seen.add(code)
            unique.append(code)

    return unique


def _fallback_text_extraction(
    html_str: str,
    source_url: str,
    source_id: str,
    school_id: str,
) -> List[ExtractedAdmissionFact]:
    """
    Fallback text-based extraction when CSS selectors fail.
    Uses regex patterns on the full page text.
    """
    soup = BeautifulSoup(html_str, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)

    # Pattern: "XX - ( CODE ) Program Name"
    # CODE must be 2+ chars and start with a letter (not K00-style combo)
    block_pattern = r"(\d+)\s*-\s*\(\s*([A-Za-z]{2,}[\-]?[A-Za-z0-9]*)\s*\)\s*(.+?)(?=\d+\s*-\s*\(|$)"
    blocks = re.findall(block_pattern, text, re.DOTALL)

    facts = []
    seen_codes = set()

    for _, code, block_text in blocks:
        # Skip if code looks like a subject combination (A00, K00, etc.)
        if re.match(r"^[A-Z]{1,2}\d{2}$", code):
            continue

        # Skip noise codes
        if code.lower() in ("k00k00", "k01k01", "a00a00"):
            continue

        program_name_match = re.match(r"(.+?)(?:\n|Ngôn ngữ)", block_text)
        program_name = (
            program_name_match.group(1).strip()
            if program_name_match
            else block_text.split("\n")[0].strip()
        )

        # Skip if program name is too short or looks like noise
        if not program_name or len(program_name) < 3:
            continue

        # Deduplicate by program code
        if code in seen_codes:
            continue
        seen_codes.add(code)

        combos = _extract_subject_combinations(block_text)

        quota_raw = None
        quota_match = re.search(r"Chỉ tiêu[^:]*:\s*(\d+)", block_text)
        if quota_match:
            quota_raw = quota_match.group(1)

        # Extract language
        language = None
        lang_match = re.search(r"Ngôn ngữ đào tạo:\s*(.+?)(?:\n|$)", block_text)
        if lang_match:
            language = lang_match.group(1).strip()

        # Build methods
        methods = []
        if any(c.startswith("K0") for c in combos):
            methods.append("Đánh giá tư duy (TSA)")
        thpt_combos = [c for c in combos if not c.startswith("K0")]
        if thpt_combos:
            methods.append("Xét điểm thi TN THPT")
        admission_method_raw = "; ".join(methods) if methods else None

        conditions = {}
        if language:
            conditions["language"] = language

        source_ref = SourceReference(
            source_id=source_id,
            source_url=source_url,
            school_id=school_id,
            trust_level=5,
        )

        fact = ExtractedAdmissionFact(
            school_name="Đại học Bách khoa Hà Nội",
            admission_year=ADMISSION_YEAR,
            program_name=program_name,
            program_code=code,
            admission_method_raw=admission_method_raw,
            subject_combinations_raw=combos,
            quota_raw=quota_raw,
            additional_conditions_raw=(
                str(conditions) if conditions else None
            ),
            source_reference=source_ref,
            confidence_score=0.75,
            extraction_method="hust_program_parser_fallback",
        )
        facts.append(fact)

    logger.info(f"Fallback extracted {len(facts)} unique programs")
    return facts

