from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from imgfind.config import config
from imgfind.models import Candidate
from imgfind.storage.db import Database

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="imgfind")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

_state: dict = {"candidates": [], "query": ""}


def set_candidates(candidates: list[Candidate], query: str) -> None:
    _state["candidates"] = candidates
    _state["query"] = query


@app.get("/", response_class=HTMLResponse)
async def index():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/api/candidates")
async def get_candidates():
    return JSONResponse({
        "query": _state["query"],
        "candidates": [c.to_dict() for c in _state["candidates"]],
    })


@app.post("/api/pick/{candidate_id}")
async def pick_candidate(candidate_id: str):
    chosen = None
    rejected_ids = []
    for c in _state["candidates"]:
        if c.id == candidate_id:
            chosen = c
        else:
            rejected_ids.append(c.id)

    if not chosen:
        raise HTTPException(404, "Candidate not found")

    db = Database()
    try:
        db.record_preference(_state["query"], chosen.id, rejected_ids)
    finally:
        db.close()

    return JSONResponse({"status": "ok", "chosen": chosen.to_dict()})


def run_server(candidates: list[Candidate], query: str, port: int | None = None):
    import uvicorn
    set_candidates(candidates, query)
    port = port or config.ui_port
    print(f"\n  Grid UI: http://localhost:{port}\n")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
