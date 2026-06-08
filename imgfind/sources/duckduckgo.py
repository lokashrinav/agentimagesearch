from __future__ import annotations

import asyncio
import logging
from functools import partial

from imgfind.models import Candidate, LicenseType
from imgfind.sources.base import Source

logger = logging.getLogger(__name__)


class DuckDuckGoSource(Source):
    name = "duckduckgo"

    def available(self) -> bool:
        try:
            import ddgs  # noqa: F401
            return True
        except ImportError:
            try:
                import duckduckgo_search  # noqa: F401
                return True
            except ImportError:
                return False

    async def search(self, query: str, n: int = 20, **kwargs) -> list[Candidate]:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS

        candidates: list[Candidate] = []
        loop = asyncio.get_running_loop()

        try:
            def _fetch() -> list[dict]:
                with DDGS() as ddgs:
                    return list(ddgs.images(query, max_results=n))

            results = await loop.run_in_executor(None, _fetch)
        except Exception:
            logger.exception("DuckDuckGo image search failed")
            return candidates

        for r in results[:n]:
            candidates.append(Candidate(
                url=r.get("image", ""),
                source=self.name,
                source_page=r.get("url", ""),
                title=r.get("title", ""),
                width=int(r.get("width", 0) or 0),
                height=int(r.get("height", 0) or 0),
                format=r.get("image", "").rsplit(".", 1)[-1][:4] if "." in r.get("image", "") else "",
                license=LicenseType.UNKNOWN,
            ))

        return candidates
