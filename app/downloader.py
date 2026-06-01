import asyncio
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from . import db
from .assets import author_avatar_url_from_payload, cache_remote_image, cover_url_from_payload
from .config import settings
from .db import utc_now
from .parser import ParserClient, author_name_from_payload


ILLEGAL_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\r\n\t]+')


class DownloadCancelled(RuntimeError):
    pass


def sanitize_filename_part(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    text = ILLEGAL_FILENAME_CHARS.sub("", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    return text or fallback


def limit_bytes(text: str, max_bytes: int = 180) -> str:
    text = text.strip()
    while len(text.encode("utf-8")) > max_bytes:
        text = text[:-1].strip()
    return text or "download"


def relative_media_path(path: str | None) -> str | None:
    if not path:
        return None
    try:
        return str(Path(path).resolve().relative_to(Path(settings.download_dir).resolve())).replace("\\", "/")
    except ValueError:
        return None


def render_filename_template(template: str, values: dict[str, str]) -> str:
    try:
        return template.format(**values)
    except (KeyError, ValueError):
        return "{author}\uff1a{desc}".format(**values)


def build_paths(
    payload: dict[str, Any],
    with_watermark: bool = False,
    app_settings: dict[str, Any] | None = None,
) -> tuple[str, str]:
    app_settings = app_settings or {}
    platform = sanitize_filename_part(payload.get("platform"), "unknown")
    author = sanitize_filename_part(author_name_from_payload(payload), "unknown_author")
    desc = sanitize_filename_part(payload.get("desc"), str(payload.get("video_id") or "download"))
    suffix = "_watermark" if with_watermark else ""
    values = {
        "author": author,
        "desc": desc,
        "video_id": sanitize_filename_part(payload.get("video_id"), "video"),
        "platform": platform,
    }
    template = str(app_settings.get("filename_template") or "{author}\uff1a{desc}")
    stem = sanitize_filename_part(render_filename_template(template, values), "download")
    filename = limit_bytes(f"{stem}{suffix}") + ".mp4"
    target_dir = Path(settings.download_dir) / platform
    if app_settings.get("author_folders", True):
        target_dir = target_dir / author
    target_dir.mkdir(parents=True, exist_ok=True)
    return str(target_dir / filename), str(target_dir / (Path(filename).stem + ".jpg"))


def build_image_paths(payload: dict[str, Any], app_settings: dict[str, Any] | None = None, count: int = 1) -> list[str]:
    video_path, _ = build_paths(payload, app_settings=app_settings)
    folder = Path(video_path).with_suffix("")
    folder.mkdir(parents=True, exist_ok=True)
    width = max(2, len(str(max(1, count))))
    return [str(folder / f"{index + 1:0{width}d}.jpg") for index in range(count)]


def build_download_headers(payload: dict[str, Any], parser_settings: dict[str, Any]) -> dict[str, str]:
    platform = str(payload.get("platform") or "").lower()
    user_agent = str(parser_settings.get("douyin_user_agent") or settings.douyin_user_agent)
    headers = {
        "User-Agent": user_agent or "Mozilla/5.0 ClipNest/0.1",
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if platform == "douyin":
        headers["Referer"] = "https://www.douyin.com/"
        cookie = str(parser_settings.get("douyin_cookie") or settings.douyin_cookie or "")
        if cookie:
            headers["Cookie"] = cookie
    return headers


def build_video_download_headers(headers: dict[str, str]) -> dict[str, str]:
    video_headers = dict(headers)
    video_headers.setdefault("Range", "bytes=0-")
    video_headers.setdefault("Accept-Encoding", "identity")
    video_headers.setdefault("Connection", "keep-alive")
    video_headers.setdefault("Sec-Fetch-Dest", "video")
    video_headers.setdefault("Sec-Fetch-Mode", "no-cors")
    video_headers.setdefault("Sec-Fetch-Site", "cross-site")
    return video_headers


def candidate_dimension(item: dict[str, Any]) -> tuple[int, int, int]:
    width = int(item.get("width") or 0)
    height = int(item.get("height") or 0)
    shorter = min(width, height) if width and height else max(width, height)
    longer = max(width, height)
    return width, height, shorter or longer


def candidate_quality_score(item: dict[str, Any]) -> tuple[int, int, int, int, int]:
    width, height, shorter = candidate_dimension(item)
    return (
        max(width, height),
        shorter,
        int(bool(item.get("is_h265"))),
        int(item.get("data_size") or 0),
        int(item.get("bit_rate") or 0),
    )


def ordered_bit_rate_candidates(
    video_data: dict[str, Any],
    quality_preference: str | None = "best",
) -> list[dict[str, Any]]:
    items = [item for item in video_data.get("bit_rate_candidates") or [] if isinstance(item, dict)]
    quality = db.normalize_quality_preference(quality_preference)
    if quality == "best":
        return sorted(items, key=candidate_quality_score, reverse=True)

    target = int(quality)
    within_target: list[dict[str, Any]] = []
    above_target: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []
    for item in items:
        _, _, shorter = candidate_dimension(item)
        if not shorter:
            unknown.append(item)
        elif shorter <= target:
            within_target.append(item)
        else:
            above_target.append(item)

    within_target.sort(key=candidate_quality_score, reverse=True)
    above_target.sort(
        key=lambda item: (
            candidate_dimension(item)[2],
            -int(bool(item.get("is_h265"))),
            -int(item.get("data_size") or 0),
            -int(item.get("bit_rate") or 0),
        )
    )
    unknown.sort(key=candidate_quality_score, reverse=True)
    return within_target + above_target + unknown


def video_download_candidates(
    video_data: dict[str, Any],
    quality_preference: str | None = "best",
) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    seen: set[str] = set()
    quality = db.normalize_quality_preference(quality_preference)
    for index, item in enumerate(ordered_bit_rate_candidates(video_data, quality)):
        width = int(item.get("width") or 0)
        height = int(item.get("height") or 0)
        fps = int(item.get("fps") or 0)
        codec = "h265" if item.get("is_h265") else "h264"
        label = f"bit-rate {width}x{height}"
        if fps:
            label = f"{label}@{fps}"
        label = f"{label} {codec}"
        urls = [item.get("url"), *(item.get("back_urls") or [])]
        for url_index, url_value in enumerate(urls):
            url = str(url_value or "").strip()
            if not url or url in seen:
                continue
            suffix = "" if url_index == 0 else f" backup {url_index}"
            candidates.append(
                {
                    "key": f"bit_rate_{quality}_{index}_{url_index}",
                    "label": f"{label}{suffix}",
                    "url": url,
                }
            )
            seen.add(url)
    ordered_keys = (
        ("nwm_video_url_HQ", "no-watermark HQ"),
        ("nwm_video_url", "no-watermark fallback"),
        ("wm_video_url_HQ", "watermark HQ"),
        ("wm_video_url", "watermark fallback"),
    )
    for key, label in ordered_keys:
        url = str(video_data.get(key) or "").strip()
        if not url or url in seen:
            continue
        candidates.append({"key": key, "label": label, "url": url})
        seen.add(url)
    return candidates


def safe_url_host(url: str) -> str:
    try:
        return urlsplit(url).netloc
    except ValueError:
        return ""


def format_size(value: Any) -> str:
    try:
        size = float(value or 0)
    except (TypeError, ValueError):
        return "-"
    if size <= 0:
        return "-"
    units = ["B", "KB", "MB", "GB", "TB"]
    index = 0
    while size >= 1024 and index < len(units) - 1:
        size /= 1024
        index += 1
    return f"{size:.1f} {units[index]}" if index else f"{int(size)} {units[index]}"


def format_seconds(value: Any) -> str:
    try:
        seconds = float(value or 0)
    except (TypeError, ValueError):
        return "-"
    if seconds <= 0:
        return "-"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, sec = divmod(int(round(seconds)), 60)
    hours, minute = divmod(minutes, 60)
    if hours:
        return f"{hours}h{minute:02d}m{sec:02d}s"
    return f"{minute}m{sec:02d}s"


def parse_content_range_total(value: str) -> int:
    match = re.search(r"/(\d+)\s*$", str(value or ""))
    return int(match.group(1)) if match else 0


def download_summary(label: str, result: dict[str, Any]) -> str:
    speed_value = float(result.get("speed_bytes_per_second") or 0)
    suffix = " · CDN 较慢" if 0 < speed_value < 128 * 1024 else ""
    return (
        f"Downloaded with {label} · {format_size(result.get('bytes'))} "
        f"in {format_seconds(result.get('duration_seconds'))} · {format_size(speed_value)}/s{suffix}"
    )


async def probe_range_size(url: str, headers: dict[str, str]) -> dict[str, Any]:
    probe_headers = build_video_download_headers(headers)
    probe_headers["Range"] = "bytes=0-0"
    timeout = httpx.Timeout(20.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        async with client.stream("GET", url, headers=probe_headers) as response:
            response.raise_for_status()
            content_range = str(response.headers.get("content-range") or "")
            content_length = int(response.headers.get("content-length") or 0)
            total_size = parse_content_range_total(content_range) or content_length
            return {
                "http_status": response.status_code,
                "content_range": content_range,
                "total_size": total_size,
                "range_supported": response.status_code == 206 and total_size > 0,
            }


async def probe_candidate_speed(candidate: dict[str, str], headers: dict[str, str], probe_bytes: int = 512 * 1024) -> dict[str, Any]:
    url = candidate["url"]
    probe_headers = build_video_download_headers(headers)
    probe_headers["Range"] = f"bytes=0-{probe_bytes - 1}"
    total = 0
    started = asyncio.get_running_loop().time()
    timeout = httpx.Timeout(20.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        async with client.stream("GET", url, headers=probe_headers) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                if not chunk:
                    continue
                total += len(chunk)
                if total >= probe_bytes:
                    break
    duration = max(0.001, asyncio.get_running_loop().time() - started)
    return {
        "key": candidate.get("key"),
        "label": candidate.get("label"),
        "host": safe_url_host(url),
        "speed_bytes_per_second": round(total / duration, 2),
        "bytes": total,
        "duration_seconds": round(duration, 3),
    }


async def reorder_candidates_by_probe(
    candidates: list[dict[str, str]],
    headers: dict[str, str],
    job_id: int | None = None,
    limit: int = 6,
) -> list[dict[str, str]]:
    if len(candidates) <= 1:
        return candidates
    probe_targets = candidates[:max(1, min(limit, len(candidates)))]
    results = await asyncio.gather(
        *(probe_candidate_speed(candidate, headers) for candidate in probe_targets),
        return_exceptions=True,
    )
    speeds: dict[str, float] = {}
    event_results: list[dict[str, Any]] = []
    for candidate, result in zip(probe_targets, results, strict=False):
        if isinstance(result, Exception):
            event_results.append(
                {
                    "key": candidate.get("key"),
                    "label": candidate.get("label"),
                    "host": safe_url_host(candidate.get("url") or ""),
                    "error": f"{type(result).__name__}: {str(result)[:160]}",
                }
            )
            continue
        speeds[str(candidate.get("url") or "")] = float(result.get("speed_bytes_per_second") or 0)
        event_results.append(result)
    if not speeds:
        return candidates
    ranked_probe_targets = sorted(
        probe_targets,
        key=lambda candidate: speeds.get(str(candidate.get("url") or ""), 0),
        reverse=True,
    )
    selected = ranked_probe_targets[0]
    if job_id is not None:
        db.add_event(
            job_id,
            "download:probe",
            f"Selected {selected.get('label')} after speed probe",
            {
                "selected_key": selected.get("key"),
                "selected_label": selected.get("label"),
                "selected_host": safe_url_host(selected.get("url") or ""),
                "probed": event_results,
            },
        )
    remaining = [candidate for candidate in candidates if candidate not in ranked_probe_targets]
    return ranked_probe_targets + remaining


def download_candidate_event_data(candidates: list[dict[str, str]], quality_preference: str | None) -> dict[str, Any]:
    return {
        "count": len(candidates),
        "quality_preference": db.normalize_quality_preference(quality_preference),
        "candidates": [
            {
                "key": candidate.get("key"),
                "label": candidate.get("label"),
                "host": safe_url_host(str(candidate.get("url") or "")),
            }
            for candidate in candidates[:12]
        ],
        "truncated": len(candidates) > 12,
    }


async def stream_to_file(
    url: str,
    file_path: str,
    progress_cb,
    headers: dict[str, str] | None = None,
    cancel_check=None,
) -> dict[str, Any]:
    temp_path = file_path + ".part"
    headers = headers or {"User-Agent": "Mozilla/5.0 ClipNest/0.1"}
    timeout = httpx.Timeout(None, connect=20.0)
    total = 0
    expected = 0
    status_code = 0
    content_range = ""
    last_progress = 0.0
    last_progress_at = 0.0
    started_at = asyncio.get_running_loop().time()
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            async with client.stream("GET", url, headers=headers) as response:
                response.raise_for_status()
                status_code = response.status_code
                content_range = str(response.headers.get("content-range") or "")
                expected = int(response.headers.get("content-length") or 0)
                with open(temp_path, "wb") as out:
                    async for chunk in response.aiter_bytes():
                        if cancel_check and await cancel_check():
                            raise DownloadCancelled("Download cancelled")
                        if not chunk:
                            continue
                        out.write(chunk)
                        total += len(chunk)
                        if expected:
                            progress = min(95, 20 + (total / expected) * 75)
                            now = asyncio.get_running_loop().time()
                            if progress - last_progress >= 1 or now - last_progress_at >= 1:
                                last_progress = progress
                                last_progress_at = now
                                await progress_cb(progress)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise
    if cancel_check and await cancel_check():
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise DownloadCancelled("Download cancelled")
    if expected and total < expected:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise RuntimeError(f"Incomplete download: got {total} bytes, expected {expected}")
    duration = max(0.001, asyncio.get_running_loop().time() - started_at)
    os.replace(temp_path, file_path)
    return {
        "bytes": total,
        "expected_size_bytes": expected,
        "duration_seconds": round(duration, 3),
        "speed_bytes_per_second": round(total / duration, 2),
        "http_status": status_code,
        "content_range": content_range,
        "range_segments": 1,
    }


async def segmented_stream_to_file(
    url: str,
    file_path: str,
    progress_cb,
    headers: dict[str, str],
    total_size: int,
    cancel_check=None,
) -> dict[str, Any]:
    segment_size = 3 * 1024 * 1024
    segment_count = max(2, min(6, (total_size + segment_size - 1) // segment_size))
    ranges: list[tuple[int, int, str]] = []
    for index in range(segment_count):
        start = (total_size * index) // segment_count
        end = ((total_size * (index + 1)) // segment_count) - 1
        ranges.append((start, end, f"{file_path}.part.{index}"))

    lock = asyncio.Lock()
    downloaded = 0
    last_progress = 0.0
    last_progress_at = 0.0
    started_at = asyncio.get_running_loop().time()
    timeout = httpx.Timeout(None, connect=20.0)
    limits = httpx.Limits(max_connections=segment_count + 2, max_keepalive_connections=segment_count + 2)

    async def download_part(client: httpx.AsyncClient, start: int, end: int, part_path: str) -> int:
        nonlocal downloaded, last_progress, last_progress_at
        part_headers = build_video_download_headers(headers)
        part_headers["Range"] = f"bytes={start}-{end}"
        part_total = 0
        try:
            async with client.stream("GET", url, headers=part_headers) as response:
                response.raise_for_status()
                if response.status_code != 206:
                    raise RuntimeError(f"Range segment returned HTTP {response.status_code}")
                with open(part_path, "wb") as out:
                    async for chunk in response.aiter_bytes():
                        if cancel_check and await cancel_check():
                            raise DownloadCancelled("Download cancelled")
                        if not chunk:
                            continue
                        out.write(chunk)
                        chunk_size = len(chunk)
                        part_total += chunk_size
                        async with lock:
                            downloaded += chunk_size
                            progress = min(95, 20 + (downloaded / max(1, total_size)) * 75)
                            now = asyncio.get_running_loop().time()
                            if progress - last_progress >= 1 or now - last_progress_at >= 1:
                                last_progress = progress
                                last_progress_at = now
                                await progress_cb(progress)
        except Exception:
            if os.path.exists(part_path):
                os.remove(part_path)
            raise
        expected = end - start + 1
        if part_total != expected:
            if os.path.exists(part_path):
                os.remove(part_path)
            raise RuntimeError(f"Incomplete range segment: got {part_total} bytes, expected {expected}")
        return part_total

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, limits=limits) as client:
            part_sizes = await asyncio.gather(
                *(download_part(client, start, end, part_path) for start, end, part_path in ranges)
            )
        with open(file_path + ".part", "wb") as out:
            for _, _, part_path in ranges:
                with open(part_path, "rb") as part:
                    while chunk := part.read(1024 * 1024):
                        out.write(chunk)
                os.remove(part_path)
        os.replace(file_path + ".part", file_path)
    except Exception:
        if os.path.exists(file_path + ".part"):
            os.remove(file_path + ".part")
        for _, _, part_path in ranges:
            if os.path.exists(part_path):
                os.remove(part_path)
        raise

    total = sum(part_sizes)
    if total != total_size:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise RuntimeError(f"Incomplete segmented download: got {total} bytes, expected {total_size}")
    duration = max(0.001, asyncio.get_running_loop().time() - started_at)
    return {
        "bytes": total,
        "expected_size_bytes": total_size,
        "duration_seconds": round(duration, 3),
        "speed_bytes_per_second": round(total / duration, 2),
        "http_status": 206,
        "content_range": f"bytes */{total_size}",
        "range_segments": segment_count,
    }


async def download_with_fallback(
    candidates: list[dict[str, str]],
    file_path: str,
    headers: dict[str, str],
    progress_cb,
    update_cb,
    job_id: int | None = None,
    cancel_check=None,
) -> dict[str, Any]:
    errors: list[str] = []
    candidates = await reorder_candidates_by_probe(candidates, headers, job_id=job_id)
    total_candidates = len(candidates)
    for index, candidate in enumerate(candidates):
        label = candidate["label"]
        url = candidate["url"]
        await update_cb(
            status="downloading",
            progress=20,
            message=f"Downloading: {label}",
            file_path=file_path,
        )
        if job_id is not None:
            db.add_event(
                job_id,
                "download:attempt",
                f"Downloading with {label}",
                {
                    "attempt": index + 1,
                    "total": total_candidates,
                    "key": candidate.get("key"),
                    "label": label,
                    "host": safe_url_host(url),
                },
            )
        try:
            video_headers = build_video_download_headers(headers)
            probe = await probe_range_size(url, video_headers)
            if probe.get("range_supported") and int(probe.get("total_size") or 0) >= 64 * 1024 * 1024:
                try:
                    result = await segmented_stream_to_file(
                        url,
                        file_path,
                        progress_cb,
                        headers=headers,
                        total_size=int(probe["total_size"]),
                        cancel_check=cancel_check,
                    )
                except DownloadCancelled:
                    raise
                except Exception as segment_exc:
                    if job_id is not None:
                        db.add_event(
                            job_id,
                            "download:segment_failed",
                            f"Segmented download failed, falling back: {type(segment_exc).__name__}",
                            {
                                "attempt": index + 1,
                                "key": candidate.get("key"),
                                "label": label,
                                "host": safe_url_host(url),
                                "error": str(segment_exc)[:240],
                            },
                        )
                    result = await stream_to_file(
                        url,
                        file_path,
                        progress_cb,
                        headers=video_headers,
                        cancel_check=cancel_check,
                    )
            else:
                result = await stream_to_file(
                    url,
                    file_path,
                    progress_cb,
                    headers=video_headers,
                    cancel_check=cancel_check,
                )
            if job_id is not None:
                success_message = download_summary(label, result)
                db.add_event(
                    job_id,
                    "download:success",
                    success_message,
                    {
                        "attempt": index + 1,
                        "total": total_candidates,
                        "key": candidate.get("key"),
                        "label": label,
                        "host": safe_url_host(url),
                        "bytes": result["bytes"],
                        "expected_size_bytes": result["expected_size_bytes"],
                        "duration_seconds": result["duration_seconds"],
                        "speed_bytes_per_second": result["speed_bytes_per_second"],
                        "http_status": result["http_status"],
                        "content_range": result["content_range"],
                        "range_request": True,
                        "range_segments": result.get("range_segments") or 1,
                    },
                )
            return {
                **result,
                "key": candidate.get("key"),
                "label": label,
                "host": safe_url_host(url),
            }
        except DownloadCancelled:
            raise
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            errors.append(f"{label}: HTTP {status_code}")
            if job_id is not None:
                db.add_event(
                    job_id,
                    "download:failed",
                    f"{label} returned HTTP {status_code}",
                    {
                        "attempt": index + 1,
                        "total": total_candidates,
                        "key": candidate.get("key"),
                        "label": label,
                        "host": safe_url_host(url),
                        "status_code": status_code,
                    },
                )
        except Exception as exc:
            errors.append(f"{label}: {type(exc).__name__}: {exc}")
            if job_id is not None:
                db.add_event(
                    job_id,
                    "download:failed",
                    f"{label} failed: {type(exc).__name__}",
                    {
                        "attempt": index + 1,
                        "total": total_candidates,
                        "key": candidate.get("key"),
                        "label": label,
                        "host": safe_url_host(url),
                        "error": str(exc)[:240],
                    },
                )
    raise RuntimeError("All download candidates failed: " + "; ".join(errors))


def inspect_media(file_path: str) -> dict[str, Any]:
    result = {"resolution": None, "codec": None, "duration_seconds": None}
    try:
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-i", file_path],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except Exception:
        return result
    output = (proc.stderr or "") + (proc.stdout or "")
    video_match = re.search(r"Video:\s*([^,\s]+).*?(\d{3,5})x(\d{3,5})", output)
    if video_match:
        result["codec"] = video_match.group(1)
        result["resolution"] = f"{video_match.group(2)}x{video_match.group(3)}"
    duration_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", output)
    if duration_match:
        hours, minutes, seconds = duration_match.groups()
        result["duration_seconds"] = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    return result


def generate_preview(file_path: str, preview_path: str) -> str | None:
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-ss",
                "1",
                "-i",
                file_path,
                "-frames:v",
                "1",
                "-vf",
                "scale=480:-1",
                preview_path,
            ],
            capture_output=True,
            timeout=30,
        )
    except Exception:
        return None
    return preview_path if os.path.exists(preview_path) else None


def fresh_cached_payload(job: dict[str, Any]) -> dict[str, Any] | None:
    payload = job.get("metadata")
    if not isinstance(payload, dict):
        return None
    cache = payload.get("_clipnest_parse_cache")
    if not isinstance(cache, dict):
        return None
    try:
        expires_at = datetime.fromisoformat(str(cache.get("expires_at") or ""))
    except ValueError:
        return None
    if expires_at <= datetime.now(timezone.utc):
        return None
    return payload if payload.get("type") == "video" else None


async def process_download(job: dict[str, Any], update_cb, cancel_check=None) -> None:
    job_id = int(job["id"])
    parser_settings = db.get_parser_settings(include_secret=True)
    parser = ParserClient(parser_settings=parser_settings)
    app_settings = db.get_app_settings()
    payload = fresh_cached_payload(job)
    async def ensure_not_cancelled() -> None:
        if cancel_check and await cancel_check():
            raise DownloadCancelled("Download cancelled")

    if payload:
        cache = payload.get("_clipnest_parse_cache") or {}
        db.add_event(job_id, "parse:cache", "Using cached parse result", {"cache_id": cache.get("id")})
        await update_cb(status="parsing", progress=10, message="Using parsed result")
    else:
        await update_cb(status="parsing", progress=5, message="Parsing")
        payload = await parser.parse(job["url"])
    await ensure_not_cancelled()
    author = author_name_from_payload(payload)
    video_data = payload.get("video_data") or {}
    parser_source = str(payload.get("parser_source") or parser.adapter.name)
    bit_rate_count = len(video_data.get("bit_rate_candidates") or [])
    db.add_event(
        job_id,
        "parse:success",
        f"Parsed via {parser.adapter.name} / {parser_source}",
        {
            "adapter": parser.adapter.name,
            "source": parser_source,
            "video_id": str(payload.get("video_id") or ""),
            "bit_rate_candidates": bit_rate_count,
            "warning": payload.get("parser_warning"),
        },
    )
    file_path, preview_path = build_paths(payload, app_settings=app_settings)
    cover_url = cover_url_from_payload(payload)
    avatar_url = author_avatar_url_from_payload(payload)
    cover_path = ""
    avatar_path = ""
    asset_headers = build_download_headers(payload, parser_settings)
    try:
        if cover_url:
            cover_path = await cache_remote_image(cover_url, "covers", headers=asset_headers)
        if avatar_url:
            avatar_path = await cache_remote_image(avatar_url, "avatars", headers=asset_headers)
    except Exception as exc:
        db.add_event(job_id, "asset:cache_failed", f"Asset cache failed: {exc}", {"error": str(exc)})
    await update_cb(
        platform=payload.get("platform"),
        video_id=str(payload.get("video_id") or ""),
        author_name=author,
        author_id=str((payload.get("author") or {}).get("uid", "")) if isinstance(payload.get("author"), dict) else "",
        description=str(payload.get("desc") or ""),
        title=str(payload.get("desc") or ""),
        cover_url=cover_url,
        cover_path=cover_path or None,
        author_avatar_url=avatar_url,
        author_avatar_path=avatar_path or None,
        metadata=payload,
    )

    if payload.get("type") == "image":
        image_data = payload.get("image_data") or {}
        image_urls = [
            str(url or "").strip()
            for url in (
                image_data.get("no_watermark_image_list")
                or image_data.get("watermark_image_list")
                or []
            )
            if str(url or "").strip()
        ]
        if not image_urls:
            raise RuntimeError("Parser did not return downloadable image URLs")
        image_paths = build_image_paths(payload, app_settings=app_settings, count=len(image_urls))
        if app_settings.get("skip_existing", True) and image_paths and os.path.exists(image_paths[0]):
            await update_cb(
                status="finished",
                progress=100,
                message="Already downloaded",
                file_path=image_paths[0],
                preview_path=image_paths[0],
                size_bytes=sum(os.path.getsize(path) for path in image_paths if os.path.exists(path)),
                expected_size_bytes=sum(os.path.getsize(path) for path in image_paths if os.path.exists(path)),
                error_type="",
                next_attempt_at=None,
                finished_at=utc_now(),
            )
            return
        db.add_event(
            job_id,
            "download:candidates",
            f"Prepared {len(image_urls)} image downloads",
            {
                "count": len(image_urls),
                "type": "image",
                "candidates": [{"host": safe_url_host(url), "label": f"image {index + 1}"} for index, url in enumerate(image_urls[:12])],
                "truncated": len(image_urls) > 12,
            },
        )
        headers = build_download_headers(payload, parser_settings)
        total_size = 0
        total_expected = 0
        first_host = safe_url_host(image_urls[0])
        for index, (url, path) in enumerate(zip(image_urls, image_paths, strict=False)):
            await ensure_not_cancelled()
            await update_cb(
                status="downloading",
                progress=20 + (index / max(1, len(image_urls))) * 75,
                message=f"Downloading image {index + 1}/{len(image_urls)}",
                file_path=image_paths[0],
            )

            async def image_progress(progress: float, image_index=index):
                base = 20 + (image_index / max(1, len(image_urls))) * 75
                span = 75 / max(1, len(image_urls))
                await update_cb(progress=round(min(95, base + (progress / 100) * span), 2))

            result = await stream_to_file(url, path, image_progress, headers=headers, cancel_check=cancel_check)
            total_size += result["bytes"]
            total_expected += result["expected_size_bytes"]
        await update_cb(
            status="finished",
            progress=100,
            message=f"Finished {len(image_urls)} images",
            file_path=image_paths[0],
            preview_path=image_paths[0],
            size_bytes=total_size,
            expected_size_bytes=total_expected or None,
            download_key="image_set",
            download_label=f"{len(image_urls)} images",
            download_host=first_host,
            error_type="",
            next_attempt_at=None,
            finished_at=utc_now(),
        )
        return

    if payload.get("type") != "video":
        raise RuntimeError(f"Unsupported job type: {payload.get('type')}")

    duplicate = db.find_finished_video(str(payload.get("platform") or ""), str(payload.get("video_id") or ""), job_id)
    if app_settings.get("skip_existing", True) and duplicate and duplicate.get("file_path") and os.path.exists(duplicate["file_path"]):
        db.add_event(
            job_id,
            "duplicate",
            f"Reusing downloaded file from job #{duplicate.get('id')}",
            {"source_job_id": duplicate.get("id"), "file_path": duplicate.get("file_path")},
        )
        await update_cb(
            status="finished",
            progress=100,
            message=f"Already downloaded as job #{duplicate.get('id')}",
            file_path=duplicate.get("file_path"),
            preview_path=duplicate.get("preview_path"),
            size_bytes=duplicate.get("size_bytes"),
            expected_size_bytes=duplicate.get("expected_size_bytes") or duplicate.get("size_bytes"),
            duration_seconds=duplicate.get("duration_seconds"),
            resolution=duplicate.get("resolution"),
            codec=duplicate.get("codec"),
            download_key=duplicate.get("download_key"),
            download_label=duplicate.get("download_label"),
            download_host=duplicate.get("download_host"),
            error_type="",
            next_attempt_at=None,
            finished_at=utc_now(),
        )
        return

    if app_settings.get("skip_existing", True) and os.path.exists(file_path):
        media = inspect_media(file_path)
        await update_cb(
            status="finished",
            progress=100,
            message="Already downloaded",
            file_path=file_path,
            preview_path=preview_path if os.path.exists(preview_path) else None,
            size_bytes=os.path.getsize(file_path),
            expected_size_bytes=os.path.getsize(file_path),
            error_type="",
            next_attempt_at=None,
            finished_at=utc_now(),
            **media,
        )
        return

    download_candidates = video_download_candidates(
        video_data,
        quality_preference=job.get("quality_preference") or "best",
    )
    if not download_candidates:
        raise RuntimeError("Parser did not return a downloadable video URL")
    db.add_event(
        job_id,
        "download:candidates",
        f"Prepared {len(download_candidates)} download candidates",
        download_candidate_event_data(download_candidates, job.get("quality_preference") or "best"),
    )

    async def progress_cb(progress: float):
        await update_cb(progress=round(progress, 2))

    await ensure_not_cancelled()
    download_info = await download_with_fallback(
        download_candidates,
        file_path,
        build_download_headers(payload, parser_settings),
        progress_cb,
        update_cb,
        job_id=job_id,
        cancel_check=cancel_check,
    )
    await update_cb(
        download_key=download_info.get("key"),
        download_label=download_info.get("label"),
        download_host=download_info.get("host"),
        expected_size_bytes=download_info.get("expected_size_bytes") or None,
    )
    await ensure_not_cancelled()
    await update_cb(progress=96, message="Inspecting")
    media = await asyncio.to_thread(inspect_media, file_path)
    await ensure_not_cancelled()
    preview = await asyncio.to_thread(generate_preview, file_path, preview_path)
    await update_cb(
        status="finished",
        progress=100,
        message="Finished",
        file_path=file_path,
        preview_path=preview,
        size_bytes=download_info.get("bytes") or os.path.getsize(file_path),
        error_type="",
        next_attempt_at=None,
        finished_at=utc_now(),
        **media,
    )
