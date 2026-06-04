from __future__ import annotations

import logging

from imgfind.models import Candidate
from imgfind.ranking import image_cache

logger = logging.getLogger(__name__)

_metric = None


def _load():
    global _metric
    if _metric is not None:
        return
    try:
        import pyiqa
        _metric = pyiqa.create_metric("musiq", as_loss=False)
    except ImportError:
        logger.warning("pyiqa not installed, technical scores will be 0")


async def score_technical(candidates: list[Candidate]) -> list[Candidate]:
    if not candidates:
        return candidates

    _load()
    if _metric is None:
        return candidates

    import torch
    from torchvision import transforms

    to_tensor = transforms.ToTensor()

    for candidate in candidates:
        img = await image_cache.get(candidate.url)
        if img is None:
            candidate.technical_score = 0.0
            continue

        try:
            img_tensor = to_tensor(img).unsqueeze(0)
            with torch.no_grad():
                score = _metric(img_tensor).item()
            candidate.technical_score = max(0.0, score)
        except Exception as e:
            logger.debug("Technical scoring failed for %s: %s", candidate.url, e)
            candidate.technical_score = 0.0

    return candidates
