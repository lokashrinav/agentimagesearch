from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx

from imgfind.config import config
from imgfind.models import Candidate, LicenseType
from imgfind.sources.base import Source

IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/bmp", "image/tiff"}


def extract_drive_id(url: str) -> tuple[str, str]:
    """Returns (id, type) where type is 'folder' or 'file'."""
    parsed = urlparse(url)
    if "folders" in parsed.path:
        m = re.search(r"folders/([a-zA-Z0-9_-]+)", parsed.path)
        if m:
            return m.group(1), "folder"
    m = re.search(r"/d/([a-zA-Z0-9_-]+)", parsed.path)
    if m:
        return m.group(1), "file"
    m = re.search(r"id=([a-zA-Z0-9_-]+)", parsed.query)
    if m:
        return m.group(1), "file"
    return "", ""


class DriveSource(Source):
    name = "drive"

    def available(self) -> bool:
        return bool(config.google_api_key)

    async def search(self, query: str, n: int = 20, **kwargs) -> list[Candidate]:
        url = kwargs.get("url", query)
        drive_id, drive_type = extract_drive_id(url)
        if not drive_id:
            return []

        if drive_type == "file":
            return await self._single_file(drive_id)
        return await self._list_folder(drive_id, n)

    async def _single_file(self, file_id: str) -> list[Candidate]:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"https://www.googleapis.com/drive/v3/files/{file_id}",
                params={
                    "key": config.google_api_key,
                    "fields": "id,name,mimeType,imageMediaMetadata,webContentLink,thumbnailLink",
                },
            )
            resp.raise_for_status()
            f = resp.json()

            if f.get("mimeType", "") not in IMAGE_MIMES:
                return []

            meta = f.get("imageMediaMetadata", {})
            return [Candidate(
                url=f.get("webContentLink", f"https://drive.google.com/uc?export=download&id={file_id}"),
                source=self.name,
                source_page=f"https://drive.google.com/file/d/{file_id}",
                title=f.get("name", ""),
                width=meta.get("width", 0),
                height=meta.get("height", 0),
                license=LicenseType.UNKNOWN,
            )]

    async def _list_folder(self, folder_id: str, n: int) -> list[Candidate]:
        candidates: list[Candidate] = []
        page_token = None
        async with httpx.AsyncClient(timeout=30) as client:
            while len(candidates) < n:
                params: dict = {
                    "key": config.google_api_key,
                    "q": f"'{folder_id}' in parents and mimeType contains 'image/'",
                    "fields": "nextPageToken, files(id,name,mimeType,imageMediaMetadata,webContentLink,thumbnailLink)",
                    "pageSize": min(n - len(candidates), 100),
                }
                if page_token:
                    params["pageToken"] = page_token

                resp = await client.get(
                    "https://www.googleapis.com/drive/v3/files",
                    params=params,
                )
                resp.raise_for_status()
                data = resp.json()

                for f in data.get("files", []):
                    meta = f.get("imageMediaMetadata", {})
                    fid = f["id"]
                    candidates.append(Candidate(
                        url=f.get("webContentLink", f"https://drive.google.com/uc?export=download&id={fid}"),
                        source=self.name,
                        source_page=f"https://drive.google.com/file/d/{fid}",
                        title=f.get("name", ""),
                        width=meta.get("width", 0),
                        height=meta.get("height", 0),
                        license=LicenseType.UNKNOWN,
                    ))

                page_token = data.get("nextPageToken")
                if not page_token:
                    break

        return candidates[:n]
