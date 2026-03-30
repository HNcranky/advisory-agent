# pipeline/ingestion_pipeline.py

from fetchers.http_fetcher import fetch_url
from parsers.html_parser import parse_html
from parsers.pdf_parser import parse_pdf
from extractors.admission_extractor import extract_admission
from pipeline.db_writer import save_to_staging


def run_ingestion(url: str):

    data = fetch_url(url)

    content = data["content"]
    content_type = data["content_type"]

    if "pdf" in content_type:
        text = parse_pdf(content)
    else:
        text = parse_html(content)

    print(f"Text: {text}\n\n\n")

    doc = extract_admission(text, url)

    # save_to_staging(doc)

    return doc