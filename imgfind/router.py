from __future__ import annotations

import logging
from urllib.parse import urlparse

from imgfind.models import Strategy
from imgfind.sources.gallery import ART_HOSTS

logger = logging.getLogger(__name__)

STOCK_KEYWORDS = {
    "stock", "royalty free", "free photo", "creative commons", "cc0",
    "commercial use", "license free", "no copyright",
}

ART_KEYWORDS = {
    "anime", "manga", "fan art", "fanart", "illustration", "pixiv",
    "artstation", "deviantart", "danbooru", "character", "waifu",
    "digital art", "concept art",
}

PHOTO_KEYWORDS = {
    "photo", "photograph", "camera", "landscape", "portrait",
    "nature", "street", "documentary", "real",
}


def classify_query(
    query: str,
    url: str | None = None,
    license_filter: str | None = None,
    sources: list[str] | None = None,
) -> list[Strategy]:
    if sources and sources != ["auto"]:
        return _map_explicit_sources(sources)

    strategies: list[Strategy] = []

    if url:
        strategies.extend(_classify_url(url))
        if strategies:
            return strategies

    query_lower = query.lower()

    if license_filter in ("cc", "royalty_free", "public_domain"):
        strategies.append(Strategy.STOCK_API)
        strategies.append(Strategy.WEB_SEARCH)
        return strategies

    if any(kw in query_lower for kw in STOCK_KEYWORDS):
        strategies.append(Strategy.STOCK_API)
        strategies.append(Strategy.WEB_SEARCH)
        return strategies

    if any(kw in query_lower for kw in ART_KEYWORDS):
        strategies.append(Strategy.GALLERY_DL)
        strategies.append(Strategy.WEB_SEARCH)
        return strategies

    strategies.append(Strategy.WEB_SEARCH)
    if any(kw in query_lower for kw in PHOTO_KEYWORDS):
        strategies.append(Strategy.STOCK_API)

    return strategies


def _classify_url(url: str) -> list[Strategy]:
    parsed = urlparse(url)
    host = parsed.hostname or ""

    if any(url.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")):
        return [Strategy.DIRECT_URL]

    if "drive.google.com" in host:
        return [Strategy.DRIVE]

    if any(host == h or host.endswith("." + h) for h in ART_HOSTS):
        return [Strategy.GALLERY_DL]

    return [Strategy.GENERIC_CRAWL]


def _map_explicit_sources(sources: list[str]) -> list[Strategy]:
    mapping = {
        "web": Strategy.WEB_SEARCH,
        "pexels": Strategy.STOCK_API,
        "wikimedia": Strategy.STOCK_API,
        "danbooru": Strategy.GALLERY_DL,
        "pixiv": Strategy.GALLERY_DL,
        "artstation": Strategy.GALLERY_DL,
        "reddit": Strategy.GALLERY_DL,
        "url": Strategy.GENERIC_CRAWL,
        "drive": Strategy.DRIVE,
        "browser": Strategy.BROWSER,
    }
    seen: set[Strategy] = set()
    result: list[Strategy] = []
    for s in sources:
        strategy = mapping.get(s, Strategy.WEB_SEARCH)
        if strategy not in seen:
            seen.add(strategy)
            result.append(strategy)
    return result
