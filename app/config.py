import os
from dataclasses import dataclass


DEFAULT_DOUYIN_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = "ClipNest"
    data_dir: str = os.getenv("CLIPNEST_DATA_DIR", "./data")
    download_dir: str = os.getenv("CLIPNEST_DOWNLOAD_DIR", "./downloads")
    api_token: str = os.getenv("CLIPNEST_API_TOKEN", "change-me")
    parser_adapter: str = os.getenv("CLIPNEST_PARSER_ADAPTER", "native_douyin")
    douyin_cookie: str = os.getenv("CLIPNEST_DOUYIN_COOKIE", "")
    douyin_user_agent: str = os.getenv("CLIPNEST_DOUYIN_USER_AGENT") or DEFAULT_DOUYIN_USER_AGENT
    worker_enabled: bool = env_bool("CLIPNEST_WORKER_ENABLED", True)
    public_base_url: str = os.getenv("CLIPNEST_PUBLIC_BASE_URL", "")
    poll_interval_seconds: float = float(os.getenv("CLIPNEST_POLL_INTERVAL_SECONDS", "2"))


settings = Settings()
