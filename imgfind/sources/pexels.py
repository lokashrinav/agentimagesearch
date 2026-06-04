from __future__ import annotations

import httpx

from imgfind.config import config
from imgfind.models import Candidate, LicenseType
from imgfind.sources.base import Source


class PexelsSource(Source):
    name = "pexels"

    def available(self) -> bool:
        return bool(config.pexels_key)

    async def search(self, query: str, n: int = 20, **kwargs) -> list[Candidate]:
        candidates: list[Candidate] = []
        async with httpx.AsyncClient(timeout=30) as client:
            headers = {"Authorization": config.pexels_key}
            per_page = min(n, 80)
            pages_needed = (n + per_page - 1) // per_page

            for page in range(1, pages_needed + 1):
                resp = await client.get(
                    "https://api.pexels.com/v1/search",
                    headers=headers,
                    params={"query": query, "per_page": per_page, "page": page},
                )
                resp.raise_for_status()
                data = resp.json()

                for photo in data.get("photos", []):
                    src = photo.get("src", {})
                    candidates.append(Candidate(
                        url=src.get("original", ""),
                        source=self.name,
                        source_page=photo.get("url", ""),
                        title=photo.get("alt", ""),
                        width=photo.get("width", 0),
                        height=photo.get("height", 0),
                        license=LicenseType.PEXELS,
                        attribution=f"Photo by {photo.get('photographer', 'Unknown')} on Pexels",
                        metadata={
                            "photographer_url": photo.get("photographer_url", ""),
                            "avg_color": photo.get("avg_color", ""),
                        },
                    ))

                if not data.get("next_page"):
                    break

        return candidates[:n]
