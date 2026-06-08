from __future__ import annotations

import base64
import io
import json
import logging
from dataclasses import dataclass, field
from typing import Callable, Awaitable

import httpx
from PIL import Image, ImageDraw, ImageFont

from imgfind.config import config
from imgfind.models import Candidate

logger = logging.getLogger(__name__)

LABELS = "ABCDEFGHIJ"
THUMB_SIZE = 384
GRID_COLS = 5
LABEL_HEIGHT = 24
LABEL_BG = (30, 30, 30)
LABEL_FG = (255, 255, 255)

VisionCallback = Callable[[str, bytes], Awaitable[str]]


@dataclass
class GridRankResult:
    ranking: list[str] = field(default_factory=list)
    explanations: dict[str, str] = field(default_factory=dict)
    confidence: float = 0.0


async def _download_thumb(url: str) -> Image.Image | None:
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "imgfind/0.1"})
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content)).convert("RGB")
            img.thumbnail((THUMB_SIZE, THUMB_SIZE), Image.LANCZOS)
            return img
    except Exception as e:
        logger.debug("Failed to download thumbnail %s: %s", url[:80], e)
        return None


def _build_grid(images: list[tuple[str, Image.Image]]) -> bytes:
    n = len(images)
    cols = min(n, GRID_COLS)
    rows = (n + cols - 1) // cols
    cell_h = THUMB_SIZE + LABEL_HEIGHT

    grid = Image.new("RGB", (cols * THUMB_SIZE, rows * cell_h), (128, 128, 128))
    draw = ImageDraw.Draw(grid)

    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        font = ImageFont.load_default()

    for i, (label, img) in enumerate(images):
        col = i % cols
        row = i // cols
        x = col * THUMB_SIZE
        y = row * cell_h

        paste_x = x + (THUMB_SIZE - img.width) // 2
        paste_y = y + LABEL_HEIGHT + (THUMB_SIZE - img.height) // 2
        grid.paste(img, (paste_x, paste_y))

        draw.rectangle([x, y, x + THUMB_SIZE, y + LABEL_HEIGHT], fill=LABEL_BG)
        draw.text((x + 8, y + 2), label, fill=LABEL_FG, font=font)

    buf = io.BytesIO()
    grid.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def _build_prompt(query: str, labels: list[str], verification: str) -> str:
    label_list = ", ".join(labels)
    prompt = (
        f'I searched for "{query}" and got these {len(labels)} candidate images '
        f"labeled {label_list}.\n\n"
        "Rank ALL candidates from best to worst match for my query. "
        "Consider: relevance to the query, image quality, usability, "
        "and whether the image would actually be useful for someone "
        "searching this term.\n\n"
    )

    if verification:
        prompt += (
            "Also verify each candidate against these criteria:\n"
            f"{verification}\n\n"
        )

    prompt += (
        "Respond with ONLY a JSON object:\n"
        "{\n"
        '  "ranking": ["B", "E", "A", ...],\n'
        '  "explanations": {"A": "one sentence", "B": "one sentence", ...},\n'
        '  "confidence": 0.0-1.0\n'
        "}"
    )
    return prompt


async def _call_anthropic(prompt: str, image_bytes: bytes) -> str:
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=config.anthropic_key)
    grid_b64 = base64.b64encode(image_bytes).decode()
    resp = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=800,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": grid_b64,
                    },
                },
                {"type": "text", "text": prompt},
            ],
        }],
    )
    return resp.content[0].text


def _parse_result(text: str) -> GridRankResult:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    data = json.loads(text)
    return GridRankResult(
        ranking=data.get("ranking", []),
        explanations=data.get("explanations", {}),
        confidence=data.get("confidence", 0.0),
    )


async def grid_rerank(
    candidates: list[Candidate],
    query: str,
    top_k: int | None = None,
    verification: str = "",
    vision: VisionCallback | None = None,
) -> list[Candidate]:
    if not candidates:
        return candidates
    if vision is None and not config.anthropic_key:
        return candidates

    k = min(top_k or config.top_k_rerank, len(candidates), len(LABELS))
    to_rerank = candidates[:k]
    rest = candidates[k:]

    images: list[tuple[str, Image.Image]] = []
    label_to_candidate: dict[str, Candidate] = {}

    for i, candidate in enumerate(to_rerank):
        label = LABELS[i]
        img = await _download_thumb(candidate.url)
        if img is None:
            continue
        images.append((label, img))
        label_to_candidate[label] = candidate

    if len(images) < 2:
        logger.info("Too few images downloaded for grid rerank (%d), skipping", len(images))
        return candidates

    grid_bytes = _build_grid(images)
    active_labels = [label for label, _ in images]
    prompt = _build_prompt(query, active_labels, verification)

    try:
        if vision is not None:
            text = await vision(prompt, grid_bytes)
        else:
            text = await _call_anthropic(prompt, grid_bytes)

        result = _parse_result(text)

        logger.info(
            "Grid rerank: %s (confidence: %.2f)",
            " > ".join(result.ranking),
            result.confidence,
        )

        reranked: list[Candidate] = []
        seen: set[str] = set()
        for label in result.ranking:
            label = label.strip().upper()
            if label in label_to_candidate and label not in seen:
                candidate = label_to_candidate[label]
                explanation = result.explanations.get(label, "")
                candidate.vision_score = float(k - len(reranked))
                candidate.vision_rationale = explanation
                reranked.append(candidate)
                seen.add(label)

        for label in active_labels:
            if label not in seen and label in label_to_candidate:
                reranked.append(label_to_candidate[label])

        return reranked + rest

    except Exception as e:
        logger.warning("Grid rerank failed: %s", e)
        return candidates
