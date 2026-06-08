"""
imgfind Python API for programmatic use by AI agents.

Usage:
    from imgfind import search

    results = await search("Gojo Satoru", google=["digital art", "transparent PNG"])
    grid_path = results["grid_image"]
    candidates = results["candidate_map"]
"""
from __future__ import annotations

import asyncio
import os
from typing import Any

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

from imgfind.config import config
from imgfind.models import Candidate
from imgfind.sources.serpapi import SerpAPISource
from imgfind.sources.brave import BraveSource
from imgfind.sources.pexels import PexelsSource
from imgfind.sources.wikimedia import WikimediaSource
from imgfind.sources.gallery import GalleryDLSource
from imgfind.ranking.grid_rerank import _download_thumb, _build_grid, LABELS


async def search(
    query: str,
    google: list[str] | None = None,
    brave: list[str] | None = None,
    danbooru: list[str] | None = None,
    pexels: list[str] | None = None,
    wikimedia: list[str] | None = None,
    duckduckgo: list[str] | None = None,
    n: int = 10,
    output_dir: str | None = None,
) -> dict[str, Any]:
    fetch_n = min(config.max_candidates, n * 5)

    backend_queries: dict[str, list[str]] = {}
    if google:
        backend_queries["google"] = google
    if brave:
        backend_queries["brave"] = brave
    if danbooru:
        backend_queries["danbooru"] = danbooru
    if pexels:
        backend_queries["pexels"] = pexels
    if wikimedia:
        backend_queries["wikimedia"] = wikimedia
    if duckduckgo:
        backend_queries["duckduckgo"] = duckduckgo

    backends = {
        "google": (SerpAPISource, "serpapi"),
        "brave": (BraveSource, "brave"),
        "pexels": (PexelsSource, "pexels"),
        "wikimedia": (WikimediaSource, "wikimedia"),
        "danbooru": (GalleryDLSource, "gallery-dl"),
    }

    try:
        from imgfind.sources.duckduckgo import DuckDuckGoSource
        backends["duckduckgo"] = (DuckDuckGoSource, "duckduckgo")
    except ImportError:
        pass

    candidates: list[Candidate] = []
    errors: list[str] = []
    source_tasks: list[tuple[str, object]] = []

    if backend_queries:
        for name, queries in backend_queries.items():
            if name not in backends:
                continue
            cls, label = backends[name]
            source = cls()
            if source.available():
                for q in queries:
                    source_tasks.append((label, source.search(q, fetch_n)))
    else:
        for name, (cls, label) in backends.items():
            source = cls()
            if source.available():
                source_tasks.append((label, source.search(query, fetch_n)))

    results = await asyncio.gather(
        *[t for _, t in source_tasks], return_exceptions=True
    )

    for (name, _), result in zip(source_tasks, results):
        if isinstance(result, Exception):
            errors.append(f"{name}: {result}")
        elif isinstance(result, list):
            candidates.extend(result)

    seen_urls: set[str] = set()
    deduped: list[Candidate] = []
    for c in candidates:
        if c.url not in seen_urls:
            seen_urls.add(c.url)
            deduped.append(c)
    candidates = deduped

    grid_k = min(len(candidates), 10, len(LABELS))
    if grid_k < 2:
        return {
            "status": "error",
            "message": f"Only {len(candidates)} candidates found, need at least 2",
            "candidates": candidates,
            "errors": errors,
        }

    images = []
    label_to_candidate: dict[str, dict] = {}
    for i, c in enumerate(candidates[:grid_k]):
        label = LABELS[i]
        img = await _download_thumb(c.url)
        if img:
            images.append((label, img))
            label_to_candidate[label] = {
                "url": c.url,
                "source": c.source,
                "title": c.title,
                "width": c.width,
                "height": c.height,
            }

    if len(images) < 2:
        return {
            "status": "error",
            "message": "Could not download enough images",
            "candidates": candidates,
            "errors": errors,
        }

    grid_bytes = _build_grid(images)
    out_dir = output_dir or os.path.join(os.path.dirname(os.path.dirname(__file__)), ".imgfind_output")
    os.makedirs(out_dir, exist_ok=True)

    grid_path = os.path.join(out_dir, "grid.jpg")
    with open(grid_path, "wb") as f:
        f.write(grid_bytes)

    import json
    meta_path = os.path.join(out_dir, "candidates.json")
    with open(meta_path, "w") as f:
        json.dump(label_to_candidate, f, indent=2)

    all_path = os.path.join(out_dir, "all_candidates.json")
    with open(all_path, "w") as f:
        json.dump([c.to_dict() for c in candidates], f, indent=2)

    return {
        "status": "ready",
        "grid_image": grid_path,
        "grid_bytes": grid_bytes,
        "candidates_file": meta_path,
        "all_candidates_file": all_path,
        "labels": [l for l, _ in images],
        "candidate_map": label_to_candidate,
        "all_candidates": candidates,
        "total_found": len(candidates),
        "errors": errors,
    }
