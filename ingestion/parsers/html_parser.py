# parsers/html_parser.py
"""
Improved HTML parser that extracts structured content:
- Clean text
- Headings hierarchy
- Tables
- Links
- Title
"""

import logging
from typing import List, Dict
from bs4 import BeautifulSoup, Tag

from ingestion.models.pipeline_models import ParsedContent, DocumentType

logger = logging.getLogger(__name__)


def parse_html(content: bytes, url: str = "") -> ParsedContent:
    """
    Parse HTML content into structured ParsedContent.

    Args:
        content: Raw HTML bytes
        url: Source URL (for logging)

    Returns:
        ParsedContent with text, headings, tables, links
    """
    # Handle encoding
    try:
        html_str = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            html_str = content.decode("latin-1")
        except UnicodeDecodeError:
            html_str = content.decode("utf-8", errors="replace")

    soup = BeautifulSoup(html_str, "html.parser")

    # Remove scripts, styles, nav, footer noise
    for tag in soup(["script", "style", "noscript", "iframe"]):
        tag.decompose()

    # ─── Extract title ──────────────────────────────────────────
    title = None
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)

    # ─── Find main content area ─────────────────────────────────
    content_tag = _find_content_area(soup)

    # ─── Extract headings ───────────────────────────────────────
    headings = _extract_headings(content_tag)

    # ─── Extract tables ─────────────────────────────────────────
    tables = _extract_tables(content_tag)

    # ─── Extract links ──────────────────────────────────────────
    links = _extract_links(content_tag)

    # ─── Extract images ─────────────────────────────────────────
    images = _extract_images(content_tag)

    # ─── Extract clean text ─────────────────────────────────────
    text = content_tag.get_text(separator="\n", strip=True)

    parsed = ParsedContent(
        text=text,
        title=title,
        headings=headings,
        tables=tables,
        links=links,
        images=images,
        document_type=DocumentType.HTML_ARTICLE,
        parser_used="html_parser",
    )

    logger.info(
        f"Parsed HTML: {len(text)} chars, "
        f"{len(headings)} headings, "
        f"{len(tables)} tables, "
        f"{len(links)} links"
    )

    return parsed


def _find_content_area(soup: BeautifulSoup) -> Tag:
    """Find the main content area, falling back through several strategies."""
    # Try common content containers in order of specificity
    selectors = [
        ("article", {}),
        ("div", {"class": "content"}),
        ("div", {"class": "post-content"}),
        ("div", {"class": "entry-content"}),
        ("div", {"class": "article-content"}),
        ("main", {}),
        ("div", {"id": "content"}),
        ("div", {"role": "main"}),
    ]

    for tag_name, attrs in selectors:
        found = soup.find(tag_name, attrs)
        if found:
            return found

    # Fallback: body
    return soup.body or soup


def _extract_headings(tag: Tag) -> List[str]:
    """Extract all heading text from h1-h6."""
    headings = []
    for h in tag.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        text = h.get_text(strip=True)
        if text:
            headings.append(f"[{h.name}] {text}")
    return headings


def _extract_tables(tag: Tag) -> List[List[List[str]]]:
    """Extract tables as list of rows, each row is list of cell texts."""
    tables = []
    for table in tag.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = []
            for td in tr.find_all(["td", "th"]):
                cells.append(td.get_text(strip=True))
            if cells:
                rows.append(cells)
        if rows:
            tables.append(rows)
    return tables


def _extract_links(tag: Tag) -> List[Dict[str, str]]:
    """Extract all links with their text."""
    links = []
    seen_urls = set()
    for a in tag.find_all("a", href=True):
        url = a["href"]
        text = a.get_text(strip=True)
        if url and url not in seen_urls and not url.startswith("javascript:"):
            links.append({"url": url, "text": text})
            seen_urls.add(url)
    return links


def _extract_images(tag: Tag) -> List[str]:
    """Extract image URLs."""
    images = []
    for img in tag.find_all("img", src=True):
        images.append(img["src"])
    return images