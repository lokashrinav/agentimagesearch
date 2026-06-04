from __future__ import annotations

import base64
import io
import json
import logging

import httpx
from PIL import Image

from imgfind.config import config
from imgfind.models import Candidate

logger = logging.getLogger(__name__)


async def _download_and_encode(url: str, max_size: int = 1024) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "imgfind/0.1"})
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content)).convert("RGB")
            img.thumbnail((max_size, max_size))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=80)
            return base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        logger.debug("Failed to download for vision rerank %s: %s", url, e)
        return None


async def vision_rerank(
    candidates: list[Candidate],
    query: str,
    top_k: int | None = None,
) -> list[Candidate]:
    if not config.anthropic_key or not candidates:
        return candidates

    k = top_k or config.top_k_rerank
    to_rerank = candidates[:k]
    rest = candidates[k:]

    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=config.anthropic_key)
    except ImportError:
        logger.warning("anthropic SDK not installed, skipping vision rerank")
        return candidates

    for candidate in to_rerank:
        b64 = await _download_and_encode(candidate.url)
        if not b64:
            continue

        try:
            resp = await client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=300,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                f'Rate this image for the query "{query}". '
                                "Respond with ONLY a JSON object: "
                                '{"relevance": 0-10, "quality": 0-10, '
                                '"license_risk": "low"|"medium"|"high", '
                                '"rationale": "one sentence"}'
                            ),
                        },
                    ],
                }],
            )

            text = resp.content[0].text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            data = json.loads(text)
            candidate.vision_score = (data.get("relevance", 0) + data.get("quality", 0)) / 2.0
            candidate.vision_rationale = data.get("rationale", "")

        except Exception as e:
            logger.debug("Vision rerank failed for %s: %s", candidate.url[:80], e)

    reranked = sorted(to_rerank, key=lambda c: c.vision_score, reverse=True)
    return reranked + rest
