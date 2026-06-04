from __future__ import annotations

from abc import ABC, abstractmethod

from imgfind.models import Candidate


class Source(ABC):
    name: str = "base"

    @abstractmethod
    async def search(self, query: str, n: int = 20, **kwargs) -> list[Candidate]:
        ...

    def available(self) -> bool:
        return True
