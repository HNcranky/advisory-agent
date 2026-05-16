from ingestion.models.pipeline_models import DocumentType, ParsedContent
from ingestion.parsers.vnu_uet_proposal_pdf_parser import VnuUetProposalPdfParser


def test_vnu_uet_proposal_pdf_parser_extracts_vertical_program_quota_table(monkeypatch):
    parser = VnuUetProposalPdfParser()
    pdf_text = """
    TT

    1.
    2.
    3.

    Công nghệ thông tin
    Kỹ thuật máy tính
    Khoa học máy tính

    Mã
    xét tuyển

    CN1
    CN2
    CN8

    Số
    lượng
    tuyển
    sinh

    120
    110
    90

    Tổng:
    """

    def fake_parse_pdf(content, url):
        return ParsedContent(
            text=pdf_text,
            document_type=DocumentType.PDF_TEXT,
            parser_used="pdf_parser",
        )

    monkeypatch.setattr(
        "ingestion.parsers.vnu_uet_proposal_pdf_parser.parse_pdf",
        fake_parse_pdf,
    )

    facts = parser.parse(
        content=b"%PDF-1.4",
        source_url="https://tuyensinh.uet.vnu.edu.vn/proposal.pdf",
        school_id="vnu_uet",
        school_name="Truong Dai hoc Cong nghe - DHQGHN",
    )

    facts_by_code = {fact.program_code: fact for fact in facts}

    assert len(facts) == 3
    assert facts_by_code["CN1"].program_name == "Công nghệ thông tin"
    assert facts_by_code["CN1"].quota_raw == "120"
    assert facts_by_code["CN2"].program_name == "Kỹ thuật máy tính"
    assert facts_by_code["CN2"].quota_raw == "110"
    assert facts_by_code["CN8"].program_name == "Khoa học máy tính"
    assert facts_by_code["CN8"].quota_raw == "90"
    assert facts_by_code["CN1"].source_reference.source_id == "vnuhn_proposal_pdf_2026"
    assert facts_by_code["CN1"].source_reference.trust_level == 5


def test_vnu_uet_proposal_pdf_parser_uses_quota_block_when_later_tables_repeat_codes(monkeypatch):
    parser = VnuUetProposalPdfParser()
    pdf_text = """
    TT
    1.
    2.
    3.
    Công nghệ thông tin
    Kỹ thuật máy tính
    Khoa học máy tính
    Mã
    xét tuyển
    Số
    lượng
    tuyển
    sinh
    Ngưỡng
    ĐBCL 2025
    24
    22
    CN1
    CN2
    CN8
    120
    110
    90
    Tổng:

    STT
    Mã
    Xét
    1
    2
    3
    CN1
    CN2
    CN8
    Công nghệ thông tin
    Kỹ thuật máy tính
    Khoa học máy tính
    38.000.000
    38.000.000
    38.000.000
    """

    def fake_parse_pdf(content, url):
        return ParsedContent(
            text=pdf_text,
            document_type=DocumentType.PDF_TEXT,
            parser_used="pdf_parser",
        )

    monkeypatch.setattr(
        "ingestion.parsers.vnu_uet_proposal_pdf_parser.parse_pdf",
        fake_parse_pdf,
    )

    facts = parser.parse(
        content=b"%PDF-1.4",
        source_url="https://tuyensinh.uet.vnu.edu.vn/proposal.pdf",
        school_id="vnu_uet",
        school_name="Truong Dai hoc Cong nghe - DHQGHN",
    )

    assert [(fact.program_code, fact.quota_raw) for fact in facts] == [
        ("CN1", "120"),
        ("CN2", "110"),
        ("CN8", "90"),
    ]


def test_vnu_uet_proposal_pdf_parser_prefers_main_quota_table_when_present(monkeypatch):
    parser = VnuUetProposalPdfParser()
    pdf_text = """
    TT
    1.
    2.
    3.
    Công nghệ thông tin
    Kỹ thuật máy tính
    Khoa học máy tính
    Mã
    xét tuyển
    Số
    lượng
    tuyển
    sinh
    CN1
    CN2
    CN8
    3
    3
    3
    Tổng:

    4. Số lượng tuyển sinh
    Tổng số lượng tuyển sinh: 4020
    TT
    Mã
    xét
    tuyển
    Tên ngành xét tuyển
    Số lượng
    tuyển
    sinh
    1. CN1 Công nghệ thông tin
    2. CN2 Kỹ thuật máy tính
    3. CN8 Khoa học máy tính
    5. CN5 Công nghệ kỹ thuật xây dựng
    460
    400
    400
    160
    1.Phương thức: xét tuyển thẳng.
    """

    def fake_parse_pdf(content, url):
        return ParsedContent(
            text=pdf_text,
            document_type=DocumentType.PDF_TEXT,
            parser_used="pdf_parser",
        )

    monkeypatch.setattr(
        "ingestion.parsers.vnu_uet_proposal_pdf_parser.parse_pdf",
        fake_parse_pdf,
    )

    facts = parser.parse(
        content=b"%PDF-1.4",
        source_url="https://tuyensinh.uet.vnu.edu.vn/proposal.pdf",
        school_id="vnu_uet",
        school_name="Truong Dai hoc Cong nghe - DHQGHN",
    )

    assert [(fact.program_code, fact.quota_raw) for fact in facts] == [
        ("CN1", "460"),
        ("CN2", "400"),
        ("CN8", "400"),
    ]


def test_vnu_uet_proposal_pdf_parser_resets_codes_at_repeated_main_table_header(monkeypatch):
    parser = VnuUetProposalPdfParser()
    pdf_text = """
    TT
    Trí tuệ nhân tạo
    Kỹ thuật năng lượng
    Mã xét tuyển
    CN12
    CN13
    3
    2
    Tổng:

    Tổng số lượng tuyển sinh: 4020
    1. CN1 Công nghệ thông tin
    460
    1.Phương thức: xét tuyển thẳng.
    Riêng CN10 và CN21 thêm tổ hợp A02
    TT
    Mã
    xét
    tuyển
    Tên ngành xét tuyển
    12. CN12 Trí tuệ nhân tạo
    13. CN13 Kỹ thuật năng lượng
    60
    320
    (-) Tổ hợp xét tuyển
    """

    def fake_parse_pdf(content, url):
        return ParsedContent(
            text=pdf_text,
            document_type=DocumentType.PDF_TEXT,
            parser_used="pdf_parser",
        )

    monkeypatch.setattr(
        "ingestion.parsers.vnu_uet_proposal_pdf_parser.parse_pdf",
        fake_parse_pdf,
    )

    facts = parser.parse(
        content=b"%PDF-1.4",
        source_url="https://tuyensinh.uet.vnu.edu.vn/proposal.pdf",
        school_id="vnu_uet",
        school_name="Truong Dai hoc Cong nghe - DHQGHN",
    )

    assert [(fact.program_code, fact.quota_raw) for fact in facts] == [
        ("CN12", "320"),
        ("CN13", "60"),
    ]
