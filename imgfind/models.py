from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class LicenseType(str, Enum):
    UNKNOWN = "unknown"
    CC_BY = "cc-by"
    CC_BY_SA = "cc-by-sa"
    CC_BY_NC = "cc-by-nc"
    CC0 = "cc0"
    PUBLIC_DOMAIN = "public_domain"
    ROYALTY_FREE = "royalty_free"
    COPYRIGHTED = "copyrighted"
    UNSPLASH = "unsplash"
    PEXELS = "pexels"

    @property
    def is_permissive(self) -> bool:
        return self in {
            LicenseType.CC0,
            LicenseType.PUBLIC_DOMAIN,
            LicenseType.ROYALTY_FREE,
            LicenseType.UNSPLASH,
            LicenseType.PEXELS,
            LicenseType.CC_BY,
        }

    @property
    def requires_attribution(self) -> bool:
        return self in {
            LicenseType.CC_BY,
            LicenseType.CC_BY_SA,
            LicenseType.CC_BY_NC,
            LicenseType.UNSPLASH,
            LicenseType.PEXELS,
        }


class Strategy(str, Enum):
    WEB_SEARCH = "web_search"
    GALLERY_DL = "gallery_dl"
    STOCK_API = "stock_api"
    DRIVE = "drive"
    GENERIC_CRAWL = "generic_crawl"
    BROWSER = "browser"
    DIRECT_URL = "direct_url"


@dataclass
class Candidate:
    url: str
    source: str
    source_page: str = ""
    title: str = ""
    width: int = 0
    height: int = 0
    format: str = ""
    license: LicenseType = LicenseType.UNKNOWN
    attribution: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    relevance_score: float = 0.0
    aesthetic_score: float = 0.0
    technical_score: float = 0.0
    vision_score: float = 0.0
    vision_rationale: str = ""
    composite_score: float = 0.0
    phash: str = ""

    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            import hashlib
            self.id = hashlib.sha256(self.url.encode()).hexdigest()[:12]

    def megapixels(self) -> float:
        if self.width and self.height:
            return (self.width * self.height) / 1_000_000
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "url": self.url,
            "source": self.source,
            "source_page": self.source_page,
            "title": self.title,
            "width": self.width,
            "height": self.height,
            "format": self.format,
            "license": self.license.value,
            "attribution": self.attribution,
            "scores": {
                "relevance": round(self.relevance_score, 4),
                "aesthetic": round(self.aesthetic_score, 4),
                "technical": round(self.technical_score, 4),
                "vision": round(self.vision_score, 4),
                "composite": round(self.composite_score, 4),
            },
            "vision_rationale": self.vision_rationale,
            "metadata": self.metadata,
        }


@dataclass
class SearchResult:
    candidates: list[Candidate]
    query: str
    strategies_used: list[str]
    total_found: int = 0
    errors: list[str] = field(default_factory=list)
