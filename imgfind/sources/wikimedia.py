from __future__ import annotations

import httpx

from imgfind.models import Candidate, LicenseType
from imgfind.sources.base import Source

LICENSE_MAP: dict[str, LicenseType] = {
    "cc0": LicenseType.CC0,
    "cc-zero": LicenseType.CC0,
    "public domain": LicenseType.PUBLIC_DOMAIN,
    "pd": LicenseType.PUBLIC_DOMAIN,
    "cc-by": LicenseType.CC_BY,
    "cc-by-sa": LicenseType.CC_BY_SA,
}


def _parse_license(short_name: str) -> LicenseType:
    lower = short_name.lower().strip()
    for key, lt in LICENSE_MAP.items():
        if key in lower:
            return lt
    return LicenseType.UNKNOWN


class WikimediaSource(Source):
    name = "wikimedia"

    async def search(self, query: str, n: int = 20, **kwargs) -> list[Candidate]:
        candidates: list[Candidate] = []
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                "https://commons.wikimedia.org/w/api.php",
                params={
                    "action": "query",
                    "generator": "search",
                    "gsrsearch": f"filetype:bitmap {query}",
                    "gsrnamespace": "6",
                    "gsrlimit": min(n, 50),
                    "prop": "imageinfo",
                    "iiprop": "url|size|extmetadata|mime",
                    "format": "json",
                },
            )
            resp.raise_for_status()
            pages = resp.json().get("query", {}).get("pages", {})

            for page in pages.values():
                info = (page.get("imageinfo") or [{}])[0]
                ext = info.get("extmetadata", {})
                license_name = ext.get("LicenseShortName", {}).get("value", "")
                credit = ext.get("Credit", {}).get("value", "")
                artist = ext.get("Artist", {}).get("value", "")

                candidates.append(Candidate(
                    url=info.get("url", ""),
                    source=self.name,
                    source_page=info.get("descriptionurl", ""),
                    title=page.get("title", "").replace("File:", ""),
                    width=info.get("width", 0),
                    height=info.get("height", 0),
                    format=info.get("mime", "").split("/")[-1],
                    license=_parse_license(license_name),
                    attribution=credit or artist or "",
                    metadata={"license_name": license_name},
                ))

        return candidates[:n]
