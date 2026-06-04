from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

app = typer.Typer(
    name="imgfind",
    help="Autonomous image discovery and retrieval agent.",
    no_args_is_help=True,
)


def _run(coro):
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(coro)


@app.command()
def search(
    query: str = typer.Argument(..., help="Natural-language image query"),
    url: Optional[str] = typer.Option(None, "--url", "-u", help="URL to crawl/traverse"),
    n: int = typer.Option(10, "--n", "-n", help="Number of results"),
    sources: Optional[str] = typer.Option(None, "--sources", "-s", help="Comma-separated sources (auto,web,pexels,wikimedia,danbooru,pixiv,drive,url)"),
    license: Optional[str] = typer.Option(None, "--license", "-l", help="License filter (any,cc,royalty_free,public_domain)"),
    min_res: int = typer.Option(1024, "--min-res", help="Minimum resolution (long edge px)"),
    fast: bool = typer.Option(False, "--fast", help="Skip ML ranking, resolution filter only"),
    no_vision: bool = typer.Option(False, "--no-vision", help="Skip vision LLM re-ranking"),
    output_json: bool = typer.Option(False, "--json", help="Output as JSON"),
    grid: bool = typer.Option(False, "--grid", help="Open grid UI in browser"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Search for images matching a query across multiple sources."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    from imgfind.config import config
    config.min_resolution = min_res

    from imgfind.engine import discover

    source_list = sources.split(",") if sources else None
    result = _run(discover(
        query=query,
        url=url,
        n=n,
        sources=source_list,
        license_filter=license,
        min_resolution=min_res,
        skip_ranking=fast,
        skip_vision=no_vision,
        fast=fast,
    ))

    if output_json:
        out = {
            "query": result.query,
            "strategies": result.strategies_used,
            "total_found": result.total_found,
            "candidates": [c.to_dict() for c in result.candidates],
            "errors": result.errors,
        }
        typer.echo(json.dumps(out, indent=2))
        return

    if grid:
        from imgfind.ui.server import run_server
        run_server(result.candidates, query)
        return

    from imgfind.ui.terminal import print_shortlist
    typer.echo(f"\n  Found {result.total_found} candidates, showing top {len(result.candidates)}")
    typer.echo(f"  Strategies: {', '.join(result.strategies_used)}")
    if result.errors:
        for err in result.errors:
            typer.echo(f"  Warning: {err}", err=True)
    print_shortlist(result.candidates, verbose=verbose)


@app.command()
def from_url(
    url: str = typer.Argument(..., help="URL to extract images from"),
    n: int = typer.Option(20, "--n", "-n"),
    fast: bool = typer.Option(False, "--fast"),
    output_json: bool = typer.Option(False, "--json"),
    grid: bool = typer.Option(False, "--grid"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Extract and rank images from a specific URL."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    from imgfind.engine import discover

    result = _run(discover(
        query=url,
        url=url,
        n=n,
        skip_ranking=fast,
        fast=fast,
    ))

    if output_json:
        typer.echo(json.dumps({
            "url": url,
            "candidates": [c.to_dict() for c in result.candidates],
        }, indent=2))
        return

    if grid:
        from imgfind.ui.server import run_server
        run_server(result.candidates, url)
        return

    from imgfind.ui.terminal import print_shortlist
    typer.echo(f"\n  Extracted {len(result.candidates)} images from {url}")
    print_shortlist(result.candidates, verbose=verbose)


@app.command()
def fetch(
    candidate_id: str = typer.Argument(..., help="Candidate ID to download"),
    out: Path = typer.Option(Path("assets"), "--out", "-o", help="Output directory"),
    width: Optional[int] = typer.Option(None, "--width", "-w", help="Target width (px)"),
    fmt: str = typer.Option("webp", "--format", "-f", help="Output format (webp,png,jpg)"),
):
    """Download and optimize a specific candidate by ID."""
    from imgfind.storage.assets import AssetManager
    from imgfind.storage.db import Database

    db = Database()
    candidate = db.get_candidate(candidate_id)
    db.close()

    if not candidate:
        typer.echo(f"  Candidate {candidate_id} not found in database", err=True)
        raise typer.Exit(1)

    manager = AssetManager(out)
    path = _run(manager.download_and_optimize(candidate, target_width=width, fmt=fmt))

    if path:
        typer.echo(f"  Saved: {path}")
    else:
        typer.echo("  Download failed", err=True)
        raise typer.Exit(1)


@app.command()
def auto(
    query: str = typer.Argument(..., help="Image query"),
    url: Optional[str] = typer.Option(None, "--url", "-u"),
    out: Path = typer.Option(Path("assets"), "--out", "-o"),
    width: Optional[int] = typer.Option(None, "--width", "-w"),
    fmt: str = typer.Option("webp", "--format", "-f"),
    threshold: float = typer.Option(8.0, "--threshold", "-t", help="Auto-pick confidence threshold"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Autonomous mode: search, rank, pick, download in one shot."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    from imgfind.config import config
    config.auto_threshold = threshold

    from imgfind.engine import auto_pick

    candidate = _run(auto_pick(query, url=url))

    if not candidate:
        typer.echo("  No candidate met the auto-pick threshold. Run 'imgfind search' for manual selection.")
        raise typer.Exit(1)

    typer.echo(f"  Auto-picked: {candidate.title or candidate.id}")
    typer.echo(f"  Score: {candidate.vision_score:.1f} | License: {candidate.license.value}")

    if candidate.license.requires_attribution:
        typer.echo(f"  Attribution required: {candidate.attribution}")

    from imgfind.storage.assets import AssetManager
    manager = AssetManager(out)
    path = _run(manager.download_and_optimize(candidate, target_width=width, fmt=fmt))

    if path:
        typer.echo(f"  Saved: {path}")
    else:
        typer.echo("  Download failed", err=True)
        raise typer.Exit(1)


@app.command()
def rank(
    directory: Path = typer.Argument(..., help="Directory of images to rank"),
    query: str = typer.Option("", "--query", "-q", help="Query for relevance scoring"),
    output_json: bool = typer.Option(False, "--json"),
):
    """Rank local images in a directory."""
    from imgfind.models import Candidate

    if not directory.is_dir():
        typer.echo(f"  {directory} is not a directory", err=True)
        raise typer.Exit(1)

    exts = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
    files = [f for f in directory.iterdir() if f.suffix.lower() in exts]

    if not files:
        typer.echo("  No image files found")
        raise typer.Exit(1)

    candidates = [
        Candidate(
            url=f"file:///{f.resolve()}",
            source="local",
            title=f.name,
        )
        for f in files
    ]

    from imgfind.ranking.pipeline import RankingPipeline
    pipeline = RankingPipeline(skip_vision=True)
    ranked = _run(pipeline.rank(candidates, query or "high quality image"))

    if output_json:
        typer.echo(json.dumps([c.to_dict() for c in ranked], indent=2))
    else:
        from imgfind.ui.terminal import print_shortlist
        print_shortlist(ranked, verbose=True)


@app.command()
def tune():
    """Tune blend weights from preference feedback."""
    from imgfind.feedback import tune_weights
    from imgfind.storage.db import Database

    db = Database()
    result = tune_weights(db)
    db.close()

    if result:
        typer.echo(f"  Updated weights: {json.dumps(result)}")
    else:
        typer.echo("  Not enough preference data yet. Use the grid UI to pick candidates first.")


if __name__ == "__main__":
    app()
