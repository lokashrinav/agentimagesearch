from __future__ import annotations

import logging

from imgfind.config import config
from imgfind.models import Candidate
from imgfind.ranking import image_cache
from imgfind.ranking.blend import blend_scores

logger = logging.getLogger(__name__)


class RankingPipeline:
    def __init__(
        self,
        skip_clip: bool = False,
        skip_aesthetic: bool = False,
        skip_technical: bool = True,
        skip_vision: bool = False,
        skip_dedup: bool = False,
        blend_method: str = "zscore",
    ):
        self.skip_clip = skip_clip
        self.skip_aesthetic = skip_aesthetic
        self.skip_technical = skip_technical
        self.skip_vision = skip_vision
        self.skip_dedup = skip_dedup
        self.blend_method = blend_method

    async def rank(self, candidates: list[Candidate], query: str) -> list[Candidate]:
        if not candidates:
            return candidates

        result = list(candidates)

        result = self._filter_resolution(result)
        logger.info("After resolution filter: %d candidates", len(result))

        if not self.skip_dedup:
            from imgfind.ranking.dedup import deduplicate
            result = await deduplicate(result)
            logger.info("After dedup: %d candidates", len(result))

        if not self.skip_clip:
            from imgfind.ranking.clip_scorer import score_relevance
            result = await score_relevance(result, query)
            result = [c for c in result if c.relevance_score >= config.relevance_floor]
            logger.info("After CLIP relevance filter: %d candidates", len(result))

        if not self.skip_aesthetic:
            from imgfind.ranking.aesthetic import score_aesthetic
            result = await score_aesthetic(result)
            logger.info("Aesthetic scoring complete")

        if not self.skip_technical:
            from imgfind.ranking.technical import score_technical
            result = await score_technical(result)
            logger.info("Technical scoring complete")

        result = blend_scores(result, method=self.blend_method)

        if not self.skip_vision and config.anthropic_key:
            from imgfind.ranking.vision_rerank import vision_rerank
            result = await vision_rerank(result, query)
            logger.info("Vision re-rank complete")

        image_cache.clear()
        return result

    def _filter_resolution(self, candidates: list[Candidate]) -> list[Candidate]:
        min_res = config.min_resolution
        filtered = []
        for c in candidates:
            if c.width == 0 and c.height == 0:
                filtered.append(c)
            elif max(c.width, c.height) >= min_res:
                filtered.append(c)
        return filtered
