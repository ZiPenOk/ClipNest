import os
from dataclasses import dataclass


DEFAULT_DOUYIN_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)
DEFAULT_TIKTOK_USER_AGENT = DEFAULT_DOUYIN_USER_AGENT
DEFAULT_BILIBILI_USER_AGENT = DEFAULT_DOUYIN_USER_AGENT


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def normalize_cookie_header(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    cookies: list[str] = []
    seen: set[str] = set()
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("cookie:"):
            line = line.split(":", 1)[1].strip()
        parts = line.split("\t")
        if len(parts) >= 7:
            name = parts[-2].strip()
            cookie_value = parts[-1].strip()
            chunk = f"{name}={cookie_value}" if name else ""
            chunks = [chunk] if chunk else []
        else:
            chunks = [chunk.strip() for chunk in line.split(";") if "=" in chunk]
        for chunk in chunks:
            name = chunk.split("=", 1)[0].strip()
            if not name or name in seen:
                continue
            cookies.append(chunk)
            seen.add(name)
    return "; ".join(cookies)


@dataclass(frozen=True)
class Settings:
    app_name: str = "ClipNest"
    data_dir: str = os.getenv("CLIPNEST_DATA_DIR", "./data")
    download_dir: str = os.getenv("CLIPNEST_DOWNLOAD_DIR", "./downloads")
    api_token: str = os.getenv("CLIPNEST_API_TOKEN", "change-me")
    parser_adapter: str = os.getenv("CLIPNEST_PARSER_ADAPTER", "native_douyin")
    douyin_cookie: str = os.getenv("CLIPNEST_DOUYIN_COOKIE", "")
    douyin_user_agent: str = os.getenv("CLIPNEST_DOUYIN_USER_AGENT") or DEFAULT_DOUYIN_USER_AGENT
    tiktok_cookie: str = os.getenv("CLIPNEST_TIKTOK_COOKIE", "")
    tiktok_user_agent: str = os.getenv("CLIPNEST_TIKTOK_USER_AGENT") or DEFAULT_TIKTOK_USER_AGENT
    bilibili_cookie: str = os.getenv("CLIPNEST_BILIBILI_COOKIE", "")
    bilibili_user_agent: str = os.getenv("CLIPNEST_BILIBILI_USER_AGENT") or DEFAULT_BILIBILI_USER_AGENT
    ffmpeg_path: str = os.getenv("CLIPNEST_FFMPEG_PATH", "ffmpeg")
    worker_enabled: bool = env_bool("CLIPNEST_WORKER_ENABLED", True)
    public_base_url: str = os.getenv("CLIPNEST_PUBLIC_BASE_URL", "")
    poll_interval_seconds: float = float(os.getenv("CLIPNEST_POLL_INTERVAL_SECONDS", "2"))


settings = Settings()
