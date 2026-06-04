from __future__ import annotations

import logging

from imgfind.models import Candidate, LicenseType
from imgfind.sources.base import Source

logger = logging.getLogger(__name__)


class BrowserSource(Source):
    name = "browser"

    def available(self) -> bool:
        try:
            import browser_use  # noqa: F401
            return True
        except ImportError:
            return False

    async def search(self, query: str, n: int = 20, **kwargs) -> list[Candidate]:
        url = kwargs.get("url", "")
        if not url:
            return []

        try:
            from browser_use import Agent
            from langchain_openai import ChatOpenAI

            llm = ChatOpenAI(model="gpt-4o-mini")
            task = (
                f"Go to {url} and find up to {n} high-quality images. "
                f"For each image, extract the direct image URL, any alt text or title, "
                f"and the approximate dimensions if visible. "
                f"Return the results as a JSON array of objects with keys: url, title, width, height."
            )
            agent = Agent(task=task, llm=llm)
            result = await agent.run()

            candidates: list[Candidate] = []
            if isinstance(result, list):
                for item in result[:n]:
                    if isinstance(item, dict) and item.get("url"):
                        candidates.append(Candidate(
                            url=item["url"],
                            source=self.name,
                            source_page=url,
                            title=item.get("title", ""),
                            width=item.get("width", 0),
                            height=item.get("height", 0),
                            license=LicenseType.UNKNOWN,
                        ))
            return candidates

        except Exception as e:
            logger.warning("browser-use failed for %s: %s", url, e)
            return []
