from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

from imgfind.models import Candidate, LicenseType
from imgfind.sources.base import Source

logger = logging.getLogger(__name__)

ART_HOSTS = {
    "pixiv.net", "danbooru.donmai.us", "artstation.com", "deviantart.com",
    "twitter.com", "x.com", "reddit.com", "tumblr.com", "flickr.com",
    "gelbooru.com", "e621.net", "newgrounds.com", "zerochan.net",
    "instagram.com", "imgur.com", "safebooru.org", "konachan.com",
    "yande.re",
}

_BOORU_SITES: dict[str, str] = {
    "danbooru":  "https://danbooru.donmai.us/posts?tags={tags}",
    "gelbooru":  "https://gelbooru.com/index.php?page=post&s=list&tags={tags}",
    "safebooru": "https://safebooru.org/index.php?page=post&s=list&tags={tags}",
}

_QUERY_SITES: dict[str, str] = {
    "deviantart": "https://www.deviantart.com/search?q={query}",
    "zerochan":   "https://www.zerochan.net/{query}",
}

_EXTRA_BOORU_SITES: dict[str, str] = {
    "yandere":   "https://yande.re/post?tags={tags}",
    "konachan":  "https://konachan.com/post?tags={tags}",
}

_DEFAULT_SITES: dict[str, str] = {**_BOORU_SITES, **_QUERY_SITES}
_ALL_SITES: dict[str, str] = {**_DEFAULT_SITES, **_EXTRA_BOORU_SITES}


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
        url = kwargs.get("url")
        if url and url.startswith("http"):
            return await self._extract_from_url(url, n, **kwargs)
        # No explicit URL — search art sites by tags/keywords.
        sites = kwargs.get("sites")
        return await self.search_by_tags(query, n, sites=sites)

    async def search_by_tags(
        self,
        query: str,
        n: int = 20,
        sites: list[str] | None = None,
    ) -> list[Candidate]:
        """Construct search URLs for popular art/booru sites and scrape them
        with gallery-dl.  Spreads *n* evenly across the selected sites and
        runs all gallery-dl invocations concurrently."""

        chosen = _DEFAULT_SITES if sites is None else {
            k: v for k, v in _ALL_SITES.items() if k in sites
        }
        if not chosen:
            return []

        n_per_site = max(1, n // len(chosen))

        # Boorus use space-separated individual tags, not one compound tag.
        space_tags = " ".join(query.strip().split())
        encoded_query = quote(query.strip())

        search_urls: list[tuple[str, str]] = []
        for site_name, pattern in chosen.items():
            if site_name in _BOORU_SITES:
                url = pattern.format(tags=quote(space_tags, safe=""))
            else:
                url = pattern.format(query=encoded_query)
            search_urls.append((site_name, url))

        tasks = [
            self._extract_from_url(url, n_per_site, site_name=site_name)
            for site_name, url in search_urls
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        candidates: list[Candidate] = []
        for site_url_pair, result in zip(search_urls, results):
            site_name, url = site_url_pair
            if isinstance(result, Exception):
                logger.warning("gallery-dl search failed for %s (%s): %s", site_name, url, result)
            elif isinstance(result, list):
                candidates.extend(result)

        return candidates[:n]

    async def _extract_from_url(self, url: str, n: int, **kwargs) -> list[Candidate]:
        site_name = kwargs.get("site_name")
        source_label = f"{self.name}:{site_name}" if site_name else self.name

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

            logger.debug("gallery-dl cmd: %s", " ".join(cmd))
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)

            if proc.returncode and proc.returncode != 0:
                logger.debug("gallery-dl stderr for %s: %s", url, stderr.decode(errors="replace")[:500])

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
                    source=source_label,
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
