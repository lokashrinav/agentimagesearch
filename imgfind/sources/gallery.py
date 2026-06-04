from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from imgfind.models import Candidate, LicenseType
from imgfind.sources.base import Source

ART_HOSTS = {
    "pixiv.net", "danbooru.donmai.us", "artstation.com", "deviantart.com",
    "twitter.com", "x.com", "reddit.com", "tumblr.com", "flickr.com",
    "gelbooru.com", "e621.net", "newgrounds.com", "zerochan.net",
    "instagram.com", "imgur.com", "safebooru.org", "konachan.com",
    "yande.re",
}


def is_gallery_dl_url(url: str) -> bool:
    from urllib.parse import urlparse
    host = urlparse(url).hostname or ""
    return any(host == h or host.endswith("." + h) for h in ART_HOSTS)


class GalleryDLSource(Source):
    name = "gallery-dl"

    def available(self) -> bool:
        try:
            subprocess.run(
                [sys.executable, "-m", "gallery_dl", "--version"],
                capture_output=True, timeout=5,
            )
            return True
        except Exception:
            return False

    async def search(self, query: str, n: int = 20, **kwargs) -> list[Candidate]:
        url = kwargs.get("url", query)
        if not url.startswith("http"):
            return []
        return await self._extract_from_url(url, n, **kwargs)

    async def _extract_from_url(self, url: str, n: int, **kwargs) -> list[Candidate]:
        with tempfile.TemporaryDirectory() as tmpdir:
            cmd = [
                sys.executable, "-m", "gallery_dl",
                "--get-urls",
                "--write-metadata",
                "--range", f"1-{n}",
                "--dest", tmpdir,
                url,
            ]
            min_res = kwargs.get("min_resolution", 0)
            if min_res:
                cmd.extend(["--filter", f"width>={min_res} or height>={min_res}"])

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)

            urls = [line.strip() for line in stdout.decode().splitlines() if line.strip()]

            candidates: list[Candidate] = []
            metadata_files = list(Path(tmpdir).rglob("*.json"))
            meta_by_url: dict[str, dict] = {}
            for mf in metadata_files:
                try:
                    meta = json.loads(mf.read_text(encoding="utf-8"))
                    file_url = meta.get("url", meta.get("file_url", ""))
                    if file_url:
                        meta_by_url[file_url] = meta
                except Exception:
                    pass

            for img_url in urls[:n]:
                meta = meta_by_url.get(img_url, {})
                candidates.append(Candidate(
                    url=img_url,
                    source=self.name,
                    source_page=url,
                    title=meta.get("title", meta.get("description", "")),
                    width=meta.get("width", meta.get("image_width", 0)),
                    height=meta.get("height", meta.get("image_height", 0)),
                    license=LicenseType.COPYRIGHTED,
                    metadata={
                        "tags": meta.get("tags", meta.get("tag_string", "")),
                        "score": meta.get("score", meta.get("fav_count", 0)),
                        "uploader": meta.get("uploader", meta.get("user", {}).get("name", "")),
                    },
                ))

            return candidates
