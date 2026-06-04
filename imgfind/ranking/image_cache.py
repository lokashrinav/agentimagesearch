from __future__ import annotations

import asyncio
import io
import logging

import httpx
from PIL import Image

logger = logging.getLogger(__name__)

_cache: dict[str, Image.Image | None] = {}


def clear():
    _cache.clear()


async def prefetch(urls: list[str], max_concurrent: int = 10) -> None:
    """Download all URLs concurrently and populate the cache."""
    new_urls = [u for u in urls if u not in _cache]
    if not new_urls:
        return

    sem = asyncio.Semaphore(max_concurrent)

    async def _download(client: httpx.AsyncClient, url: str) -> None:
        async with sem:
            try:
                resp = await client.get(url, headers={"User-Agent": "imgfind/0.1"})
                resp.raise_for_status()
                img = Image.open(io.BytesIO(resp.content)).convert("RGB")
                _cache[url] = img
            except Exception as e:
                logger.debug("Failed to download %s: %s", url, e)
                _cache[url] = None

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        await asyncio.gather(*[_download(client, u) for u in new_urls])

    logger.info("Prefetched %d images (%d new)", len(urls), len(new_urls))


async def get(url: str) -> Image.Image | None:
    if url in _cache:
        return _cache[url]

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "imgfind/0.1"})
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content)).convert("RGB")
            _cache[url] = img
            return img
    except Exception as e:
        logger.debug("Failed to download %s: %s", url, e)
        _cache[url] = None
        return None
