from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .config import settings


ASSET_ROOT = Path(settings.download_dir) / "_assets"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def first_url(value) -> str:
    if isinstance(value, list):
        for item in value:
            url = first_url(item)
            if url:
                return url
    if isinstance(value, str):
        return value.strip().split()[0] if value.strip() else ""
    return ""


def cover_url_from_payload(payload: dict) -> str:
    cover = ((payload.get("cover_data") or {}).get("cover") or {})
    if isinstance(cover, dict):
        url = first_url(cover.get("url_list"))
        if url:
            return url
    return str(payload.get("cover_url") or "")


def author_avatar_url_from_payload(payload: dict) -> str:
    author = payload.get("author")
    if not isinstance(author, dict):
        return ""
    for key in ("avatar_thumb", "avatar_medium", "avatar_larger", "avatar_300x300"):
        avatar = author.get(key)
        if isinstance(avatar, dict):
            url = first_url(avatar.get("url_list"))
            if url:
                return url
    return ""


def extension_for_url(url: str, content_type: str = "") -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return suffix
    if "png" in content_type:
        return ".png"
    if "webp" in content_type:
        return ".webp"
    if "gif" in content_type:
        return ".gif"
    return ".jpg"


def relative_asset_path(path: str | Path | None) -> str:
    if not path:
        return ""
    try:
        return str(Path(path).resolve().relative_to(ASSET_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return ""


def asset_file_path(kind: str, url: str, content_type: str = "") -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]
    return ASSET_ROOT / kind / f"{digest}{extension_for_url(url, content_type)}"


async def cache_remote_image(url: str, kind: str, headers: dict[str, str] | None = None) -> str:
    url = str(url or "").strip()
    if not url.startswith("http"):
        return ""
    provisional = asset_file_path(kind, url)
    if provisional.exists():
        return str(provisional)
    async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
        response = await client.get(url, headers=headers or {})
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        target = asset_file_path(kind, url, content_type)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            return str(target)
        target.write_bytes(response.content)
        return str(target)

