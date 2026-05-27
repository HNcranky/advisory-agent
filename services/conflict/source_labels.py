from urllib.parse import urlparse

MOCK_LABELS = {
    "mock://uet/program-page": "Nguon mock: UET program page",
    "mock://vnu/proposal-pdf": "Nguon mock: VNU proposal PDF",
    "mock://uet/admission-news": "Nguon mock: UET admission news",
}

HOST_LABELS = {
    "uet.vnu.edu.vn": "Trang tuyen sinh UET (DHQGHN)",
    "vnu.edu.vn": "De an tuyen sinh DHQGHN",
    "ts.hust.edu.vn": "Trang tuyen sinh HUST",
    "hust.edu.vn": "Trang tuyen sinh HUST",
}


def label_for_source(source_url: str) -> str:
    if not source_url:
        return "Nguon khong xac dinh"
    if source_url in MOCK_LABELS:
        return MOCK_LABELS[source_url]

    parsed = urlparse(source_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "Nguon khong xac dinh"
    hostname = parsed.netloc.lower()
    return HOST_LABELS.get(hostname, f"Nguon: {hostname}")
