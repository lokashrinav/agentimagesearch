"""Claude Code entry point.

Usage:
    python -m imgfind.cc_search --query "Sans Undertale" [--google "..." "..."] [--brave "..." "..."] [--danbooru "..." "..."] [--pexels "..."] [--wikimedia "..."]

Per-backend queries are optional. If provided, only those backends are hit.
Each backend flag accepts multiple queries — all run in parallel and results are pooled.
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

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



async def run(query: str, backend_queries: dict[str, list[str]], n: int) -> None:
    fetch_n = min(config.max_candidates, n * 5)

    candidates: list[Candidate] = []
    errors: list[str] = []
    source_tasks: list[tuple[str, object]] = []

    backends = {
        "google": (SerpAPISource, "serpapi"),
        "brave": (BraveSource, "brave"),
        "pexels": (PexelsSource, "pexels"),
        "wikimedia": (WikimediaSource, "wikimedia"),
        "danbooru": (GalleryDLSource, "gallery-dl"),
    }

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

    print(json.dumps({
        "status": "searching",
        "sources_hit": [name for name, _ in source_tasks],
        "queries_used": backend_queries if backend_queries else {"all": [query]},
        "total_candidates": len(candidates),
        "errors": errors,
    }))

    grid_k = min(len(candidates), 10, len(LABELS))
    if grid_k < 2:
        print(json.dumps({"status": "error", "message": f"Only {len(candidates)} candidates found, need at least 2"}))
        return

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
        print(json.dumps({"status": "error", "message": "Could not download enough images"}))
        return

    grid_bytes = _build_grid(images)
    out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".imgfind_output")
    os.makedirs(out_dir, exist_ok=True)

    grid_path = os.path.join(out_dir, "grid.jpg")
    with open(grid_path, "wb") as f:
        f.write(grid_bytes)

    meta_path = os.path.join(out_dir, "candidates.json")
    with open(meta_path, "w") as f:
        json.dump(label_to_candidate, f, indent=2)

    all_path = os.path.join(out_dir, "all_candidates.json")
    with open(all_path, "w") as f:
        json.dump([c.to_dict() for c in candidates], f, indent=2)

    print(json.dumps({
        "status": "ready",
        "grid_image": grid_path,
        "candidates_file": meta_path,
        "all_candidates_file": all_path,
        "labels": [l for l, _ in images],
        "candidate_map": label_to_candidate,
    }))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True, help="Original user query")
    parser.add_argument("--google", nargs="+", help="Google/SerpAPI search queries")
    parser.add_argument("--brave", nargs="+", help="Brave search queries")
    parser.add_argument("--danbooru", nargs="+", help="Danbooru tag queries")
    parser.add_argument("--pexels", nargs="+", help="Pexels search queries")
    parser.add_argument("--wikimedia", nargs="+", help="Wikimedia search queries")
    parser.add_argument("--n", type=int, default=10)
    args = parser.parse_args()

    backend_queries: dict[str, list[str]] = {}
    if args.google:
        backend_queries["google"] = args.google
    if args.brave:
        backend_queries["brave"] = args.brave
    if args.danbooru:
        backend_queries["danbooru"] = args.danbooru
    if args.pexels:
        backend_queries["pexels"] = args.pexels
    if args.wikimedia:
        backend_queries["wikimedia"] = args.wikimedia

    asyncio.run(run(args.query, backend_queries, args.n))


if __name__ == "__main__":
    main()
