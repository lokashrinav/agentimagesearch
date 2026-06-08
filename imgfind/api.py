"""
FastAPI server exposing imgfind image search as a hosted API.

Run with:
    python -m imgfind.api
    uvicorn imgfind.api:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import os
import tempfile
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from imgfind import __version__

app = FastAPI(
    title="agentimagesearch",
    description="Image search for AI agents that actually see what they recommend.",
    version=__version__,
)

# Temp directory for per-search grid storage
_GRID_STORE = os.path.join(tempfile.gettempdir(), "imgfind_grids")
os.makedirs(_GRID_STORE, exist_ok=True)

# Track the latest search ID so GET /grid can serve it
_latest_search_id: str | None = None


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    query: str
    google: list[str] | None = None
    duckduckgo: list[str] | None = None
    danbooru: list[str] | None = None
    brave: list[str] | None = None
    pexels: list[str] | None = None
    wikimedia: list[str] | None = None
    n: int = Field(default=10, ge=1, le=50)


class CandidateInfo(BaseModel):
    url: str
    source: str
    title: str
    width: int
    height: int


class SearchResponse(BaseModel):
    search_id: str
    status: str
    candidate_map: dict[str, CandidateInfo]
    labels: list[str]
    grid_url: str
    total_found: int
    errors: list[str]


class ErrorResponse(BaseModel):
    search_id: str
    status: str
    message: str
    errors: list[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
async def root() -> dict[str, Any]:
    return {
        "service": "agentimagesearch",
        "version": __version__,
        "endpoints": {
            "POST /search": "Run an image search across multiple backends",
            "GET /grid": "Serve the latest grid image as JPEG",
            "GET /grid/{search_id}": "Serve a specific grid image by search ID",
        },
    }


@app.post("/search", response_model=SearchResponse | ErrorResponse)
async def run_search(req: SearchRequest) -> JSONResponse:
    global _latest_search_id

    from imgfind.search import search

    search_id = uuid4().hex
    output_dir = os.path.join(_GRID_STORE, search_id)
    os.makedirs(output_dir, exist_ok=True)

    result = await search(
        query=req.query,
        google=req.google,
        brave=req.brave,
        danbooru=req.danbooru,
        pexels=req.pexels,
        wikimedia=req.wikimedia,
        duckduckgo=req.duckduckgo,
        n=req.n,
        output_dir=output_dir,
    )

    if result.get("status") == "error":
        return JSONResponse(
            status_code=422,
            content={
                "search_id": search_id,
                "status": "error",
                "message": result.get("message", "Search failed"),
                "errors": result.get("errors", []),
            },
        )

    _latest_search_id = search_id

    candidate_map: dict[str, dict] = result.get("candidate_map", {})

    return JSONResponse(content={
        "search_id": search_id,
        "status": "ready",
        "candidate_map": candidate_map,
        "labels": result.get("labels", []),
        "grid_url": f"/grid/{search_id}",
        "total_found": result.get("total_found", 0),
        "errors": [str(e) for e in result.get("errors", [])],
    })


@app.get("/grid")
async def get_latest_grid() -> FileResponse:
    if _latest_search_id is None:
        raise HTTPException(status_code=404, detail="No search has been run yet")
    return _serve_grid(_latest_search_id)


@app.get("/grid/{search_id}")
async def get_grid(search_id: str) -> FileResponse:
    return _serve_grid(search_id)


def _serve_grid(search_id: str) -> FileResponse:
    grid_path = os.path.join(_GRID_STORE, search_id, "grid.jpg")
    if not os.path.isfile(grid_path):
        raise HTTPException(status_code=404, detail=f"Grid not found for search_id={search_id}")
    return FileResponse(grid_path, media_type="image/jpeg", filename="grid.jpg")


# ---------------------------------------------------------------------------
# __main__ entry point
# ---------------------------------------------------------------------------

def main() -> None:
    import uvicorn
    uvicorn.run(
        "imgfind.api:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )


if __name__ == "__main__":
    main()
