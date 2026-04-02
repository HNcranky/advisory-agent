# parsers/parser_dispatcher.py
"""
Selects and runs the appropriate parser based on DocumentType
and parser_profile from the source registry.
"""

import logging
from typing import Optional, List, Union

from ingestion.models.pipeline_models import (
    DocumentType, ParsedContent, FetchResult, ExtractedAdmissionFact,
)
from ingestion.parsers.html_parser import parse_html
from ingestion.parsers.pdf_parser import parse_pdf

logger = logging.getLogger(__name__)


def dispatch_parser(
    fetch_result: FetchResult,
    doc_type: DocumentType,
    parser_profile: str = "default",
) -> Union[ParsedContent, List[ExtractedAdmissionFact]]:
    """
    Dispatch to the appropriate parser based on document type
    and parser profile.

    For special profiles like 'hust_programs', we use a
    domain-specific parser that returns ExtractedAdmissionFact
    directly (skipping the generic extraction step).

    Args:
        fetch_result: Fetched content
        doc_type: Classified document type
        parser_profile: Parser configuration from source registry

    Returns:
        Either ParsedContent (for generic flow)
        or List[ExtractedAdmissionFact] (for specialized parsers)
    """
    # ─── Specialized parsers ────────────────────────────────────
    if parser_profile == "hust_programs":
        from ingestion.parsers.hust_program_parser import parse_hust_programs
        return parse_hust_programs(
            content=fetch_result.raw_content,
            source_url=fetch_result.final_url,
        )

    # ─── Generic parsers ────────────────────────────────────────
    if doc_type == DocumentType.HTML_ARTICLE:
        return parse_html(
            content=fetch_result.raw_content,
            url=fetch_result.final_url,
        )

    elif doc_type in (DocumentType.PDF_TEXT, DocumentType.PDF_SCANNED):
        if doc_type == DocumentType.PDF_SCANNED:
            # TODO: Use Gemini OCR for scanned PDFs
            logger.warning(
                f"Scanned PDF detected for {fetch_result.final_url}, "
                "falling back to text extraction"
            )
        return parse_pdf(
            content=fetch_result.raw_content,
            url=fetch_result.final_url,
        )

    elif doc_type == DocumentType.DOCX:
        # TODO: Implement DOCX parser
        logger.warning("DOCX parsing not yet implemented")
        return ParsedContent(
            text="",
            document_type=doc_type,
            parser_used="none",
        )

    else:
        logger.warning(f"No parser for document type {doc_type}")
        return ParsedContent(
            text="",
            document_type=doc_type,
            parser_used="none",
        )
