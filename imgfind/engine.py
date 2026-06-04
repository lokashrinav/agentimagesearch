from __future__ import annotations

import asyncio
import logging

from imgfind.config import config
from imgfind.models import Candidate, LicenseType, SearchResult, Strategy
from imgfind.ranking.pipeline import RankingPipeline
from imgfind.router import classify_query
from imgfind.sources.brave import BraveSource
from imgfind.sources.browser import BrowserSource
from imgfind.sources.crawl import CrawlSource
from imgfind.sources.drive import DriveSource
from imgfind.sources.gallery import GalleryDLSource
from imgfind.sources.pexels import PexelsSource
from imgfind.sources.serpapi import SerpAPISource
from imgfind.sources.wikimedia import WikimediaSource
from imgfind.storage.db import Database

logger = logging.getLogger(__name__)


async def discover(
    query: str,
    url: str | None = None,
    n: int | None = None,
    sources: list[str] | None = None,
    license_filter: str | None = None,
    min_resolution: int | None = None,
    skip_ranking: bool = False,
    skip_vision: bool = False,
    quality: bool = False,
    fast: bool = False,
) -> SearchResult:
    n = n or config.default_n
    if min_resolution:
        config.min_resolution = min_resolution

    strategies = classify_query(query, url=url, license_filter=license_filter, sources=sources)
    logger.info("Strategies: %s", [s.value for s in strategies])

    fetch_n = min(config.max_candidates, n * 5)

    tasks = []
    for strategy in strategies:
        tasks.extend(_build_tasks(strategy, query, url, fetch_n, license_filter))

    results = await asyncio.gather(*[t for t in tasks], return_exceptions=True)

    all_candidates: list[Candidate] = []
    errors: list[str] = []
    for result in results:
        if isinstance(result, Exception):
            errors.append(str(result))
            logger.warning("Source error: %s", result)
        elif isinstance(result, list):
            all_candidates.extend(result)

    logger.info("Collected %d raw candidates from %d sources", len(all_candidates), len(tasks))

    before = len(all_candidates)
    all_candidates = [c for c in all_candidates if not _is_unfetchable(c.url)]
    if len(all_candidates) < before:
        logger.info("Dropped %d unfetchable candidates (walled gardens)", before - len(all_candidates))

    if license_filter:
        all_candidates = _apply_license_preference(all_candidates, license_filter)

    if skip_ranking:
        ranked = all_candidates[:n]
    else:
        pipeline = RankingPipeline(
            skip_clip=fast,
            skip_aesthetic=not quality,
            skip_technical=True,
            skip_vision=skip_vision or fast,
            skip_dedup=fast,
        )
        ranked = await pipeline.rank(all_candidates, query)
        ranked = ranked[:n]

    db = Database()
    try:
        db.save_candidates(ranked, query)
    finally:
        db.close()

    return SearchResult(
        candidates=ranked,
        query=query,
        strategies_used=[s.value for s in strategies],
        total_found=len(all_candidates),
        errors=errors,
    )


async def auto_pick(
    query: str,
    url: str | None = None,
    n: int = 10,
    **kwargs,
) -> Candidate | None:
    result = await discover(query, url=url, n=n, **kwargs)
    if not result.candidates:
        return None

    top = result.candidates[0]

    if top.vision_score < config.auto_threshold:
        logger.info("Top candidate below auto threshold (%.1f < %.1f)", top.vision_score, config.auto_threshold)
        return None

    if len(result.candidates) > 1:
        margin = top.vision_score - result.candidates[1].vision_score
        if margin < config.auto_margin:
            logger.info("Margin too small (%.1f < %.1f)", margin, config.auto_margin)
            return None

    if top.license.requires_attribution and not top.attribution:
        logger.info("Top candidate requires attribution but none found, skipping auto-pick")
        return None

    return top


def _build_tasks(
    strategy: Strategy,
    query: str,
    url: str | None,
    n: int,
    license_filter: str | None,
) -> list:
    tasks = []
    kwargs: dict = {}
    if url:
        kwargs["url"] = url
    if license_filter:
        kwargs["license"] = license_filter

    if strategy == Strategy.WEB_SEARCH:
        serpapi = SerpAPISource()
        brave = BraveSource()
        if serpapi.available():
            tasks.append(serpapi.search(query, n, **kwargs))
        if brave.available():
            tasks.append(brave.search(query, n, **kwargs))

    elif strategy == Strategy.STOCK_API:
        for source_cls in [PexelsSource, WikimediaSource]:
            source = source_cls()
            if source.available():
                tasks.append(source.search(query, n, **kwargs))

    elif strategy == Strategy.GALLERY_DL:
        gdl = GalleryDLSource()
        if gdl.available():
            tasks.append(gdl.search(query, n, **kwargs))

    elif strategy == Strategy.DRIVE:
        drive = DriveSource()
        if drive.available() and url:
            tasks.append(drive.search(query, n, url=url))

    elif strategy == Strategy.GENERIC_CRAWL:
        crawl = CrawlSource()
        if url:
            tasks.append(crawl.search(query, n, url=url))

    elif strategy == Strategy.BROWSER:
        browser = BrowserSource()
        if browser.available() and url:
            tasks.append(browser.search(query, n, url=url))

    elif strategy == Strategy.DIRECT_URL:
        if url:
            tasks.append(_make_direct_candidate(url))

    return tasks


async def _make_direct_candidate(url: str) -> list[Candidate]:
    return [Candidate(url=url, source="direct", source_page=url)]


_UNFETCHABLE_HOSTS = {
    "lookaside.fbsbx.com",
    "lookaside.instagram.com",
    "scontent.cdninstagram.com",
    "scontent-",
    "fbcdn.net",
}


def _is_unfetchable(url: str) -> bool:
    from urllib.parse import urlparse
    host = urlparse(url).hostname or ""
    return any(host == h or host.endswith("." + h) or h in host for h in _UNFETCHABLE_HOSTS)


def _apply_license_preference(candidates: list[Candidate], license_filter: str) -> list[Candidate]:
    permissive = [c for c in candidates if c.license.is_permissive]
    other = [c for c in candidates if not c.license.is_permissive]
    return permissive + other
