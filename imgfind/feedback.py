from __future__ import annotations

import json
import logging
import math

from imgfind.config import config
from imgfind.storage.db import Database

logger = logging.getLogger(__name__)


def tune_weights(db: Database, min_samples: int = 10) -> dict[str, float] | None:
    prefs = db.get_preferences()
    if len(prefs) < min_samples:
        logger.info("Not enough preference data (%d/%d), skipping weight tuning", len(prefs), min_samples)
        return None

    signal_names = ["relevance", "aesthetic", "technical"]
    best_weights = dict(config.blend_weights)
    best_accuracy = 0.0

    for r_w in _weight_range():
        for a_w in _weight_range():
            t_w = 1.0 - r_w - a_w
            if t_w < 0:
                continue

            correct = 0
            total = 0

            for pref in prefs:
                chosen = db.get_candidate(pref["chosen_id"])
                rejected_ids = json.loads(pref.get("rejected_ids", "[]"))
                if not chosen or not rejected_ids:
                    continue

                chosen_score = (
                    r_w * chosen.relevance_score
                    + a_w * chosen.aesthetic_score
                    + t_w * chosen.technical_score
                )

                for rid in rejected_ids:
                    rejected = db.get_candidate(rid)
                    if not rejected:
                        continue
                    rejected_score = (
                        r_w * rejected.relevance_score
                        + a_w * rejected.aesthetic_score
                        + t_w * rejected.technical_score
                    )
                    total += 1
                    if chosen_score > rejected_score:
                        correct += 1

            accuracy = correct / total if total > 0 else 0
            if accuracy > best_accuracy:
                best_accuracy = accuracy
                best_weights = {
                    "relevance": round(r_w, 2),
                    "aesthetic": round(a_w, 2),
                    "technical": round(t_w, 2),
                }

    if best_accuracy > 0.5:
        logger.info("Tuned weights: %s (accuracy: %.1f%%)", best_weights, best_accuracy * 100)
        config.blend_weights.update(best_weights)
        return best_weights

    return None


def _weight_range():
    return [i / 10.0 for i in range(0, 11)]
