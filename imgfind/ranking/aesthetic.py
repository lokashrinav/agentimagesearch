from __future__ import annotations

import logging

from imgfind.models import Candidate
from imgfind.ranking import image_cache

logger = logging.getLogger(__name__)

_predictor = None


def _load():
    global _predictor
    if _predictor is not None:
        return
    try:
        from aesthetic_predictor_v2_5 import convert_v2_5_from_siglip
        _predictor = convert_v2_5_from_siglip(
            low_cpu_mem_usage=True,
            trust_remote_code=True,
        )
    except ImportError:
        logger.warning("aesthetic-predictor-v2-5 not installed, scores will be 0")


async def score_aesthetic(candidates: list[Candidate]) -> list[Candidate]:
    if not candidates:
        return candidates

    _load()
    if _predictor is None:
        return candidates

    model, preprocessor = _predictor

    import torch
    device = next(model.parameters()).device

    for candidate in candidates:
        img = await image_cache.get(candidate.url)
        if img is None:
            candidate.aesthetic_score = 0.0
            continue

        inputs = preprocessor(images=img, return_tensors="pt").to(device)
        with torch.no_grad():
            score = model(**inputs).logits.squeeze().item()

        candidate.aesthetic_score = max(0.0, min(10.0, score))

    return candidates
