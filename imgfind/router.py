from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
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

FICTIONAL_KEYWORDS = {
    "anime", "manga", "fanart", "fan art", "character", "waifu",
    "undertale", "genshin", "jujutsu", "naruto", "one piece",
    "pokemon", "zelda", "mario", "sonic", "oc",
}

_BOORU_TAG_MAP = {
    "pixel art": "pixel_art",
    "transparent background": "transparent_background",
    "white background": "white_background",
    "simple background": "simple_background",
    "black background": "black_background",
    "high resolution": "highres",
    "high res": "highres",
    "hd": "highres",
    "solo": "solo",
    "full body": "full_body",
    "upper body": "upper_body",
    "close-up": "close-up",
    "portrait": "upper_body",
    "profile picture": "upper_body solo",
    "pfp": "upper_body solo",
    "wallpaper": "highres absurdres",
    "thumbnail": "highres",
    "screenshot": "screencap",
    "meme": "meme",
}

_NEGATIVE_PATTERNS = [
    (r"not?\s+pixel\s*art", "-pixel_art"),
    (r"not?\s+a?\s*screenshot", "-screencap"),
    (r"not?\s+a?\s*meme", "-meme"),
    (r"not?\s+pixel", "-pixel_art"),
    (r"not?\s+blurry", "-blurry"),
    (r"not?\s+low\s*(?:res|quality)", "-lowres"),
]


@dataclass
class SearchRoute:
    strategies: list[Strategy]
    queries: dict[str, str | None] = field(default_factory=dict)


def classify_query(
    query: str,
    url: str | None = None,
    license_filter: str | None = None,
    sources: list[str] | None = None,
) -> list[Strategy]:
    return route_query(query, url=url, license_filter=license_filter, sources=sources).strategies


def route_query(
    query: str,
    url: str | None = None,
    license_filter: str | None = None,
    sources: list[str] | None = None,
) -> SearchRoute:
    if sources and sources != ["auto"]:
        strategies = _map_explicit_sources(sources)
        return SearchRoute(strategies=strategies, queries=_format_queries(query, strategies))

    if url:
        strategies = _classify_url(url)
        if strategies:
            return SearchRoute(strategies=strategies, queries=_format_queries(query, strategies))

    query_lower = query.lower()
    strategies: list[Strategy] = []

    if license_filter in ("cc", "royalty_free", "public_domain"):
        strategies = [Strategy.STOCK_API, Strategy.WEB_SEARCH]
    elif any(kw in query_lower for kw in STOCK_KEYWORDS):
        strategies = [Strategy.STOCK_API, Strategy.WEB_SEARCH]
    elif any(kw in query_lower for kw in ART_KEYWORDS):
        strategies = [Strategy.GALLERY_DL, Strategy.WEB_SEARCH]
    else:
        strategies = [Strategy.WEB_SEARCH]
        if any(kw in query_lower for kw in PHOTO_KEYWORDS):
            strategies.append(Strategy.STOCK_API)

    queries = _format_queries(query, strategies)
    return SearchRoute(strategies=strategies, queries=queries)


def _format_queries(query: str, strategies: list[Strategy]) -> dict[str, str | None]:
    query_lower = query.lower()
    is_fictional = any(kw in query_lower for kw in FICTIONAL_KEYWORDS)

    queries: dict[str, str | None] = {}

    if Strategy.WEB_SEARCH in strategies:
        queries["serpapi"] = _format_web_query(query)
        queries["brave"] = _format_web_query(query)

    if Strategy.STOCK_API in strategies:
        queries["pexels"] = None if is_fictional else _strip_negations(query)
        queries["wikimedia"] = None if is_fictional else _strip_negations(query)

    if Strategy.GALLERY_DL in strategies:
        queries["gallery-dl"] = _format_booru_query(query)

    return queries


def _format_web_query(query: str) -> str:
    cleaned = re.sub(r'\b(?:not?|don\'t|without|exclude)\s+\w+', '', query, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned or query


def _format_booru_query(query: str) -> str:
    query_lower = query.lower()

    tags: list[str] = []
    negative_tags: list[str] = []
    remaining = query_lower

    for pattern, neg_tag in _NEGATIVE_PATTERNS:
        match = re.search(pattern, remaining)
        if match:
            negative_tags.append(neg_tag)
            remaining = remaining[:match.start()] + remaining[match.end():]

    for phrase, tag in sorted(_BOORU_TAG_MAP.items(), key=lambda x: -len(x[0])):
        if phrase in remaining:
            tags.extend(tag.split())
            remaining = remaining.replace(phrase, "")

    remaining = re.sub(r'\b(?:for|a|an|the|my|i\s+need|find\s+me|get\s+me|image|picture|photo)\b',
                       '', remaining, flags=re.IGNORECASE)
    remaining = re.sub(r'[,.]', ' ', remaining)

    core_words = [w.strip() for w in remaining.split() if len(w.strip()) > 1]
    core_tags = ["_".join(core_words)] if core_words else []

    all_tags = core_tags + list(dict.fromkeys(tags)) + list(dict.fromkeys(negative_tags))
    return " ".join(all_tags)


def _strip_negations(query: str) -> str:
    cleaned = re.sub(r'\b(?:not?|don\'t|without|exclude)\s+\w+', '', query, flags=re.IGNORECASE)
    cleaned = re.sub(r'\b(?:for|a|an|the|my)\b', '', cleaned, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', cleaned).strip()


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
