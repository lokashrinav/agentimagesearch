from __future__ import annotations

import io
import logging

import httpx
from PIL import Image

logger = logging.getLogger(__name__)

_cache: dict[str, Image.Image | None] = {}


def clear():
    _cache.clear()


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
