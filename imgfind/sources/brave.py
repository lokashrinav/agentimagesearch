from __future__ import annotations

import httpx

from imgfind.config import config
from imgfind.models import Candidate, LicenseType
from imgfind.sources.base import Source


class BraveSource(Source):
    name = "brave"

    def available(self) -> bool:
        return bool(config.brave_key)

    async def search(self, query: str, n: int = 20, **kwargs) -> list[Candidate]:
        candidates: list[Candidate] = []
        async with httpx.AsyncClient(timeout=30) as client:
            headers = {
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": config.brave_key,
            }
            params = {"q": query, "count": min(n, 150)}
            resp = await client.get(
                "https://api.search.brave.com/res/v1/images/search",
                headers=headers,
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

            for result in data.get("results", [])[:n]:
                props = result.get("properties", {})
                candidates.append(Candidate(
                    url=props.get("url", result.get("url", "")),
                    source=self.name,
                    source_page=result.get("url", ""),
                    title=result.get("title", ""),
                    width=props.get("width", 0),
                    height=props.get("height", 0),
                    format=props.get("format", ""),
                    license=LicenseType.UNKNOWN,
                ))

        return candidates
