# parsers/pdf_parser.py

from pdfminer.high_level import extract_text
import tempfile

def parse_pdf(content: bytes):

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
        f.write(content)
        path = f.name

    text = extract_text(path)

    return text