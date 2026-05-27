from services.conflict.source_labels import label_for_source


def test_mock_sources_have_readable_labels():
    assert label_for_source("mock://uet/program-page") == "Nguon mock: UET program page"
    assert label_for_source("mock://vnu/proposal-pdf") == "Nguon mock: VNU proposal PDF"


def test_known_hosts_have_vietnamese_labels():
    assert label_for_source("https://uet.vnu.edu.vn/tuyen-sinh") == "Trang tuyen sinh UET (DHQGHN)"
    assert label_for_source("https://vnu.edu.vn/de-an.pdf") == "De an tuyen sinh DHQGHN"
    assert label_for_source("https://ts.hust.edu.vn/tin-tuc") == "Trang tuyen sinh HUST"


def test_unknown_and_empty_sources_fallback_safely():
    assert label_for_source("https://example.edu.vn/a") == "Nguon: example.edu.vn"
    assert label_for_source("") == "Nguon khong xac dinh"
    assert label_for_source("not-a-url") == "Nguon khong xac dinh"
