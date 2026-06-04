from __future__ import annotations

import math

from imgfind.config import config
from imgfind.models import Candidate


def _z_scores(values: list[float]) -> list[float]:
    if not values or len(values) < 2:
        return [0.0] * len(values)
    mean = sum(values) / len(values)
    std = math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))
    if std < 1e-8:
        return [0.0] * len(values)
    return [(v - mean) / std for v in values]


def _rrf(rankings: list[list[int]], k: int = 60) -> list[float]:
    n = max(max(r) for r in rankings) + 1 if rankings and rankings[0] else 0
    scores = [0.0] * n
    for ranking in rankings:
        for rank, idx in enumerate(ranking):
            scores[idx] += 1.0 / (k + rank + 1)
    return scores


def blend_scores(candidates: list[Candidate], method: str = "zscore") -> list[Candidate]:
    if not candidates:
        return candidates

    weights = config.blend_weights

    if method == "rrf":
        rel_ranking = sorted(range(len(candidates)), key=lambda i: candidates[i].relevance_score, reverse=True)
        aes_ranking = sorted(range(len(candidates)), key=lambda i: candidates[i].aesthetic_score, reverse=True)
        tech_ranking = sorted(range(len(candidates)), key=lambda i: candidates[i].technical_score, reverse=True)

        rrf_scores = _rrf([rel_ranking, aes_ranking, tech_ranking])
        for i, c in enumerate(candidates):
            c.composite_score = rrf_scores[i]
    else:
        rel_z = _z_scores([c.relevance_score for c in candidates])
        aes_z = _z_scores([c.aesthetic_score for c in candidates])
        tech_z = _z_scores([c.technical_score for c in candidates])

        for i, c in enumerate(candidates):
            c.composite_score = (
                weights["relevance"] * rel_z[i]
                + weights["aesthetic"] * aes_z[i]
                + weights["technical"] * tech_z[i]
            )

    candidates.sort(key=lambda c: c.composite_score, reverse=True)
    return candidates
