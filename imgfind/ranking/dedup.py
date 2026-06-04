from __future__ import annotations

import logging

import imagehash

from imgfind.config import config
from imgfind.models import Candidate
from imgfind.ranking import image_cache

logger = logging.getLogger(__name__)


async def deduplicate(candidates: list[Candidate]) -> list[Candidate]:
    if not candidates:
        return candidates

    threshold = config.dedup_threshold
    hashes: list[tuple[imagehash.ImageHash, Candidate]] = []
    unique: list[Candidate] = []

    for candidate in candidates:
        img = await image_cache.get(candidate.url)
        if img is None:
            unique.append(candidate)
            continue

        phash = imagehash.phash(img)
        candidate.phash = str(phash)

        is_dup = False
        for existing_hash, _ in hashes:
            if abs(phash - existing_hash) < threshold:
                is_dup = True
                break

        if not is_dup:
            hashes.append((phash, candidate))
            unique.append(candidate)
        else:
            logger.debug("Dedup: dropped %s (near-duplicate)", candidate.url[:80])

    return unique
