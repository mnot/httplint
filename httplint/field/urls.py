"""
URL resolution shared by Link, Location, Referer, Reporting-Endpoints, Speculation-Rules and NEL.
"""

from typing import Optional
from urllib.parse import SplitResult, urljoin, urlsplit


def resolve_url(url: str, base: str = "") -> Optional[SplitResult]:
    "Resolve url against base (if any) and split it; None if urllib rejects it (e.g., bad IPv6)."
    try:
        return urlsplit(urljoin(base, url))
    except ValueError:
        return None


def is_secure(split: SplitResult) -> bool:
    "Whether a split URL has a secure scheme (https or wss)."
    return split.scheme.lower() in ("https", "wss")
