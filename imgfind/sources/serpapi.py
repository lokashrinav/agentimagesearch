from __future__ import annotations

import httpx

from imgfind.config import config
from imgfind.models import Candidate, LicenseType
from imgfind.sources.base import Source


class SerpAPISource(Source):
    name = "serpapi"

    def available(self) -> bool:
        return bool(config.serpapi_key)

    async def search(self, query: str, n: int = 20, **kwargs) -> list[Candidate]:
        candidates: list[Candidate] = []
        async with httpx.AsyncClient(timeout=30) as client:
            params = {
                "engine": "google_images",
                "q": query,
                "num": min(n, 100),
                "api_key": config.serpapi_key,
                "ijn": "0",
            }
            if kwargs.get("license") in ("cc", "royalty_free"):
                params["tbs"] = "il:cl"

            resp = await client.get("https://serpapi.com/search.json", params=params)
            resp.raise_for_status()
            data = resp.json()

            for img in data.get("images_results", [])[:n]:
                candidates.append(Candidate(
                    url=img.get("original", img.get("thumbnail", "")),
                    source=self.name,
                    source_page=img.get("link", ""),
                    title=img.get("title", ""),
                    width=img.get("original_width", 0),
                    height=img.get("original_height", 0),
                    license=LicenseType.UNKNOWN,
                ))

        return candidates
