from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    serpapi_key: str = field(default_factory=lambda: os.environ.get("SERPAPI_API_KEY", ""))
    brave_key: str = field(default_factory=lambda: os.environ.get("BRAVE_API_KEY", ""))
    pexels_key: str = field(default_factory=lambda: os.environ.get("PEXELS_API_KEY", ""))
    anthropic_key: str = field(default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", ""))
    google_api_key: str = field(default_factory=lambda: os.environ.get("GOOGLE_API_KEY", ""))

    db_path: Path = field(default_factory=lambda: Path.home() / ".imgfind" / "imgfind.db")
    assets_dir: Path = field(default_factory=lambda: Path("assets"))

    clip_model: str = "ViT-B-32"
    clip_pretrained: str = "laion2b_s34b_b79k"
    aesthetic_threshold: float = 5.5
    relevance_floor: float = 0.2
    dedup_threshold: int = 8
    auto_threshold: float = 8.0
    auto_margin: float = 1.0

    max_candidates: int = 50
    top_k_rerank: int = 10
    default_n: int = 10
    min_resolution: int = 1024

    blend_weights: dict[str, float] = field(default_factory=lambda: {
        "relevance": 0.5,
        "aesthetic": 0.3,
        "technical": 0.2,
    })

    ui_port: int = 8777

    def ensure_dirs(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)


config = Config()
