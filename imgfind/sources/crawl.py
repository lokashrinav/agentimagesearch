from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

import httpx

from imgfind.models import Candidate, LicenseType
from imgfind.sources.base import Source

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".svg"}


def _looks_like_image_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in IMAGE_EXTENSIONS)


def _extract_image_urls_from_html(html: str, base_url: str) -> list[dict]:
    images: list[dict] = []
    seen = set()

    for match in re.finditer(
        r'<img[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE
    ):
        src = urljoin(base_url, match.group(1))
        if src not in seen and not src.startswith("data:"):
            seen.add(src)
            alt = ""
            alt_match = re.search(r'alt=["\']([^"\']*)["\']', match.group(0), re.IGNORECASE)
            if alt_match:
                alt = alt_match.group(1)
            width, height = 0, 0
            w_match = re.search(r'width=["\']?(\d+)', match.group(0), re.IGNORECASE)
            h_match = re.search(r'height=["\']?(\d+)', match.group(0), re.IGNORECASE)
            if w_match:
                width = int(w_match.group(1))
            if h_match:
                height = int(h_match.group(1))
            images.append({"url": src, "alt": alt, "width": width, "height": height})

    for match in re.finditer(
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        html, re.IGNORECASE,
    ):
        src = urljoin(base_url, match.group(1))
        if src not in seen:
            seen.add(src)
            images.insert(0, {"url": src, "alt": "", "width": 0, "height": 0})

    return images


class CrawlSource(Source):
    name = "crawl"

    async def search(self, query: str, n: int = 20, **kwargs) -> list[Candidate]:
        url = kwargs.get("url", query)
        if not url.startswith("http"):
            return []

        try:
            return await self._crawl4ai(url, n)
        except ImportError:
            return await self._fallback_crawl(url, n)

    async def _crawl4ai(self, url: str, n: int) -> list[Candidate]:
        from crawl4ai import AsyncWebCrawler

        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url)

        candidates: list[Candidate] = []
        for img in (result.media.get("images", []) if result.media else [])[:n]:
            candidates.append(Candidate(
                url=img.get("src", ""),
                source=self.name,
                source_page=url,
                title=img.get("alt", ""),
                license=LicenseType.UNKNOWN,
            ))
        return candidates

    async def _fallback_crawl(self, url: str, n: int) -> list[Candidate]:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "imgfind/0.1"})
            resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if "image/" in content_type or _looks_like_image_url(url):
            return [Candidate(url=url, source=self.name, source_page=url)]

        if "text/html" not in content_type:
            return []

        images = _extract_image_urls_from_html(resp.text, str(resp.url))
        candidates: list[Candidate] = []
        for img in images[:n]:
            if _looks_like_image_url(img["url"]) or img["width"] > 100:
                candidates.append(Candidate(
                    url=img["url"],
                    source=self.name,
                    source_page=url,
                    title=img.get("alt", ""),
                    width=img.get("width", 0),
                    height=img.get("height", 0),
                    license=LicenseType.UNKNOWN,
                ))
        return candidates
