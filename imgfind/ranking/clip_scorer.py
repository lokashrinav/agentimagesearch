from __future__ import annotations

import logging

import torch

from imgfind.config import config
from imgfind.models import Candidate
from imgfind.ranking import image_cache

logger = logging.getLogger(__name__)

_model = None
_preprocess = None
_tokenizer = None


def _load():
    global _model, _preprocess, _tokenizer
    if _model is not None:
        return
    import open_clip
    _model, _, _preprocess = open_clip.create_model_and_transforms(
        config.clip_model, pretrained=config.clip_pretrained,
    )
    _tokenizer = open_clip.get_tokenizer(config.clip_model)
    _model.eval()
    if torch.cuda.is_available():
        _model = _model.cuda()


async def score_relevance(candidates: list[Candidate], query: str) -> list[Candidate]:
    if not candidates:
        return candidates

    _load()
    device = next(_model.parameters()).device

    text_tokens = _tokenizer([query]).to(device)
    with torch.no_grad():
        text_features = _model.encode_text(text_tokens)
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)

    for candidate in candidates:
        img = await image_cache.get(candidate.url)
        if img is None:
            candidate.relevance_score = 0.0
            continue

        if candidate.width == 0:
            candidate.width, candidate.height = img.size

        img_tensor = _preprocess(img).unsqueeze(0).to(device)
        with torch.no_grad():
            img_features = _model.encode_image(img_tensor)
            img_features = img_features / img_features.norm(dim=-1, keepdim=True)
            similarity = (img_features @ text_features.T).item()

        candidate.relevance_score = max(0.0, similarity)

    return candidates
