from __future__ import annotations

import io
import json
import logging
import re
from pathlib import Path

import httpx
from PIL import Image

from imgfind.config import config
from imgfind.models import Candidate

logger = logging.getLogger(__name__)


def _slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[-\s]+", "-", text).strip("-")[:50]


class AssetManager:
    def __init__(self, out_dir: Path | None = None):
        self.out_dir = out_dir or config.assets_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.out_dir / "manifest.json"

    async def download_and_optimize(
        self,
        candidate: Candidate,
        target_width: int | None = None,
        fmt: str = "webp",
        quality: int = 85,
    ) -> Path | None:
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(
                    candidate.url, headers={"User-Agent": "imgfind/0.1"}
                )
                resp.raise_for_status()
                img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        except Exception as e:
            logger.error("Failed to download %s: %s", candidate.url, e)
            return None

        if target_width and img.width > target_width:
            ratio = target_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((target_width, new_height), Image.LANCZOS)

        slug = _slugify(candidate.title or candidate.id)
        filename = f"{slug}-{candidate.id}.{fmt}"
        filepath = self.out_dir / filename

        save_kwargs: dict = {}
        if fmt == "webp":
            save_kwargs = {"format": "WEBP", "quality": quality}
        elif fmt == "png":
            save_kwargs = {"format": "PNG"}
        elif fmt in ("jpg", "jpeg"):
            save_kwargs = {"format": "JPEG", "quality": quality}

        img.save(filepath, **save_kwargs)
        logger.info("Saved %s (%dx%d)", filepath, img.width, img.height)

        sidecar = {
            "id": candidate.id,
            "source_url": candidate.url,
            "source_page": candidate.source_page,
            "source": candidate.source,
            "license": candidate.license.value,
            "attribution": candidate.attribution,
            "scores": {
                "relevance": round(candidate.relevance_score, 4),
                "aesthetic": round(candidate.aesthetic_score, 4),
                "composite": round(candidate.composite_score, 4),
            },
            "dimensions": {"width": img.width, "height": img.height},
        }
        sidecar_path = filepath.with_suffix(filepath.suffix + ".json")
        sidecar_path.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")

        self._update_manifest(filename, sidecar)

        return filepath

    def _update_manifest(self, filename: str, entry: dict) -> None:
        manifest: dict = {}
        if self.manifest_path.exists():
            try:
                manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            except Exception:
                manifest = {}

        if "assets" not in manifest:
            manifest["assets"] = {}
        manifest["assets"][filename] = entry

        self.manifest_path.write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
