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


async def score_aesthetic(candidates: list[Candidate], batch_size: int = 8) -> list[Candidate]:
    if not candidates:
        return candidates

    _load()
    if _predictor is None:
        return candidates

    model, preprocessor = _predictor

    import torch
    device = next(model.parameters()).device

    valid_indices: list[int] = []
    images = []

    for i, candidate in enumerate(candidates):
        img = await image_cache.get(candidate.url)
        if img is None:
            candidate.aesthetic_score = 0.0
            continue
        images.append(img)
        valid_indices.append(i)

    for batch_start in range(0, len(images), batch_size):
        batch_imgs = images[batch_start:batch_start + batch_size]
        batch_indices = valid_indices[batch_start:batch_start + batch_size]

        inputs = preprocessor(images=batch_imgs, return_tensors="pt").to(device)
        with torch.no_grad():
            scores = model(**inputs).logits.squeeze(-1)

        if scores.dim() == 0:
            scores = scores.unsqueeze(0)

        for j, idx in enumerate(batch_indices):
            candidates[idx].aesthetic_score = max(0.0, min(10.0, scores[j].item()))

    return candidates
