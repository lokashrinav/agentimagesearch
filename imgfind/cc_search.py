"""Claude Code / AI agent CLI entry point.

Usage:
    python -m imgfind.cc_search --query "Sans Undertale" [--google "..." "..."] [--brave "..." "..."] [--danbooru "..." "..."] [--duckduckgo "..." "..."] [--pexels "..."] [--wikimedia "..."]

Per-backend queries are optional. If provided, only those backends are hit.
Each backend flag accepts multiple queries — all run in parallel and results are pooled.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from imgfind.search import search


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True, help="Original user query")
    parser.add_argument("--google", nargs="+", help="Google/SerpAPI search queries")
    parser.add_argument("--brave", nargs="+", help="Brave search queries")
    parser.add_argument("--danbooru", nargs="+", help="Danbooru tag queries")
    parser.add_argument("--duckduckgo", nargs="+", help="DuckDuckGo search queries (free, no API key)")
    parser.add_argument("--pexels", nargs="+", help="Pexels search queries")
    parser.add_argument("--wikimedia", nargs="+", help="Wikimedia search queries")
    parser.add_argument("--n", type=int, default=10)
    args = parser.parse_args()

    kwargs = {}
    if args.google:
        kwargs["google"] = args.google
    if args.brave:
        kwargs["brave"] = args.brave
    if args.danbooru:
        kwargs["danbooru"] = args.danbooru
    if args.duckduckgo:
        kwargs["duckduckgo"] = args.duckduckgo
    if args.pexels:
        kwargs["pexels"] = args.pexels
    if args.wikimedia:
        kwargs["wikimedia"] = args.wikimedia

    result = asyncio.run(search(args.query, n=args.n, **kwargs))

    output = {k: v for k, v in result.items() if k not in ("grid_bytes", "all_candidates")}
    print(json.dumps(output, default=str))


if __name__ == "__main__":
    main()


