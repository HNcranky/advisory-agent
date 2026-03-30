import requests
import urllib3

urllib3.disable_warnings()

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

def fetch_url(url: str):

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30,
        verify=False
    )

    response.raise_for_status()

    return {
        "content": response.content,
        "content_type": response.headers.get("Content-Type", "")
    }