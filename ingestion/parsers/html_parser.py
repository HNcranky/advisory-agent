# parsers/html_parser.py

from bs4 import BeautifulSoup


def parse_html(content: bytes):

    soup = BeautifulSoup(content, "html.parser")

    # remove scripts/styles
    for tag in soup(["script", "style"]):
        tag.decompose()

    # 1️⃣ thử thẻ <content>
    content_tag = soup.find("content")

    # 2️⃣ fallback div.content
    if not content_tag:
        content_tag = soup.find("div", class_="content")

    # 3️⃣ fallback main
    if not content_tag:
        content_tag = soup.find("main")

    # 4️⃣ nếu vẫn không có → body
    if not content_tag:
        content_tag = soup.body

    text = content_tag.get_text(separator="\n", strip=True)

    return text