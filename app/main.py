from contextlib import asynccontextmanager
import hashlib
import hmac
import html
import ipaddress
import math
import os
from pathlib import Path
import re
import time
from typing import Annotated
from urllib.parse import urlsplit

import httpx
from fastapi import Body, Cookie, Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from . import db, runtime_state
from .assets import ASSET_ROOT, author_avatar_url_from_payload, cache_remote_image, cover_url_from_payload
from .config import settings
from .downloader import build_download_headers, ordered_bit_rate_candidates, relative_media_path
from .notifier import send_telegram
from .parser import NativeBilibiliParserAdapter, NativeDouyinParserAdapter, NativeTikTokParserAdapter, ParserClient, author_name_from_payload
from .telegram_bot import TelegramBotWorker
from .worker import AuthorCrawlWorker, DownloadWorker


worker = DownloadWorker()
author_worker = AuthorCrawlWorker()
telegram_bot_worker = TelegramBotWorker()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


class JobCreate(BaseModel):
    url: str = Field(min_length=8)
    quality_preference: str | None = Field(default=None, max_length=20)
    parse_cache_id: str | None = Field(default=None, max_length=80)


class JobBatchCreate(BaseModel):
    urls: list[str] = Field(default_factory=list)
    text: str | None = None
    quality_preference: str | None = Field(default=None, max_length=20)


class PushCreate(BaseModel):
    url: str | None = None
    urls: list[str] = Field(default_factory=list)
    text: str | None = None
    quality_preference: str | None = Field(default=None, max_length=20)
    cover_url: str | None = Field(default=None, max_length=3000)
    dry_run: bool = False


class AuthorCrawlCreate(BaseModel):
    url: str = Field(min_length=8)
    author_name: str | None = Field(default=None, max_length=120)
    sec_uid: str | None = Field(default=None, max_length=220)
    sync_source_id: int | None = None
    max_items: int = Field(default=200, ge=1, le=1000)
    max_pages: int = Field(default=80, ge=1, le=100)
    delay_ms: int = Field(default=600, ge=0, le=5000)
    quality_preference: str | None = Field(default=None, max_length=20)
    sync_mode: str | None = Field(default=None, max_length=20)
    dry_run: bool = False


class AuthorSyncSourceCreate(BaseModel):
    url: str | None = Field(default=None, max_length=2000)
    author_name: str | None = Field(default=None, max_length=120)
    sec_uid: str | None = Field(default=None, max_length=220)
    platform: str | None = Field(default="douyin", max_length=40)
    enabled: bool = True
    sync_mode: str | None = Field(default="incremental", max_length=20)
    max_items: int = Field(default=200, ge=1, le=1000)
    max_pages: int = Field(default=80, ge=1, le=100)
    delay_ms: int = Field(default=600, ge=0, le=5000)
    quality_preference: str | None = Field(default=None, max_length=20)
    include_images: bool = False
    stop_after_existing_pages: int = Field(default=2, ge=1, le=20)
    stop_after_existing_items: int = Field(default=36, ge=1, le=300)
    notes: str | None = Field(default=None, max_length=500)


class AuthorSyncSourceUpdate(BaseModel):
    url: str | None = Field(default=None, max_length=2000)
    author_name: str | None = Field(default=None, max_length=120)
    sec_uid: str | None = Field(default=None, max_length=220)
    platform: str | None = Field(default=None, max_length=40)
    enabled: bool | None = None
    sync_mode: str | None = Field(default=None, max_length=20)
    max_items: int | None = Field(default=None, ge=1, le=1000)
    max_pages: int | None = Field(default=None, ge=1, le=100)
    delay_ms: int | None = Field(default=None, ge=0, le=5000)
    quality_preference: str | None = Field(default=None, max_length=20)
    include_images: bool | None = None
    stop_after_existing_pages: int | None = Field(default=None, ge=1, le=20)
    stop_after_existing_items: int | None = Field(default=None, ge=1, le=300)
    notes: str | None = Field(default=None, max_length=500)


class AuthorSyncBatchCrawl(BaseModel):
    source_ids: list[int] = Field(default_factory=list, max_length=2000)
    sync_mode: str | None = Field(default=None, max_length=20)
    enabled_only: bool = True


class AuthorSyncBatchUpdate(BaseModel):
    source_ids: list[int] = Field(default_factory=list, max_length=500)
    enabled: bool | None = None
    sync_mode: str | None = Field(default=None, max_length=20)
    max_items: int | None = Field(default=None, ge=1, le=1000)
    max_pages: int | None = Field(default=None, ge=1, le=100)
    include_images: bool | None = None
    stop_after_existing_pages: int | None = Field(default=None, ge=1, le=20)
    stop_after_existing_items: int | None = Field(default=None, ge=1, le=300)
    delete: bool = False


class ParsePreviewCreate(BaseModel):
    url: str = Field(min_length=8)


class JobRetry(BaseModel):
    force: bool = False
    quality_preference: str | None = Field(default=None, max_length=20)
    parse_cache_id: str | None = Field(default=None, max_length=80)


class JobBulkAction(BaseModel):
    job_ids: list[int] = Field(default_factory=list, max_length=200)
    force: bool = False
    delete_file: bool = False


class SessionCreate(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class SetupCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=8, max_length=200)
    confirm_password: str = Field(min_length=8, max_length=200)


class AppSettingsUpdate(BaseModel):
    skip_existing: bool | None = None
    author_folders: bool | None = None
    filename_template: str | None = Field(default=None, max_length=180)
    queue_paused: bool | None = None
    max_concurrent_downloads: int | None = None
    auto_retry_attempts: int | None = None
    auto_retry_delay_seconds: int | None = None
    telegram_enabled: bool | None = None
    telegram_bot_token: str | None = Field(default=None, max_length=300)
    telegram_chat_id: str | None = Field(default=None, max_length=120)
    telegram_notify_success: bool | None = None
    telegram_notify_failure: bool | None = None


class TelegramTestCreate(BaseModel):
    telegram_bot_token: str | None = Field(default=None, max_length=300)
    telegram_chat_id: str | None = Field(default=None, max_length=120)


class ParserSettingsUpdate(BaseModel):
    parser_adapter: str | None = None
    douyin_cookie: str | None = Field(default=None, max_length=20000)
    douyin_user_agent: str | None = Field(default=None, max_length=500)
    tiktok_cookie: str | None = Field(default=None, max_length=20000)
    tiktok_user_agent: str | None = Field(default=None, max_length=500)
    bilibili_cookie: str | None = Field(default=None, max_length=20000)
    bilibili_user_agent: str | None = Field(default=None, max_length=500)


RUNNING_STATUSES = {"parsing", "downloading", "cancelling"}
CANCELABLE_STATUSES = {"queued", "retry", "parsing", "downloading"}
URL_RE = re.compile(r"https?://\S+")
TRAILING_URL_PUNCTUATION = ".,;)" + "\uff0c\u3002\uff1b"
SESSION_COOKIE_NAME = "clipnest_session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 30
PASSWORD_HASH_ITERATIONS = 260_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_HASH_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt_hex, digest_hex = password_hash.split("$", 3)
        iterations = int(iterations_text)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (ValueError, TypeError):
        return False
    if algorithm != "pbkdf2_sha256" or iterations < 100_000:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def normalize_auth_username(username: str) -> str:
    clean = str(username or "").strip()
    if not clean:
        return ""
    return re.sub(r"\s+", "", clean)[:80]


def sign_session(password_hash: str, created_at: int | None = None) -> str:
    timestamp = str(created_at or int(time.time()))
    message = f"v2|{timestamp}".encode("utf-8")
    signature = hmac.new(
        f"{settings.api_token}:{password_hash}".encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()
    return f"v2.{timestamp}.{signature}"


def verify_session(value: str | None) -> bool:
    if not value:
        return False
    try:
        version, timestamp_text, signature = value.split(".", 2)
        timestamp = int(timestamp_text)
    except ValueError:
        return False
    if version != "v2":
        return False
    if time.time() - timestamp > SESSION_MAX_AGE_SECONDS:
        return False
    admin = db.get_auth_admin()
    if not admin:
        return False
    expected = sign_session(admin["password_hash"], timestamp)
    return hmac.compare_digest(value, expected)


def create_session_cookie(response: Response, admin: dict[str, str]) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=sign_session(admin["password_hash"]),
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )


def extract_token(
    authorization: Annotated[str | None, Header()] = None,
    x_api_token: Annotated[str | None, Header()] = None,
    clipnest_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
    token: str | None = Query(default=None),
) -> str:
    if x_api_token:
        return x_api_token
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    if verify_session(clipnest_session):
        return settings.api_token
    return token or ""


def require_token(token: Annotated[str, Depends(extract_token)]) -> None:
    if settings.api_token and token != settings.api_token:
        raise HTTPException(status_code=401, detail="Invalid API token")


def clean_url(value: str) -> str:
    return value.strip().rstrip(TRAILING_URL_PUNCTUATION)


def diagnose_error_text(error: str | None, platform: str | None = None) -> dict:
    raw = str(error or "").strip()
    lower = raw.lower()
    clean_platform = str(platform or "").strip().lower()
    if not raw:
        return {"code": "", "message": "", "suggestion": ""}
    if "cookie" in lower or "login" in lower or "captcha" in lower:
        return {
            "code": "cookie_or_login",
            "message": f"{clean_platform or '平台'} Cookie 可能失效或需要重新登录",
            "suggestion": "更新 Cookie 后重试，必要时重新打开浏览器获取完整 Cookie。",
        }
    if "403" in lower or "forbidden" in lower:
        return {
            "code": "http_403",
            "message": "平台拒绝访问链接",
            "suggestion": "更新 Cookie、确认网络/地区可访问，稍后重试。",
        }
    if "404" in lower or "not found" in lower:
        return {
            "code": "http_404",
            "message": "作品可能已删除、私密或链接无效",
            "suggestion": "检查原链接是否能在浏览器直接打开。",
        }
    if "timeout" in lower or "timed out" in lower:
        return {
            "code": "timeout",
            "message": "网络请求超时",
            "suggestion": "检查网络、DNS、代理或稍后重试。",
        }
    if clean_platform == "tiktok" and any(key in lower for key in ("region", "signature", "aweme", "web json", "rehydration")):
        return {
            "code": "tiktok_region_or_signature",
            "message": "TikTok 解析受地区、登录态或页面结构影响",
            "suggestion": "确认服务器可访问 TikTok，补充 TikTok Cookie 后重试。",
        }
    return {"code": "unknown", "message": raw.splitlines()[0][:300], "suggestion": "查看任务详情里的原始错误。"}


def collect_urls(payload: JobBatchCreate) -> list[str]:
    candidates = list(payload.urls)
    if payload.text:
        candidates.extend(URL_RE.findall(payload.text))
    cleaned: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        url = clean_url(candidate)
        if len(url) < 8 or url in seen:
            continue
        cleaned.append(url)
        seen.add(url)
    return cleaned


def push_payload_to_batch(payload: PushCreate) -> JobBatchCreate:
    urls = list(payload.urls)
    if payload.url:
        urls.insert(0, payload.url)
    return JobBatchCreate(urls=urls, text=payload.text, quality_preference=payload.quality_preference)


def create_push_jobs(urls: list[str], quality_preference: str | None = None) -> list[dict]:
    return [db.create_job_or_reuse_finished(url, quality_preference=quality_preference) for url in urls]


def clean_cover_url(value: str | None) -> str:
    raw = html.unescape(str(value or "").strip())
    if not raw.startswith(("http://", "https://")):
        return ""
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return ""
    host = (parsed.hostname or "").lower()
    if host == "douyinpic.com" or host.endswith(".douyinpic.com"):
        return raw
    return ""


async def attach_pushed_cover(job: dict, cover_url: str | None) -> bool:
    clean = clean_cover_url(cover_url)
    job_id = int(job.get("id") or 0)
    if not clean or not job_id:
        return False
    headers = {
        "User-Agent": settings.douyin_user_agent or "Mozilla/5.0 ClipNest/0.1",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Referer": "https://www.douyin.com/",
    }
    try:
        cover_path = await cache_remote_image(clean, "covers", headers=headers)
    except Exception as exc:
        db.add_event(job_id, "push:cover_failed", f"Push cover cache failed: {exc}", {"cover_url": clean})
        return False
    db.update_job(job_id, cover_url=clean, cover_path=cover_path, preview_path=cover_path)
    db.add_event(job_id, "push:cover", "Using cover from browser push", {"cover_url": clean})
    job["cover_url"] = clean
    job["cover_path"] = cover_path
    job["preview_path"] = cover_path
    return True


def push_summary(
    *,
    urls: list[str],
    jobs: list[dict] | None = None,
    dry_run: bool = False,
    cover_attached: bool = False,
) -> dict:
    jobs = jobs or []
    reused_count = sum(1 for item in jobs if item.get("reused"))
    created_count = len(jobs) - reused_count
    if dry_run:
        message = f"预检通过：识别到 {len(urls)} 个链接"
    elif created_count and reused_count:
        message = f"已加入 {created_count} 个下载任务，{reused_count} 个已存在媒体库"
    elif reused_count:
        message = f"视频已存在媒体库：{reused_count} 个"
    else:
        message = f"已加入下载队列：{created_count} 个"
    return {
        "dry_run": dry_run,
        "count": len(urls) if dry_run else len(jobs),
        "created_count": created_count,
        "reused_count": reused_count,
        "cover_attached": cover_attached,
        "message": message,
    }


def resolve_media_path(path: str | None) -> Path | None:
    if not path:
        return None
    resolved = Path(path).resolve()
    download_root = Path(settings.download_dir).resolve()
    if download_root not in resolved.parents and resolved != download_root:
        raise HTTPException(status_code=403, detail="Invalid media path")
    return resolved


def remove_job_files(job_data: dict) -> list[str]:
    removed: list[str] = []
    seen: set[Path] = set()
    for field in ("file_path", "preview_path"):
        resolved = resolve_media_path(job_data.get(field))
        if not resolved or resolved in seen:
            continue
        seen.add(resolved)
        if resolved.exists() and resolved.is_file():
            resolved.unlink()
            removed.append(str(resolved))
    return removed


def first_cover_url(payload: dict) -> str:
    return cover_url_from_payload(payload)


def image_proxy_headers(url: str) -> dict[str, str]:
    host = (urlsplit(url).hostname or "").lower()
    parser_settings = db.get_parser_settings(include_secret=True)
    headers = {
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "User-Agent": settings.douyin_user_agent,
    }
    if "bilibili.com" in host or "hdslb.com" in host:
        headers["Referer"] = "https://www.bilibili.com/"
        headers["User-Agent"] = str(parser_settings.get("bilibili_user_agent") or settings.bilibili_user_agent)
        cookie = str(parser_settings.get("bilibili_cookie") or settings.bilibili_cookie or "").strip()
        if cookie:
            headers["Cookie"] = cookie
    elif "douyin.com" in host or "douyinpic.com" in host or "douyinstatic.com" in host:
        headers["Referer"] = "https://www.douyin.com/"
        headers["User-Agent"] = str(parser_settings.get("douyin_user_agent") or settings.douyin_user_agent)
    elif "tiktok.com" in host or "tiktokcdn" in host:
        headers["Referer"] = "https://www.tiktok.com/"
        headers["User-Agent"] = str(parser_settings.get("tiktok_user_agent") or settings.tiktok_user_agent)
    return headers


def is_private_proxy_host(host: str) -> bool:
    if not host:
        return True
    lowered = host.lower().strip("[]")
    if lowered in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        address = ipaddress.ip_address(lowered)
    except ValueError:
        return False
    return address.is_private or address.is_loopback or address.is_link_local or address.is_multicast


def format_quality_option(item: dict) -> dict:
    width = int(item.get("width") or 0)
    height = int(item.get("height") or 0)
    shorter = int(item.get("quality_height") or 0) or (min(width, height) if width and height else max(width, height))
    fps = int(item.get("fps") or 0)
    codec = str(item.get("codec") or ("H.265" if item.get("is_h265") else "H.264"))
    quality_label = str(item.get("quality_label") or "").strip()
    label_parts = [quality_label or (f"{shorter}P" if shorter else "自动"), f"{width}x{height}" if width and height else ""]
    if fps:
        label_parts.append(f"{fps}fps")
    label_parts.append(codec)
    return {
        "value": str(shorter or "best"),
        "label": " · ".join(part for part in label_parts if part),
        "resolution": f"{width}x{height}" if width and height else "",
        "fps": fps,
        "codec": codec,
        "bit_rate": int(item.get("bit_rate") or 0),
        "data_size": int(item.get("data_size") or 0),
    }


def quality_options_from_payload(payload: dict) -> list[dict]:
    video_data = payload.get("video_data") or {}
    rates = ordered_bit_rate_candidates(video_data, "best")
    options: list[dict] = []
    if rates:
        best = format_quality_option(rates[0])
        options.append({**best, "value": "best", "label": f"最高 · {best['label']}"})
    seen: set[str] = set()
    for item in rates:
        option = format_quality_option(item)
        value = option["value"]
        if value == "best" or value in seen:
            continue
        seen.add(value)
        options.append(option)
    return options or [{"value": "best", "label": "最高", "resolution": "", "fps": 0, "codec": "", "bit_rate": 0, "data_size": 0}]


def parse_diagnostics_from_payload(payload: dict) -> dict:
    video_data = payload.get("video_data") or {}
    candidates = video_data.get("bit_rate_candidates") or []
    qualities = (
        quality_options_from_payload(payload)
        if payload.get("type") == "video"
        else [{"value": "best", "label": "全部图片", "resolution": "", "fps": 0, "codec": "image", "bit_rate": 0, "data_size": 0}]
    )
    best = qualities[0] if qualities else {}
    return {
        "type": payload.get("type"),
        "platform": payload.get("platform"),
        "video_id": str(payload.get("video_id") or ""),
        "title": str(payload.get("desc") or ""),
        "author_name": author_name_from_payload(payload),
        "cover_url": first_cover_url(payload),
        "parser_source": str(payload.get("parser_source") or ""),
        "parser_warning": str(payload.get("parser_warning") or ""),
        "bit_rate_candidates": len(candidates) if isinstance(candidates, list) else 0,
        "best_quality": best,
        "qualities": qualities,
    }


async def cache_job_assets(payload: dict, parser_settings: dict) -> dict[str, str]:
    updates: dict[str, str] = {}
    headers = build_download_headers(payload, parser_settings)
    cover_url = cover_url_from_payload(payload)
    avatar_url = author_avatar_url_from_payload(payload)
    if cover_url:
        updates["cover_path"] = await cache_remote_image(cover_url, "covers", headers=headers)
    if avatar_url:
        updates["author_avatar_url"] = avatar_url
        updates["author_avatar_path"] = await cache_remote_image(avatar_url, "avatars", headers=headers)
    return updates


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    Path(settings.download_dir).mkdir(parents=True, exist_ok=True)
    if settings.worker_enabled:
        worker.start()
        author_worker.start()
    telegram_bot_worker.start()
    try:
        yield
    finally:
        await telegram_bot_worker.stop()
        if settings.worker_enabled:
            await worker.stop()
            await author_worker.stop()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")
TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
if TOOLS_DIR.exists():
    app.mount("/tools", StaticFiles(directory=str(TOOLS_DIR)), name="tools")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, clipnest_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None):
    if not db.auth_admin_configured():
        return RedirectResponse("/login?setup=1", status_code=302)
    if not verify_session(clipnest_session):
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "app_name": settings.app_name,
        },
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, clipnest_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None):
    setup_required = not db.auth_admin_configured()
    if not setup_required and verify_session(clipnest_session):
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "app_name": settings.app_name,
            "setup_required": setup_required,
        },
    )


@app.get("/api/session", dependencies=[Depends(require_token)])
async def session_status():
    admin = db.get_auth_admin()
    return {
        "authenticated": True,
        "setup_required": admin is None,
        "username": admin["username"] if admin else "",
        "max_age": SESSION_MAX_AGE_SECONDS,
    }


@app.post("/api/setup")
async def setup_admin(payload: SetupCreate, response: Response):
    if db.auth_admin_configured():
        raise HTTPException(status_code=409, detail="Admin account already exists")
    username = normalize_auth_username(payload.username)
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if payload.password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    admin = db.set_auth_admin(username, hash_password(payload.password))
    create_session_cookie(response, admin)
    return {"authenticated": True, "username": admin["username"], "max_age": SESSION_MAX_AGE_SECONDS}


@app.post("/api/session")
async def create_session(payload: SessionCreate, response: Response):
    admin = db.get_auth_admin()
    if not admin:
        raise HTTPException(status_code=409, detail="Admin account has not been initialized")
    username = normalize_auth_username(payload.username)
    if not hmac.compare_digest(username, admin["username"]) or not verify_password(payload.password, admin["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    create_session_cookie(response, admin)
    return {"authenticated": True, "username": admin["username"], "max_age": SESSION_MAX_AGE_SECONDS}


@app.delete("/api/session")
async def delete_session(response: Response):
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return {"authenticated": False}


@app.get("/api/settings", dependencies=[Depends(require_token)])
async def app_settings():
    return db.get_public_app_settings()


@app.patch("/api/settings", dependencies=[Depends(require_token)])
async def update_app_settings(payload: AppSettingsUpdate):
    db.update_app_settings(payload.model_dump(exclude_unset=True))
    return db.get_public_app_settings()


@app.post("/api/settings/telegram/test", dependencies=[Depends(require_token)])
async def test_telegram(payload: TelegramTestCreate):
    app_settings = db.get_app_settings()
    token = str(payload.telegram_bot_token or app_settings.get("telegram_bot_token") or "").strip()
    chat_id = str(
        payload.telegram_chat_id
        if payload.telegram_chat_id is not None
        else app_settings.get("telegram_chat_id") or ""
    ).strip()
    if not token:
        raise HTTPException(status_code=400, detail="Telegram Bot Token 未配置")
    if not chat_id:
        raise HTTPException(status_code=400, detail="Telegram Chat ID 未配置")
    test_settings = {
        **app_settings,
        "telegram_bot_token": token,
        "telegram_chat_id": chat_id,
    }
    try:
        await send_telegram(
            test_settings,
            "ClipNest Telegram 测试通知\n如果你收到这条消息，说明 TG 通知配置已经生效。",
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Telegram 测试发送失败：{exc}") from exc
    return {"ok": True, "message": "Telegram 测试消息已发送"}


@app.get("/api/parser/settings", dependencies=[Depends(require_token)])
async def parser_settings():
    return db.get_parser_settings()


@app.patch("/api/parser/settings", dependencies=[Depends(require_token)])
async def update_parser_settings(payload: ParserSettingsUpdate):
    try:
        return db.update_parser_settings(payload.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/parser", dependencies=[Depends(require_token)])
async def parser_info():
    return ParserClient().info()


@app.get("/api/parser/health", dependencies=[Depends(require_token)])
async def parser_health():
    return await ParserClient().health()


@app.get("/api/tiktok/diagnostics", dependencies=[Depends(require_token)])
async def tiktok_diagnostics(limit: int = Query(default=10, ge=1, le=50)):
    parser_settings = db.get_parser_settings(include_secret=False)
    adapter = NativeTikTokParserAdapter(parser_settings=db.get_parser_settings(include_secret=True))
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT id, url, status, error, error_type, message, updated_at, created_at
            FROM jobs
            WHERE COALESCE(platform, '') = 'tiktok'
              AND status IN ('failed', 'retry')
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    failures = []
    for row in rows:
        item = dict(row)
        item["diagnosis"] = diagnose_error_text(item.get("error") or item.get("message"), "tiktok")
        failures.append(item)
    health_info = await adapter.health()
    cookie_configured = bool(parser_settings.get("tiktok_cookie_configured"))
    suggestions = []
    if not cookie_configured:
        suggestions.append("建议配置 TikTok Cookie，部分地区或登录态视频需要 Cookie 才能解析。")
    if failures:
        suggestions.append("最近有 TikTok 失败任务，可以先从失败任务重试或查看详情。")
    return {
        "ok": True,
        "platform": "tiktok",
        "cookie_configured": cookie_configured,
        "cookie_source": parser_settings.get("tiktok_cookie_source"),
        "adapter": health_info,
        "recent_failures": failures,
        "suggestions": suggestions,
    }


@app.post("/api/parse-preview", dependencies=[Depends(require_token)])
async def parse_preview(payload: ParsePreviewCreate):
    url = clean_url(payload.url)
    try:
        parsed = await ParserClient().parse(url)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Parse failed: {exc}") from exc
    if parsed.get("type") not in {"video", "image"}:
        raise HTTPException(status_code=400, detail=f"Unsupported link type: {parsed.get('type')}")
    cache = db.create_parse_cache(url, parsed)
    return {
        "url": url,
        "parse_cache_id": cache["id"],
        "parse_cache_expires_at": cache["expires_at"],
        "platform": parsed.get("platform"),
        "video_id": str(parsed.get("video_id") or ""),
        "title": str(parsed.get("desc") or ""),
        "author_name": author_name_from_payload(parsed),
        "cover_url": first_cover_url(parsed),
        "qualities": quality_options_from_payload(parsed)
        if parsed.get("type") == "video"
        else [{"value": "best", "label": "全部图片", "resolution": "", "fps": 0, "codec": "image", "bit_rate": 0, "data_size": 0}],
    }


@app.get("/api/image-proxy", dependencies=[Depends(require_token)])
async def image_proxy(url: str = Query(min_length=8, max_length=3000)):
    clean = str(url or "").strip()
    if clean.startswith("//"):
        clean = f"https:{clean}"
    parsed = urlsplit(clean)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Invalid image URL")
    if is_private_proxy_host(parsed.hostname or ""):
        raise HTTPException(status_code=400, detail="Unsupported image host")
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            response = await client.get(clean, headers=image_proxy_headers(clean))
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Image request failed: HTTP {exc.response.status_code}") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Image request failed: {exc}") from exc
    final_host = response.url.host or ""
    if is_private_proxy_host(final_host):
        raise HTTPException(status_code=400, detail="Unsupported image host")
    content_type = response.headers.get("content-type", "image/jpeg").split(";", 1)[0].strip().lower()
    if content_type and not content_type.startswith("image/"):
        raise HTTPException(status_code=502, detail="Remote URL did not return an image")
    if len(response.content) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image is too large")
    return Response(
        content=response.content,
        media_type=content_type or "image/jpeg",
        headers={"Cache-Control": "private, max-age=600"},
    )


@app.post("/api/jobs", dependencies=[Depends(require_token)])
async def create_job(payload: JobCreate):
    try:
        url = clean_url(payload.url)
        cached_metadata = None
        cached = db.get_parse_cache(payload.parse_cache_id)
        if cached and cached.get("url") == url and isinstance(cached.get("payload"), dict):
            cached_metadata = cached["payload"]
        return db.create_job(url, quality_preference=payload.quality_preference, metadata=cached_metadata)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/jobs/batch", dependencies=[Depends(require_token)])
async def create_jobs(payload: JobBatchCreate):
    urls = collect_urls(payload)
    if not urls:
        raise HTTPException(status_code=400, detail="No valid video links found")
    if len(urls) > 100:
        raise HTTPException(status_code=400, detail="Batch limit is 100 links")
    try:
        created = [db.create_job(url, quality_preference=payload.quality_preference) for url in urls]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"count": len(created), "jobs": created}


@app.post("/api/push", dependencies=[Depends(require_token)])
async def push_jobs(payload: PushCreate):
    urls = collect_urls(push_payload_to_batch(payload))
    if not urls:
        raise HTTPException(status_code=400, detail="No valid video links found")
    if len(urls) > 100:
        raise HTTPException(status_code=400, detail="Batch limit is 100 links")
    if payload.dry_run:
        return {**push_summary(urls=urls, dry_run=True), "urls": urls}
    try:
        created = create_push_jobs(urls, quality_preference=payload.quality_preference)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    cover_attached = False
    if len(urls) == 1 and created:
        cover_attached = await attach_pushed_cover(created[0], payload.cover_url)
    return {**push_summary(urls=urls, jobs=created, cover_attached=cover_attached), "jobs": created}


@app.get("/api/push", response_class=HTMLResponse, dependencies=[Depends(require_token)])
async def push_job_from_query(
    url: str | None = Query(default=None),
    text: str | None = Query(default=None),
    quality_preference: str | None = Query(default=None, max_length=20),
    cover_url: str | None = Query(default=None, max_length=3000),
    dry_run: bool = Query(default=False),
):
    payload = PushCreate(url=url, text=text, quality_preference=quality_preference, cover_url=cover_url, dry_run=dry_run)
    urls = collect_urls(push_payload_to_batch(payload))
    if not urls:
        raise HTTPException(status_code=400, detail="No valid video links found")
    if len(urls) > 100:
        raise HTTPException(status_code=400, detail="Batch limit is 100 links")
    created: list[dict] = []
    if not dry_run:
        try:
            created = create_push_jobs(urls, quality_preference=quality_preference)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    cover_attached = False
    if not dry_run and len(urls) == 1 and created:
        cover_attached = await attach_pushed_cover(created[0], cover_url)
    summary = push_summary(urls=urls, jobs=created, dry_run=dry_run, cover_attached=cover_attached)
    title = "ClipNest 推送预检完成" if dry_run else "ClipNest 推送完成"
    body = "".join(f"<li>{html.escape(item)}</li>" for item in urls[:20])
    extra = (
        "<p>dry-run 模式没有创建任务。</p>"
        if dry_run
        else f"<p>新建 {summary['created_count']} 个，已存在 {summary['reused_count']} 个。</p>"
    )
    return HTMLResponse(
        f"""
        <!doctype html>
        <html lang="zh-CN">
          <head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title></head>
          <body style="font-family: system-ui, sans-serif; padding: 24px; line-height: 1.5;">
            <h1>{title}</h1>
            <p>{html.escape(summary["message"])}</p>
            {extra}
            <ul>{body}</ul>
          </body>
        </html>
        """
    )


@app.post("/api/author-crawls", dependencies=[Depends(require_token)])
async def create_author_crawl(payload: AuthorCrawlCreate):
    try:
        quality = db.normalize_quality_preference(payload.quality_preference)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    source = db.get_author_sync_source(payload.sync_source_id) if payload.sync_source_id else None
    url = clean_url(payload.url)
    author_name = payload.author_name
    sec_uid = payload.sec_uid
    sync_source_id = payload.sync_source_id
    if source:
        url = str(source.get("url") or url)
        author_name = author_name or str(source.get("author_name") or "")
        sec_uid = sec_uid or str(source.get("sec_uid") or "")
        sync_source_id = int(source["id"])
    job = db.create_author_crawl_job(
        url,
        max_items=payload.max_items,
        max_pages=payload.max_pages,
        delay_ms=payload.delay_ms,
        quality_preference=quality,
        author_name=author_name,
        sec_uid=sec_uid,
        sync_mode=payload.sync_mode,
        sync_source_id=sync_source_id,
    )
    return {"message": "作者抓取任务已创建", "job": job, "source": source}


@app.get("/api/author-crawls", dependencies=[Depends(require_token)])
async def list_author_crawls(limit: int = Query(default=20, ge=1, le=100)):
    return db.list_author_crawl_jobs(limit=limit)


@app.post("/api/author-crawls/cleanup", dependencies=[Depends(require_token)])
async def cleanup_author_crawls(
    status: str = Query(default="finished,failed,cancelled", max_length=120),
    limit: int = Query(default=500, ge=1, le=2000),
):
    statuses = [item.strip() for item in status.split(",")]
    return db.cleanup_author_crawl_jobs(statuses=statuses, limit=limit)


async def resolve_author_sync_source_payload(payload: AuthorSyncSourceCreate | AuthorSyncSourceUpdate) -> dict:
    values = payload.model_dump(exclude_unset=True)
    url = clean_url(str(values.get("url") or ""))
    sec_uid = str(values.get("sec_uid") or "").strip()
    platform_value = str(values.get("platform") or "").strip().lower()
    platform = platform_value or ("bilibili" if NativeBilibiliParserAdapter.is_author_url(url) else "douyin")
    if platform not in {"douyin", "bilibili"}:
        raise HTTPException(status_code=400, detail="当前作者同步支持抖音和哔哩哔哩")
    if url and not sec_uid:
        if platform == "bilibili":
            sec_uid = NativeBilibiliParserAdapter.extract_mid(url)
        else:
            direct = NativeDouyinParserAdapter.extract_sec_uid(url)
            if direct and direct.lower() != "self":
                sec_uid = direct
            else:
                parser_settings = db.get_parser_settings(include_secret=True)
                crawler = NativeDouyinParserAdapter(parser_settings=parser_settings)
                try:
                    sec_uid = await crawler.resolve_sec_uid(url)
                except Exception as exc:
                    raise HTTPException(status_code=502, detail=f"解析作者主页失败：{exc}") from exc
    if sec_uid and not url:
        url = (
            f"https://space.bilibili.com/{sec_uid}/upload/video"
            if platform == "bilibili"
            else f"https://www.douyin.com/user/{sec_uid}"
        )
    if not url and not sec_uid:
        raise HTTPException(status_code=400, detail="请填写作者主页链接或主页 ID")
    if platform == "bilibili" and not sec_uid:
        raise HTTPException(status_code=400, detail="请填写哔哩哔哩 UP 主空间链接，例如 https://space.bilibili.com/116683/upload/video")
    values["platform"] = platform
    values["url"] = NativeBilibiliParserAdapter.canonical_author_url(sec_uid) if platform == "bilibili" else url
    values["sec_uid"] = sec_uid
    return values


@app.get("/api/author-sync-sources", dependencies=[Depends(require_token)])
async def list_author_sync_sources(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=100),
    q: str | None = Query(default=None, max_length=120),
    platform: str | None = Query(default=None, max_length=40),
    enabled: bool | None = Query(default=None),
):
    return db.list_author_sync_sources(
        page=page,
        page_size=page_size,
        q=q.strip() if q else None,
        platform=platform.strip().lower() if platform else None,
        enabled=enabled,
    )


@app.get("/api/author-sync-sources/{source_id}", dependencies=[Depends(require_token)])
async def author_sync_source_detail(
    source_id: int,
    history_limit: int = Query(default=30, ge=1, le=100),
):
    try:
        return db.author_sync_source_detail(source_id, history_limit=history_limit)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Author sync source not found") from exc


@app.post("/api/author-sync-sources", dependencies=[Depends(require_token)])
async def create_author_sync_source(payload: AuthorSyncSourceCreate):
    values = await resolve_author_sync_source_payload(payload)
    try:
        source = db.upsert_author_sync_source(values)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": "作者同步源已保存", "source": source}


@app.patch("/api/author-sync-sources/{source_id}", dependencies=[Depends(require_token)])
async def update_author_sync_source(source_id: int, payload: AuthorSyncSourceUpdate):
    values = await resolve_author_sync_source_payload(payload) if payload.url or payload.sec_uid else payload.model_dump(exclude_unset=True)
    try:
        source = db.update_author_sync_source(source_id, values)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Author sync source not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": "作者同步源已更新", "source": source}


@app.delete("/api/author-sync-sources/{source_id}", dependencies=[Depends(require_token)])
async def delete_author_sync_source(source_id: int):
    if not db.delete_author_sync_source(source_id):
        raise HTTPException(status_code=404, detail="Author sync source not found")
    return {"deleted": True}


@app.post("/api/author-sync-sources/bulk", dependencies=[Depends(require_token)])
async def bulk_author_sync_sources(payload: AuthorSyncBatchUpdate):
    if not payload.source_ids:
        raise HTTPException(status_code=400, detail="No author sync sources selected")
    updated: list[int] = []
    deleted: list[int] = []
    skipped: list[dict] = []
    for source_id in payload.source_ids:
        source = db.get_author_sync_source(source_id)
        if not source:
            skipped.append({"id": source_id, "reason": "not_found"})
            continue
        if payload.delete:
            if db.delete_author_sync_source(source_id):
                deleted.append(source_id)
            continue
        patch: dict = {}
        if payload.enabled is not None:
            patch["enabled"] = payload.enabled
        if payload.sync_mode is not None:
            patch["sync_mode"] = payload.sync_mode
        if payload.max_items is not None:
            patch["max_items"] = payload.max_items
            patch["max_pages"] = max(30, min(100, math.ceil(payload.max_items / 18) + 5))
        if payload.max_pages is not None:
            patch["max_pages"] = payload.max_pages
        if payload.include_images is not None:
            patch["include_images"] = payload.include_images
        if payload.stop_after_existing_pages is not None:
            patch["stop_after_existing_pages"] = payload.stop_after_existing_pages
        if payload.stop_after_existing_items is not None:
            patch["stop_after_existing_items"] = payload.stop_after_existing_items
        if not patch:
            skipped.append({"id": source_id, "reason": "no_change"})
            continue
        db.update_author_sync_source(source_id, patch)
        updated.append(source_id)
    return {"updated": updated, "deleted": deleted, "skipped": skipped}


@app.post("/api/author-sync-sources/import-library", dependencies=[Depends(require_token)])
async def import_author_sync_sources_from_library(
    platform: str | None = Query(default="douyin", max_length=40),
    limit: int = Query(default=2000, ge=1, le=2000),
):
    return db.import_author_sync_sources_from_library(platform=platform.strip().lower() if platform else "douyin", limit=limit)


def author_sync_source_to_crawl(source: dict, sync_mode: str | None = None) -> dict:
    mode = db.normalize_author_crawl_mode(sync_mode or source.get("sync_mode") or "incremental")
    existing = db.active_author_crawl_for_source(int(source["id"]))
    if existing:
        existing["reused"] = True
        return existing
    platform = str(source.get("platform") or "").strip().lower()
    fallback_url = (
        f"https://space.bilibili.com/{source.get('sec_uid') or ''}/upload/video"
        if platform == "bilibili"
        else f"https://www.douyin.com/user/{source.get('sec_uid') or ''}"
    )
    job = db.create_author_crawl_job(
        str(source.get("url") or fallback_url),
        max_items=int(source.get("max_items") or 200),
        max_pages=int(source.get("max_pages") or 80),
        delay_ms=int(source.get("delay_ms") or 600),
        quality_preference=source.get("quality_preference"),
        author_name=str(source.get("author_name") or ""),
        sec_uid=str(source.get("sec_uid") or ""),
        sync_mode=mode,
        sync_source_id=int(source["id"]),
    )
    job["reused"] = False
    return job


@app.post("/api/author-sync-sources/{source_id}/crawl", dependencies=[Depends(require_token)])
async def crawl_author_sync_source(source_id: int, sync_mode: str | None = Query(default=None, max_length=20)):
    source = db.get_author_sync_source(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Author sync source not found")
    if not source.get("enabled"):
        raise HTTPException(status_code=409, detail="该作者同步源已停用")
    job = author_sync_source_to_crawl(source, sync_mode=sync_mode)
    return {"message": "同步任务已创建", "job": job, "source": source}


@app.post("/api/author-sync-sources/crawl", dependencies=[Depends(require_token)])
async def crawl_author_sync_sources(payload: AuthorSyncBatchCrawl):
    if payload.source_ids:
        sources = []
        for source_id in payload.source_ids:
            source = db.get_author_sync_source(source_id)
            if source:
                sources.append(source)
    else:
        sources = []
        page_no = 1
        while True:
            page = db.list_author_sync_sources(
                page=page_no,
                page_size=100,
                platform=None,
                enabled=True if payload.enabled_only else None,
            )
            sources.extend(page.get("items") or [])
            if page_no >= int(page.get("total_pages") or 1):
                break
            page_no += 1
    created: list[dict] = []
    reused_count = 0
    skipped: list[dict] = []
    for source in sources:
        if payload.enabled_only and not source.get("enabled"):
            skipped.append({"id": source.get("id"), "reason": "disabled"})
            continue
        if not str(source.get("sec_uid") or "").strip() and not str(source.get("url") or "").strip():
            skipped.append({"id": source.get("id"), "reason": "missing_identity"})
            continue
        job = author_sync_source_to_crawl(source, sync_mode=payload.sync_mode)
        if job.get("reused"):
            reused_count += 1
        created.append(job)
    new_count = len(created) - reused_count
    skipped_count = len(skipped)
    message = f"已创建 {new_count} 个同步任务，复用 {reused_count} 个进行中任务"
    if skipped_count:
        message += f"，跳过 {skipped_count} 个不可同步作者"
    return {"message": message, "jobs": created, "skipped": skipped}


@app.post("/api/author-crawls/{crawl_id}/pause", dependencies=[Depends(require_token)])
async def pause_author_crawl(crawl_id: int):
    found = db.get_author_crawl_job(crawl_id)
    if not found:
        raise HTTPException(status_code=404, detail="Author crawl job not found")
    status = str(found.get("status") or "")
    if status == "queued":
        db.update_author_crawl_job(crawl_id, status="paused", message="已暂停")
    elif status == "running":
        db.update_author_crawl_job(crawl_id, status="pausing", message="正在暂停")
    elif status != "paused":
        raise HTTPException(status_code=409, detail=f"Cannot pause from status: {status}")
    return db.get_author_crawl_job(crawl_id) or {}


@app.post("/api/author-crawls/{crawl_id}/resume", dependencies=[Depends(require_token)])
async def resume_author_crawl(crawl_id: int):
    found = db.get_author_crawl_job(crawl_id)
    if not found:
        raise HTTPException(status_code=404, detail="Author crawl job not found")
    status = str(found.get("status") or "")
    if status not in {"paused", "failed"}:
        raise HTTPException(status_code=409, detail=f"Cannot resume from status: {status}")
    db.update_author_crawl_job(
        crawl_id,
        status="queued",
        message="排队中",
        error="",
        progress=min(float(found.get("progress") or 0), 99),
        finished_at=None,
    )
    return db.get_author_crawl_job(crawl_id) or {}


@app.post("/api/author-crawls/{crawl_id}/continue", dependencies=[Depends(require_token)])
async def continue_author_crawl(crawl_id: int):
    found = db.get_author_crawl_job(crawl_id)
    if not found:
        raise HTTPException(status_code=404, detail="Author crawl job not found")
    status = str(found.get("status") or "")
    cursor = int(found.get("cursor") or 0)
    if status != "finished" or cursor <= 0:
        raise HTTPException(status_code=409, detail=f"Cannot continue from status: {status}")
    message = str(found.get("message") or "")
    if "更多" not in message:
        raise HTTPException(status_code=409, detail="This author crawl has no more saved pages")
    job = db.create_author_crawl_job(
        str(found.get("url") or ""),
        max_items=int(found.get("max_items") or 200),
        max_pages=int(found.get("max_pages") or 80),
        delay_ms=int(found.get("delay_ms") or 600),
        quality_preference=found.get("quality_preference"),
        author_name=str(found.get("author_name") or ""),
        sec_uid=str(found.get("sec_uid") or ""),
        cursor=cursor,
        sync_mode=str(found.get("sync_mode") or "full"),
    )
    return {"message": "续抓任务已创建", "job": job, "source_id": crawl_id}


@app.post("/api/author-crawls/{crawl_id}/cancel", dependencies=[Depends(require_token)])
async def cancel_author_crawl(crawl_id: int):
    found = db.get_author_crawl_job(crawl_id)
    if not found:
        raise HTTPException(status_code=404, detail="Author crawl job not found")
    status = str(found.get("status") or "")
    if status in {"queued", "paused", "failed"}:
        db.update_author_crawl_job(
            crawl_id,
            status="cancelled",
            progress=100,
            message="已取消",
            finished_at=db.utc_now(),
        )
    elif status in {"running", "pausing"}:
        db.update_author_crawl_job(crawl_id, status="cancelling", message="正在取消")
    elif status not in {"cancelled", "finished"}:
        raise HTTPException(status_code=409, detail=f"Cannot cancel from status: {status}")
    return db.get_author_crawl_job(crawl_id) or {}


@app.post("/api/authors/crawl", dependencies=[Depends(require_token)])
async def crawl_author_posts(payload: AuthorCrawlCreate):
    author_url = clean_url(payload.url)
    try:
        quality = db.normalize_quality_preference(payload.quality_preference)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    parser_settings = db.get_parser_settings(include_secret=True)
    crawler = NativeDouyinParserAdapter(parser_settings=parser_settings)
    try:
        crawl = await crawler.list_author_posts(
            author_url,
            max_pages=payload.max_pages,
            max_items=payload.max_items,
            delay_ms=payload.delay_ms,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Author crawl failed: {exc}") from exc

    created: list[dict] = []
    reused: list[dict] = []
    preview: list[dict] = []
    deleted_skipped: list[dict] = []
    for item in crawl["items"]:
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        platform = str(metadata.get("platform") or "douyin")
        video_id = str(metadata.get("video_id") or item.get("aweme_id") or "")
        item_url = str(item.get("url") or "")
        if db.is_deleted_media(platform=platform, video_id=video_id, url=item_url):
            deleted_skipped.append(
                {
                    "url": item.get("url"),
                    "video_id": video_id,
                    "title": item.get("desc"),
                    "author_name": item.get("author_name"),
                }
            )
            continue
        existing = db.find_existing_video_job(platform, video_id, quality_preference=quality)
        if existing:
            reused.append(
                {
                    "id": existing.get("id"),
                    "status": existing.get("status"),
                    "url": item.get("url"),
                    "video_id": video_id,
                    "title": item.get("desc") or existing.get("title"),
                }
            )
            continue
        if payload.dry_run:
            preview.append(
                {
                    "url": item.get("url"),
                    "video_id": video_id,
                    "title": item.get("desc"),
                    "type": item.get("type"),
                    "author_name": item.get("author_name"),
                }
            )
            continue
        created.append(db.create_job(item_url, quality_preference=quality, metadata=metadata))

    created_count = len(created)
    reused_count = len(reused)
    would_create_count = len(preview)
    deleted_skipped_count = len(deleted_skipped)
    if payload.dry_run:
        message = (
            f"预检完成：发现 {crawl['count']} 个作品，"
            f"{would_create_count} 个可加入，{reused_count} 个已存在，{deleted_skipped_count} 个已删除跳过"
        )
    else:
        message = (
            f"作者作品已加入队列：新增 {created_count} 个，"
            f"已存在 {reused_count} 个，已删除跳过 {deleted_skipped_count} 个"
        )
    if crawl.get("limit_reached"):
        message += "，还有更多作品未抓完"
    return {
        "message": message,
        "dry_run": payload.dry_run,
        "sec_uid": crawl.get("sec_uid"),
        "found_count": crawl.get("count", 0),
        "created_count": created_count,
        "reused_count": reused_count,
        "would_create_count": would_create_count,
        "deleted_skipped_count": deleted_skipped_count,
        "pages": crawl.get("pages", 0),
        "has_more": crawl.get("has_more", False),
        "limit_reached": crawl.get("limit_reached", False),
        "next_cursor": crawl.get("next_cursor", 0),
        "quality_preference": quality,
        "created": created[:50],
        "reused": reused[:50],
        "preview": preview[:50],
        "deleted_skipped": deleted_skipped[:50],
    }


@app.get("/api/jobs", dependencies=[Depends(require_token)])
async def jobs(
    limit: int = Query(default=100, ge=1, le=500),
    status: str | None = Query(default=None),
    author: str | None = Query(default=None),
    platform: str | None = Query(default=None, max_length=40),
    q: str | None = Query(default=None, max_length=120),
    page: int | None = Query(default=None, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
):
    if page is not None:
        return runtime_state.overlay_jobs_page(
            db.list_jobs_page(
                page=page,
                page_size=page_size,
                status=status.strip() if status else None,
                author=author.strip() if author else None,
                platform=platform.strip().lower() if platform else None,
                q=q.strip() if q else None,
            )
        )
    return runtime_state.overlay_jobs(
        db.list_jobs(
            limit=limit,
            status=status.strip() if status else None,
            author=author.strip() if author else None,
            platform=platform.strip().lower() if platform else None,
            q=q.strip() if q else None,
        )
    )


@app.post("/api/jobs/bulk/cancel", dependencies=[Depends(require_token)])
async def bulk_cancel_jobs(payload: JobBulkAction):
    updated: list[int] = []
    skipped: list[dict] = []
    for job_id in dict.fromkeys(payload.job_ids):
        found = db.get_job(job_id)
        if not found:
            skipped.append({"id": job_id, "reason": "not_found"})
            continue
        status = str(found.get("status") or "")
        if status not in CANCELABLE_STATUSES:
            skipped.append({"id": job_id, "reason": f"status:{status}"})
            continue
        if status in {"queued", "retry"}:
            db.update_job(
                job_id,
                status="cancelled",
                progress=100,
                message="Cancelled",
                error="",
                error_type="",
                next_attempt_at=None,
                finished_at=db.utc_now(),
            )
            db.add_event(job_id, "cancel", "Cancelled before start")
        else:
            db.update_job(job_id, status="cancelling", message="Cancelling")
            db.add_event(job_id, "cancel", "Cancellation requested")
        updated.append(job_id)
    return {"updated": updated, "skipped": skipped}


@app.post("/api/jobs/bulk/retry", dependencies=[Depends(require_token)])
async def bulk_retry_jobs(payload: JobBulkAction):
    updated: list[int] = []
    skipped: list[dict] = []
    files_removed: list[str] = []
    for job_id in dict.fromkeys(payload.job_ids):
        found = db.get_job(job_id)
        if not found:
            skipped.append({"id": job_id, "reason": "not_found"})
            continue
        if found.get("status") in RUNNING_STATUSES:
            skipped.append({"id": job_id, "reason": f"status:{found.get('status')}"})
            continue
        removed = remove_job_files(found) if payload.force else []
        files_removed.extend(removed)
        db.update_job(
            job_id,
            status="retry",
            progress=0,
            message="Queued for redownload" if payload.force else "Queued for retry",
            error="",
            error_type="",
            file_path=None if payload.force else found.get("file_path"),
            preview_path=None if payload.force else found.get("preview_path"),
            size_bytes=None if payload.force else found.get("size_bytes"),
            expected_size_bytes=None if payload.force else found.get("expected_size_bytes"),
            duration_seconds=None if payload.force else found.get("duration_seconds"),
            resolution=None if payload.force else found.get("resolution"),
            codec=None if payload.force else found.get("codec"),
            download_key=None if payload.force else found.get("download_key"),
            download_label=None if payload.force else found.get("download_label"),
            download_host=None if payload.force else found.get("download_host"),
            attempt_count=0,
            next_attempt_at=None,
            started_at=None,
            finished_at=None,
        )
        db.add_event(
            job_id,
            "redownload" if payload.force else "retry",
            "Queued for redownload" if payload.force else "Queued for retry",
            {"files_removed": removed, "quality": found.get("quality_preference")},
        )
        updated.append(job_id)
    return {"updated": updated, "skipped": skipped, "files_removed": files_removed}


@app.post("/api/jobs/bulk/delete", dependencies=[Depends(require_token)])
async def bulk_delete_jobs(payload: JobBulkAction):
    deleted: list[int] = []
    skipped: list[dict] = []
    files_removed: list[str] = []
    for job_id in dict.fromkeys(payload.job_ids):
        found = db.get_job(job_id)
        if not found:
            skipped.append({"id": job_id, "reason": "not_found"})
            continue
        if found.get("status") in RUNNING_STATUSES:
            skipped.append({"id": job_id, "reason": f"status:{found.get('status')}"})
            continue
        if payload.delete_file:
            files_removed.extend(remove_job_files(found))
            db.mark_deleted_media(found, reason="bulk")
        db.delete_job(job_id)
        deleted.append(job_id)
    return {"deleted": deleted, "skipped": skipped, "files_removed": files_removed}


@app.post("/api/jobs/cleanup", dependencies=[Depends(require_token)])
async def cleanup_jobs(
    status: str = Query(min_length=1, max_length=40),
    platform: str | None = Query(default=None, max_length=40),
    delete_file: bool = Query(default=False),
    limit: int = Query(default=500, ge=1, le=2000),
):
    clean_status = status.strip().lower()
    if clean_status not in {"failed", "cancelled"}:
        raise HTTPException(status_code=400, detail="Only failed/cancelled cleanup is supported")
    candidates = db.list_jobs(
        limit=limit,
        status=clean_status,
        platform=platform.strip().lower() if platform else None,
    )
    deleted: list[int] = []
    skipped: list[dict] = []
    files_removed: list[str] = []
    for found in candidates:
        job_id = int(found.get("id") or 0)
        if found.get("status") in RUNNING_STATUSES:
            skipped.append({"id": job_id, "reason": f"status:{found.get('status')}"})
            continue
        if delete_file:
            files_removed.extend(remove_job_files(found))
        db.delete_job(job_id)
        deleted.append(job_id)
    return {"deleted": deleted, "skipped": skipped, "files_removed": files_removed}


@app.get("/api/jobs/{job_id}", dependencies=[Depends(require_token)])
async def job(job_id: int):
    found = db.get_job(job_id)
    if not found:
        raise HTTPException(status_code=404, detail="Job not found")
    return runtime_state.overlay_job(found)


@app.get("/api/jobs/{job_id}/events", dependencies=[Depends(require_token)])
async def job_events(job_id: int):
    found = db.get_job(job_id)
    if not found:
        raise HTTPException(status_code=404, detail="Job not found")
    return db.list_events(job_id)


@app.post("/api/jobs/{job_id}/refresh-metadata", dependencies=[Depends(require_token)])
async def refresh_job_metadata(job_id: int):
    found = db.get_job(job_id)
    if not found:
        raise HTTPException(status_code=404, detail="Job not found")
    if found.get("status") in RUNNING_STATUSES:
        raise HTTPException(status_code=409, detail="Job is running")
    parser_settings = db.get_parser_settings(include_secret=True)
    parser = ParserClient(parser_settings=parser_settings)
    try:
        payload = await parser.parse(found["url"])
    except Exception as exc:
        db.add_event(
            job_id,
            "parse:refresh_failed",
            f"Refresh parse failed: {type(exc).__name__}",
            {"error": str(exc)[:500]},
        )
        raise HTTPException(status_code=502, detail=f"Parse failed: {exc}") from exc
    diagnostics = parse_diagnostics_from_payload(payload)
    asset_updates: dict[str, str] = {}
    try:
        asset_updates = await cache_job_assets(payload, parser_settings)
    except Exception as exc:
        db.add_event(job_id, "asset:cache_failed", f"Asset cache failed: {exc}", {"error": str(exc)[:240]})
    author = author_name_from_payload(payload)
    author_data = payload.get("author") if isinstance(payload.get("author"), dict) else {}
    updates = {
        "platform": payload.get("platform"),
        "video_id": str(payload.get("video_id") or ""),
        "author_name": author,
        "author_id": str(author_data.get("uid") or ""),
        "description": str(payload.get("desc") or ""),
        "title": str(payload.get("desc") or ""),
        "cover_url": first_cover_url(payload),
        "metadata": payload,
        **asset_updates,
    }
    db.update_job(job_id, **updates)
    cache = db.create_parse_cache(str(found.get("url") or ""), payload)
    db.add_event(
        job_id,
        "parse:refresh",
        f"Metadata refreshed via {parser.adapter.name}",
        {
            "adapter": parser.adapter.name,
            "source": diagnostics.get("parser_source"),
            "video_id": diagnostics.get("video_id"),
            "bit_rate_candidates": diagnostics.get("bit_rate_candidates"),
            "best_quality": diagnostics.get("best_quality"),
            "parse_cache_id": cache["id"],
        },
    )
    return {
        "job": db.get_job(job_id) or {},
        "diagnostics": diagnostics,
        "parse_cache_id": cache["id"],
        "parse_cache_expires_at": cache["expires_at"],
    }


@app.post("/api/jobs/{job_id}/retry", dependencies=[Depends(require_token)])
async def retry_job(job_id: int, payload: JobRetry | None = Body(default=None)):
    found = db.get_job(job_id)
    if not found:
        raise HTTPException(status_code=404, detail="Job not found")
    if found.get("status") in RUNNING_STATUSES:
        raise HTTPException(status_code=409, detail="Job is running")
    force = bool(payload.force) if payload else False
    quality_preference = None
    cached_metadata = None
    if payload and payload.quality_preference is not None:
        try:
            quality_preference = db.normalize_quality_preference(payload.quality_preference)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if payload and payload.parse_cache_id:
        cached = db.get_parse_cache(payload.parse_cache_id)
        if cached and cached.get("url") == found.get("url") and isinstance(cached.get("payload"), dict):
            cached_metadata = cached["payload"]
    removed = remove_job_files(found) if force else []
    updates = {
        "status": "retry",
        "progress": 0,
        "message": "Queued for redownload" if force else "Queued for retry",
        "error": "",
        "error_type": "",
        "file_path": None if force else found.get("file_path"),
        "preview_path": None if force else found.get("preview_path"),
        "size_bytes": None if force else found.get("size_bytes"),
        "expected_size_bytes": None if force else found.get("expected_size_bytes"),
        "duration_seconds": None if force else found.get("duration_seconds"),
        "resolution": None if force else found.get("resolution"),
        "codec": None if force else found.get("codec"),
        "download_key": None if force else found.get("download_key"),
        "download_label": None if force else found.get("download_label"),
        "download_host": None if force else found.get("download_host"),
        "attempt_count": 0,
        "next_attempt_at": None,
        "started_at": None,
        "finished_at": None,
    }
    if quality_preference is not None:
        updates["quality_preference"] = quality_preference
    if cached_metadata is not None:
        updates["metadata"] = cached_metadata
    db.update_job(job_id, **updates)
    db.add_event(
        job_id,
        "redownload" if force else "retry",
        "Queued for redownload" if force else "Queued for retry",
        {
            "files_removed": removed,
            "quality": quality_preference or found.get("quality_preference"),
            "cached_parse": cached_metadata is not None,
        },
    )
    queued = db.get_job(job_id) or {}
    queued["files_removed"] = removed
    return queued


@app.post("/api/jobs/{job_id}/cancel", dependencies=[Depends(require_token)])
async def cancel_job(job_id: int):
    found = db.get_job(job_id)
    if not found:
        raise HTTPException(status_code=404, detail="Job not found")
    status = str(found.get("status") or "")
    if status not in CANCELABLE_STATUSES:
        raise HTTPException(status_code=409, detail=f"Job cannot be cancelled from status: {status}")
    if status in {"queued", "retry"}:
        db.update_job(
            job_id,
            status="cancelled",
            progress=100,
            message="Cancelled",
            error="",
            error_type="",
            next_attempt_at=None,
            finished_at=db.utc_now(),
        )
        db.add_event(job_id, "cancel", "Cancelled before start")
    else:
        db.update_job(job_id, status="cancelling", message="Cancelling")
        db.add_event(job_id, "cancel", "Cancellation requested")
    return runtime_state.overlay_job(db.get_job(job_id)) or {}


@app.delete("/api/jobs/{job_id}", dependencies=[Depends(require_token)])
async def delete_job(job_id: int, delete_file: bool = Query(default=False)):
    found = db.get_job(job_id)
    if not found:
        raise HTTPException(status_code=404, detail="Job not found")
    if found.get("status") in RUNNING_STATUSES:
        raise HTTPException(status_code=409, detail="Job is running")
    removed = remove_job_files(found) if delete_file else []
    if delete_file:
        db.mark_deleted_media(found, reason="single")
    db.delete_job(job_id)
    return {"deleted": True, "files_removed": removed}


@app.get("/api/stats", dependencies=[Depends(require_token)])
async def stats():
    return db.get_stats()


@app.get("/api/library/authors", dependencies=[Depends(require_token)])
async def library_authors(
    limit: int = Query(default=100, ge=1, le=500),
    page: int | None = Query(default=None, ge=1),
    page_size: int = Query(default=24, ge=1, le=100),
    q: str | None = Query(default=None, max_length=120),
    platform: str | None = Query(default=None, max_length=40),
):
    clean_platform = platform.strip().lower() if platform else None
    if page is not None:
        return db.list_authors_page(page=page, page_size=page_size, q=q.strip() if q else None, platform=clean_platform)
    return db.list_authors(limit, platform=clean_platform)


@app.get("/api/library/authors/{author}", dependencies=[Depends(require_token)])
async def library_author_detail(author: str, platform: str | None = Query(default=None, max_length=40)):
    return db.author_detail(author, platform=platform.strip().lower() if platform else None)


@app.delete("/api/library/authors/{author}", dependencies=[Depends(require_token)])
async def delete_library_author(
    author: str,
    delete_file: bool = Query(default=True),
    platform: str | None = Query(default=None, max_length=40),
):
    return delete_library_author_jobs(author, delete_file=delete_file, platform=platform.strip().lower() if platform else None)


@app.delete("/api/library/author", dependencies=[Depends(require_token)])
async def delete_library_author_by_query(
    author: str = Query(min_length=1, max_length=160),
    delete_file: bool = Query(default=True),
    platform: str | None = Query(default=None, max_length=40),
):
    return delete_library_author_jobs(author, delete_file=delete_file, platform=platform.strip().lower() if platform else None)


def delete_library_author_jobs(author: str, delete_file: bool = True, platform: str | None = None):
    jobs = db.list_author_jobs(author, platform=platform)
    if not jobs:
        raise HTTPException(status_code=404, detail="Author not found")
    deleted: list[int] = []
    skipped: list[dict] = []
    files_removed: list[str] = []
    for found in jobs:
        job_id = int(found.get("id") or 0)
        if found.get("status") in RUNNING_STATUSES:
            skipped.append({"id": job_id, "reason": f"status:{found.get('status')}"})
            continue
        if delete_file:
            files_removed.extend(remove_job_files(found))
        db.mark_deleted_media(found, reason="author")
        db.delete_job(job_id)
        deleted.append(job_id)
    return {
        "deleted": deleted,
        "deleted_count": len(deleted),
        "skipped": skipped,
        "files_removed": files_removed,
    }


@app.get("/api/library/jobs", dependencies=[Depends(require_token)])
async def library_jobs(
    author: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    page: int | None = Query(default=None, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    type: str | None = Query(default=None),
    sort: str | None = Query(default="publish_desc"),
    q: str | None = Query(default=None, max_length=120),
    platform: str | None = Query(default=None, max_length=40),
    status: str | None = Query(default="finished", max_length=40),
    date_field: str | None = Query(default="download", max_length=20),
    date_from: str | None = Query(default=None, max_length=30),
    date_to: str | None = Query(default=None, max_length=30),
):
    clean_platform = platform.strip().lower() if platform else None
    if page is not None:
        return db.list_library_jobs_page(
            page=page,
            page_size=page_size,
            author=author.strip() if author else None,
            media_type=type.strip() if type else None,
            sort=sort.strip() if sort else "publish_desc",
            q=q.strip() if q else None,
            platform=clean_platform,
            status=status.strip() if status else "finished",
            date_field=date_field.strip() if date_field else "download",
            date_from=date_from.strip() if date_from else None,
            date_to=date_to.strip() if date_to else None,
        )
    return db.list_jobs(limit=limit, author=author.strip() if author else None, platform=clean_platform)


@app.get("/api/library/deleted", dependencies=[Depends(require_token)])
async def deleted_library_media(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    q: str | None = Query(default=None, max_length=120),
    platform: str | None = Query(default=None, max_length=40),
    author: str | None = Query(default=None, max_length=160),
    date_from: str | None = Query(default=None, max_length=30),
    date_to: str | None = Query(default=None, max_length=30),
):
    return db.list_deleted_media(
        page=page,
        page_size=page_size,
        q=q.strip() if q else None,
        platform=platform.strip().lower() if platform else None,
        author=author.strip() if author else None,
        date_from=date_from.strip() if date_from else None,
        date_to=date_to.strip() if date_to else None,
    )


@app.delete("/api/library/deleted/{record_id}", dependencies=[Depends(require_token)])
async def delete_deleted_library_media(record_id: int):
    if not db.delete_deleted_media_record(record_id):
        raise HTTPException(status_code=404, detail="Deleted media record not found")
    return {"deleted": True}


@app.delete("/api/library/deleted", dependencies=[Depends(require_token)])
async def clear_deleted_library_media(
    platform: str | None = Query(default=None, max_length=40),
    author: str | None = Query(default=None, max_length=160),
    q: str | None = Query(default=None, max_length=120),
    date_from: str | None = Query(default=None, max_length=30),
    date_to: str | None = Query(default=None, max_length=30),
):
    deleted_count = db.clear_deleted_media_records(
        platform=platform.strip().lower() if platform else None,
        author_name=author.strip() if author else None,
        q=q.strip() if q else None,
        date_from=date_from.strip() if date_from else None,
        date_to=date_to.strip() if date_to else None,
    )
    return {"deleted_count": deleted_count}


@app.get("/api/cookie/health", dependencies=[Depends(require_token)])
async def cookie_health():
    parser_settings = db.get_parser_settings(include_secret=False)
    activity = db.cookie_activity()
    latest_success = activity.get("latest_parse_success")
    latest_failure = activity.get("latest_parse_failure")
    return {
        "cookie_configured": parser_settings.get("douyin_cookie_configured"),
        "cookie_source": parser_settings.get("douyin_cookie_source"),
        "latest_parse_success_at": latest_success.get("created_at") if latest_success else None,
        "latest_parse_failure_at": latest_failure.get("updated_at") if latest_failure else None,
        "latest_parse_failure": latest_failure,
        "status": "configured" if parser_settings.get("douyin_cookie_configured") else "missing",
    }


@app.get("/api/health", dependencies=[Depends(require_token)])
async def health():
    parser = ParserClient().info()
    app_settings = db.get_app_settings()
    with db.connect() as conn:
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
    return {
        "ok": True,
        "app": settings.app_name,
        "worker_enabled_in_web": settings.worker_enabled,
        "parser": parser,
        "settings": {
            "queue_paused": app_settings.get("queue_paused"),
            "max_concurrent_downloads": app_settings.get("max_concurrent_downloads"),
            "auto_retry_attempts": app_settings.get("auto_retry_attempts"),
            "auto_retry_delay_seconds": app_settings.get("auto_retry_delay_seconds"),
        },
        "database": {
            "path": db.DB_PATH,
            "journal_mode": journal_mode,
            "busy_timeout": busy_timeout,
        },
        "stats": db.get_stats(),
    }


@app.get("/api/maintenance/events", dependencies=[Depends(require_token)])
async def maintenance_events(limit: int = Query(default=100, ge=1, le=500)):
    return db.list_recent_events(limit)


@app.get("/api/logs/events", dependencies=[Depends(require_token)])
async def logs_events(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    q: str | None = Query(default=None, max_length=160),
    event_type: str | None = Query(default=None, max_length=80),
    platform: str | None = Query(default=None, max_length=40),
    status: str | None = Query(default=None, max_length=40),
    date_from: str | None = Query(default=None, max_length=40),
    date_to: str | None = Query(default=None, max_length=40),
):
    return db.list_events_page(
        page=page,
        page_size=page_size,
        q=q.strip() if q else None,
        event_type=event_type.strip() if event_type else None,
        platform=platform.strip().lower() if platform else None,
        status=status.strip().lower() if status else None,
        date_from=date_from.strip() if date_from else None,
        date_to=date_to.strip() if date_to else None,
    )


@app.get("/api/maintenance/config", dependencies=[Depends(require_token)])
async def maintenance_config():
    return {
        "app_settings": db.get_app_settings(),
        "parser_settings": db.get_parser_settings(include_secret=False),
        "health": await health(),
    }


@app.get("/api/maintenance/backup")
async def maintenance_backup(_: Annotated[None, Depends(require_token)]):
    db.checkpoint()
    filename = f"clipnest-{int(time.time())}.sqlite3"
    return FileResponse(db.DB_PATH, filename=filename)


@app.get("/api/maintenance/orphans", dependencies=[Depends(require_token)])
async def maintenance_orphans(delete: bool = Query(default=False)):
    return db.scan_orphan_files(delete=delete)


@app.get("/api/maintenance/duplicates", dependencies=[Depends(require_token)])
async def maintenance_duplicates(limit: int = Query(default=100, ge=1, le=500)):
    return db.scan_duplicate_media_jobs(limit=limit)


@app.post("/api/maintenance/duplicates/cleanup", dependencies=[Depends(require_token)])
async def maintenance_cleanup_duplicates(limit: int = Query(default=500, ge=1, le=500)):
    return db.cleanup_duplicate_media_jobs(limit=limit)


@app.post("/api/maintenance/cache-assets", dependencies=[Depends(require_token)])
async def maintenance_cache_assets(limit: int = Query(default=200, ge=1, le=500)):
    cached_covers = 0
    cached_avatars = 0
    failed: list[dict] = []
    headers = {"User-Agent": settings.douyin_user_agent}
    for job in db.list_jobs(limit=limit):
        metadata = job.get("metadata") if isinstance(job.get("metadata"), dict) else {}
        updates: dict[str, str] = {}
        cover_url = job.get("cover_url") or cover_url_from_payload(metadata)
        avatar_url = job.get("author_avatar_url") or author_avatar_url_from_payload(metadata)
        if cover_url and not job.get("cover_path"):
            try:
                updates["cover_path"] = await cache_remote_image(str(cover_url), "covers", headers=headers)
                cached_covers += 1
            except Exception as exc:
                failed.append({"job_id": job.get("id"), "asset": "cover", "error": str(exc)})
        if avatar_url and not job.get("author_avatar_path"):
            try:
                updates["author_avatar_path"] = await cache_remote_image(str(avatar_url), "avatars", headers=headers)
                updates["author_avatar_url"] = str(avatar_url)
                cached_avatars += 1
            except Exception as exc:
                failed.append({"job_id": job.get("id"), "asset": "avatar", "error": str(exc)})
        if updates:
            db.update_job(int(job["id"]), **updates)
    return {
        "cached_covers": cached_covers,
        "cached_avatars": cached_avatars,
        "failed": failed,
        "failed_count": len(failed),
    }


@app.get("/api/assets/{asset_path:path}")
async def cached_asset(asset_path: str, _: Annotated[None, Depends(require_token)]):
    resolved = (ASSET_ROOT / asset_path).resolve()
    root = ASSET_ROOT.resolve()
    if root not in resolved.parents and resolved != root:
        raise HTTPException(status_code=403, detail="Invalid asset path")
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(str(resolved), filename=resolved.name)


def safe_file_response(job_id: int, field: str):
    found = db.get_job(job_id)
    if not found:
        raise HTTPException(status_code=404, detail="Job not found")
    path = found.get(field)
    if not path:
        raise HTTPException(status_code=404, detail="File not available")
    resolved = resolve_media_path(path)
    if not resolved:
        raise HTTPException(status_code=404, detail="File not available")
    if not resolved.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(str(resolved), filename=resolved.name)


@app.get("/api/jobs/{job_id}/file")
async def job_file(job_id: int, _: Annotated[None, Depends(require_token)]):
    return safe_file_response(job_id, "file_path")


@app.get("/api/jobs/{job_id}/preview")
async def job_preview(job_id: int, _: Annotated[None, Depends(require_token)]):
    return safe_file_response(job_id, "preview_path")


@app.get("/api/jobs/{job_id}/media")
async def job_media(job_id: int, _: Annotated[None, Depends(require_token)]):
    found = db.get_job(job_id)
    if not found:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "file": relative_media_path(found.get("file_path")),
        "preview": relative_media_path(found.get("preview_path")),
    }
