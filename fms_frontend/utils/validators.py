import re

_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def is_valid_url(url: str) -> bool:
    if not url:
        return True
    return bool(_URL_RE.match(url.strip()))