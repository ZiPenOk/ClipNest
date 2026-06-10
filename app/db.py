import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .assets import cover_url_from_payload, relative_asset_path
from .config import normalize_cookie_header, settings


DB_PATH = os.path.join(settings.data_dir, "clipnest.sqlite3")
DEFAULT_APP_SETTINGS: dict[str, Any] = {
    "skip_existing": True,
    "author_folders": True,
    "filename_template": "{author}\uff1a{desc}",
    "queue_paused": False,
    "max_concurrent_downloads": 1,
    "auto_retry_attempts": 1,
    "auto_retry_delay_seconds": 60,
    "telegram_enabled": False,
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "telegram_notify_success": True,
    "telegram_notify_failure": False,
}
DEFAULT_PARSER_SETTINGS: dict[str, Any] = {
    "parser_adapter": settings.parser_adapter,
    "douyin_cookie": settings.douyin_cookie,
    "douyin_user_agent": settings.douyin_user_agent,
    "tiktok_cookie": settings.tiktok_cookie,
    "tiktok_user_agent": settings.tiktok_user_agent,
    "bilibili_cookie": settings.bilibili_cookie,
    "bilibili_user_agent": settings.bilibili_user_agent,
    "douyin_signer_kind": "local_abogus",
}
PARSER_ADAPTERS = {"native_douyin", "native_douyin_share", "native_tiktok", "native_bilibili"}
PARSE_CACHE_TTL_SECONDS = 10 * 60
QUALITY_ALIASES = {
    "最高": "best",
    "最高清": "best",
    "highest": "best",
    "auto": "best",
    "4k": "2160",
    "2160p": "2160",
    "2k": "1440",
    "1440p": "1440",
    "1080p": "1080",
    "720p": "720",
}
JOB_LIST_ORDER_SQL = """
CASE
    WHEN status IN ('parsing', 'downloading', 'cancelling') THEN 0
    WHEN status IN ('queued', 'retry') THEN 1
    ELSE 2
END,
CASE
    WHEN status IN ('parsing', 'downloading', 'cancelling', 'queued', 'retry') THEN id
    ELSE -id
END ASC
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect():
    os.makedirs(settings.data_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db() -> None:
    with connect() as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                progress REAL NOT NULL DEFAULT 0,
                message TEXT NOT NULL DEFAULT '',
                platform TEXT,
                video_id TEXT,
                author_name TEXT,
                author_id TEXT,
                description TEXT,
                title TEXT,
                cover_url TEXT,
                file_path TEXT,
                preview_path TEXT,
                size_bytes INTEGER,
                duration_seconds REAL,
                resolution TEXT,
                codec TEXT,
                quality_preference TEXT,
                metadata_json TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS job_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                message TEXT NOT NULL DEFAULT '',
                data_json TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS parse_cache (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS author_crawl_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sync_source_id INTEGER,
                url TEXT NOT NULL,
                author_name TEXT NOT NULL DEFAULT '',
                sec_uid TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'queued',
                progress REAL NOT NULL DEFAULT 0,
                message TEXT NOT NULL DEFAULT '',
                quality_preference TEXT,
                sync_mode TEXT NOT NULL DEFAULT 'full',
                max_items INTEGER NOT NULL DEFAULT 200,
                max_pages INTEGER NOT NULL DEFAULT 80,
                delay_ms INTEGER NOT NULL DEFAULT 600,
                cursor INTEGER NOT NULL DEFAULT 0,
                pages_scanned INTEGER NOT NULL DEFAULT 0,
                found_count INTEGER NOT NULL DEFAULT 0,
                created_count INTEGER NOT NULL DEFAULT 0,
                reused_count INTEGER NOT NULL DEFAULT 0,
                error TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS author_sync_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL DEFAULT 'douyin',
                url TEXT NOT NULL DEFAULT '',
                author_name TEXT NOT NULL DEFAULT '',
                sec_uid TEXT NOT NULL DEFAULT '',
                avatar_url TEXT NOT NULL DEFAULT '',
                avatar_path TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 1,
                sync_mode TEXT NOT NULL DEFAULT 'incremental',
                max_items INTEGER NOT NULL DEFAULT 200,
                max_pages INTEGER NOT NULL DEFAULT 80,
                delay_ms INTEGER NOT NULL DEFAULT 600,
                quality_preference TEXT,
                include_images INTEGER NOT NULL DEFAULT 0,
                stop_after_existing_pages INTEGER NOT NULL DEFAULT 2,
                stop_after_existing_items INTEGER NOT NULL DEFAULT 36,
                last_cursor INTEGER NOT NULL DEFAULT 0,
                last_seen_video_id TEXT NOT NULL DEFAULT '',
                last_seen_publish_time INTEGER NOT NULL DEFAULT 0,
                last_sync_job_id INTEGER,
                last_sync_status TEXT NOT NULL DEFAULT '',
                last_sync_message TEXT NOT NULL DEFAULT '',
                last_sync_at TEXT,
                last_finished_at TEXT,
                last_found_count INTEGER NOT NULL DEFAULT 0,
                last_created_count INTEGER NOT NULL DEFAULT 0,
                last_reused_count INTEGER NOT NULL DEFAULT 0,
                last_deleted_skipped_count INTEGER NOT NULL DEFAULT 0,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS deleted_media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL DEFAULT '',
                video_id TEXT NOT NULL DEFAULT '',
                url TEXT NOT NULL DEFAULT '',
                author_name TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL DEFAULT '',
                source_job_id INTEGER,
                reason TEXT NOT NULL DEFAULT 'manual',
                deleted_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
        ensure_column(conn, "jobs", "quality_preference", "TEXT")
        ensure_column(conn, "jobs", "download_key", "TEXT")
        ensure_column(conn, "jobs", "download_label", "TEXT")
        ensure_column(conn, "jobs", "download_host", "TEXT")
        ensure_column(conn, "jobs", "expected_size_bytes", "INTEGER")
        ensure_column(conn, "jobs", "error_type", "TEXT")
        ensure_column(conn, "jobs", "attempt_count", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "jobs", "next_attempt_at", "TEXT")
        ensure_column(conn, "jobs", "cover_path", "TEXT")
        ensure_column(conn, "jobs", "author_avatar_url", "TEXT")
        ensure_column(conn, "jobs", "author_avatar_path", "TEXT")
        ensure_column(conn, "author_crawl_jobs", "sync_source_id", "INTEGER")
        ensure_column(conn, "author_crawl_jobs", "author_name", "TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "author_crawl_jobs", "sync_mode", "TEXT NOT NULL DEFAULT 'full'")
        ensure_column(conn, "author_crawl_jobs", "stop_reason", "TEXT NOT NULL DEFAULT ''")
        ensure_column(conn, "author_crawl_jobs", "has_more", "INTEGER NOT NULL DEFAULT 0")
        ensure_column(conn, "author_sync_sources", "include_images", "INTEGER NOT NULL DEFAULT 0")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_author ON jobs(author_name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_next_attempt ON jobs(status, next_attempt_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_job_events_job ON job_events(job_id, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_parse_cache_expires ON parse_cache(expires_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_author_crawl_status ON author_crawl_jobs(status, id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_author_crawl_source ON author_crawl_jobs(sync_source_id, id)")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_author_sync_source_identity ON author_sync_sources(platform, sec_uid) WHERE sec_uid != ''")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_author_sync_source_enabled ON author_sync_sources(enabled, platform, updated_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_author_sync_source_author ON author_sync_sources(author_name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_deleted_media_identity ON deleted_media(platform, video_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_deleted_media_url ON deleted_media(url)")


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    if data.get("metadata_json"):
        try:
            data["metadata"] = json.loads(data["metadata_json"])
        except json.JSONDecodeError:
            data["metadata"] = {}
    else:
        data["metadata"] = {}
    data.pop("metadata_json", None)
    data["quality_preference"] = normalize_quality_preference(data.get("quality_preference"))
    data["cover_path"] = relative_asset_path(data.get("cover_path"))
    data["author_avatar_path"] = relative_asset_path(data.get("author_avatar_path"))
    return data


def first_url(value: Any) -> str:
    if isinstance(value, list):
        for item in value:
            url = first_url(item)
            if url:
                return url
    if isinstance(value, str):
        return value.strip().split()[0] if value.strip() else ""
    return ""


def author_avatar_url(metadata: dict[str, Any] | None) -> str:
    if not isinstance(metadata, dict):
        return ""
    author = metadata.get("author")
    if not isinstance(author, dict):
        return ""
    for key in ("avatar_thumb", "avatar_medium", "avatar_larger", "avatar_300x300"):
        avatar = author.get(key)
        if isinstance(avatar, dict):
            url = first_url(avatar.get("url_list"))
            if url:
                return url
    return ""


def author_sec_uid(metadata: dict[str, Any] | None) -> str:
    if not isinstance(metadata, dict):
        return ""
    author = metadata.get("author")
    if isinstance(author, dict):
        return str(author.get("sec_uid") or author.get("sec_user_id") or "")
    return ""


def author_sec_uid_from_history(
    conn: sqlite3.Connection,
    author_name: str,
    preferred_metadata: dict[str, Any] | None = None,
    platform: str | None = None,
) -> str:
    sec_uid = author_sec_uid(preferred_metadata)
    if sec_uid:
        return sec_uid
    clauses = ["COALESCE(author_name, 'Unknown') = ?", "metadata_json IS NOT NULL"]
    params: list[Any] = [author_name]
    clean_platform = str(platform or "").strip().lower()
    if clean_platform:
        clauses.append("COALESCE(platform, '') = ?")
        params.append(clean_platform)
    rows = conn.execute(
        f"""
        SELECT metadata_json
        FROM jobs
        WHERE {' AND '.join(clauses)}
        ORDER BY id DESC
        LIMIT 30
        """,
        params,
    ).fetchall()
    for row in rows:
        try:
            metadata = json.loads(row["metadata_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        sec_uid = author_sec_uid(metadata)
        if sec_uid:
            return sec_uid
    return ""


def author_name_from_metadata(metadata: dict[str, Any] | None) -> str:
    if not isinstance(metadata, dict):
        return ""
    author = metadata.get("author")
    if isinstance(author, dict):
        for key in ("nickname", "unique_id", "short_id", "uid", "sec_uid"):
            value = str(author.get(key) or "").strip()
            if value:
                return value
    return ""


def metadata_job_fields(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}
    author = metadata.get("author")
    if not isinstance(author, dict):
        author = {}
    description = str(metadata.get("desc") or "").strip()
    return {
        "platform": str(metadata.get("platform") or "").strip() or None,
        "video_id": str(metadata.get("video_id") or "").strip() or None,
        "author_name": author_name_from_metadata(metadata) or None,
        "author_id": str(author.get("uid") or author.get("sec_uid") or "").strip() or None,
        "description": description or None,
        "title": description or None,
        "cover_url": cover_url_from_payload(metadata) or None,
        "author_avatar_url": author_avatar_url(metadata) or None,
    }


def _insert_event(
    conn: sqlite3.Connection,
    job_id: int,
    event_type: str,
    message: str = "",
    data: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO job_events (job_id, event_type, message, data_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            job_id,
            event_type,
            message,
            json.dumps(data, ensure_ascii=False) if data else None,
            utc_now(),
        ),
    )


def add_event(
    job_id: int,
    event_type: str,
    message: str = "",
    data: dict[str, Any] | None = None,
) -> None:
    with connect() as conn:
        _insert_event(conn, job_id, event_type, message, data)


def normalize_app_settings(values: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    if "skip_existing" in values:
        normalized["skip_existing"] = bool(values["skip_existing"])
    if "author_folders" in values:
        normalized["author_folders"] = bool(values["author_folders"])
    if "filename_template" in values:
        template = str(values["filename_template"] or "").strip()
        normalized["filename_template"] = template[:180] or DEFAULT_APP_SETTINGS["filename_template"]
    if "queue_paused" in values:
        normalized["queue_paused"] = bool(values["queue_paused"])
    if "max_concurrent_downloads" in values:
        try:
            normalized["max_concurrent_downloads"] = max(1, min(6, int(values["max_concurrent_downloads"])))
        except (TypeError, ValueError):
            normalized["max_concurrent_downloads"] = DEFAULT_APP_SETTINGS["max_concurrent_downloads"]
    if "auto_retry_attempts" in values:
        try:
            normalized["auto_retry_attempts"] = max(0, min(10, int(values["auto_retry_attempts"])))
        except (TypeError, ValueError):
            normalized["auto_retry_attempts"] = DEFAULT_APP_SETTINGS["auto_retry_attempts"]
    if "auto_retry_delay_seconds" in values:
        try:
            normalized["auto_retry_delay_seconds"] = max(0, min(86400, int(values["auto_retry_delay_seconds"])))
        except (TypeError, ValueError):
            normalized["auto_retry_delay_seconds"] = DEFAULT_APP_SETTINGS["auto_retry_delay_seconds"]
    if "telegram_enabled" in values:
        normalized["telegram_enabled"] = bool(values["telegram_enabled"])
    if "telegram_bot_token" in values:
        normalized["telegram_bot_token"] = str(values["telegram_bot_token"] or "").strip()[:300]
    if "telegram_chat_id" in values:
        normalized["telegram_chat_id"] = str(values["telegram_chat_id"] or "").strip()[:120]
    if "telegram_notify_success" in values:
        normalized["telegram_notify_success"] = bool(values["telegram_notify_success"])
    if "telegram_notify_failure" in values:
        normalized["telegram_notify_failure"] = bool(values["telegram_notify_failure"])
    return normalized


def normalize_quality_preference(value: Any, default: str = "best") -> str:
    quality = str(value or default or "best").strip().lower()
    quality = QUALITY_ALIASES.get(quality, quality)
    if quality == "best":
        return quality
    if not quality.isdigit():
        raise ValueError(f"Unsupported quality preference: {value}")
    target = int(quality)
    if target < 144 or target > 4320:
        raise ValueError(f"Unsupported quality preference: {value}")
    return quality


def normalize_parser_settings(values: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    if "parser_adapter" in values:
        adapter = str(values["parser_adapter"] or "").strip()
        if adapter not in PARSER_ADAPTERS:
            raise ValueError(f"Unsupported parser adapter: {adapter}")
        normalized["parser_adapter"] = adapter
    if "douyin_cookie" in values:
        normalized["douyin_cookie"] = normalize_cookie_header(values["douyin_cookie"])[:20000]
    if "douyin_user_agent" in values:
        douyin_user_agent = str(values["douyin_user_agent"] or "").strip()
        normalized["douyin_user_agent"] = (douyin_user_agent or settings.douyin_user_agent)[:500]
    if "tiktok_cookie" in values:
        normalized["tiktok_cookie"] = normalize_cookie_header(values["tiktok_cookie"])[:20000]
    if "tiktok_user_agent" in values:
        tiktok_user_agent = str(values["tiktok_user_agent"] or "").strip()
        normalized["tiktok_user_agent"] = (tiktok_user_agent or settings.tiktok_user_agent)[:500]
    if "bilibili_cookie" in values:
        normalized["bilibili_cookie"] = normalize_cookie_header(values["bilibili_cookie"])[:20000]
    if "bilibili_user_agent" in values:
        bilibili_user_agent = str(values["bilibili_user_agent"] or "").strip()
        normalized["bilibili_user_agent"] = (bilibili_user_agent or settings.bilibili_user_agent)[:500]
    return normalized


def get_app_settings() -> dict[str, Any]:
    result = dict(DEFAULT_APP_SETTINGS)
    with connect() as conn:
        rows = conn.execute("SELECT key, value_json FROM app_settings").fetchall()
    for row in rows:
        if row["key"] not in result:
            continue
        try:
            result[row["key"]] = json.loads(row["value_json"])
        except json.JSONDecodeError:
            pass
    return result


def get_public_app_settings() -> dict[str, Any]:
    result = get_app_settings()
    token = str(result.get("telegram_bot_token") or "")
    result["telegram_bot_token"] = ""
    result["telegram_bot_configured"] = bool(token)
    return result


def get_auth_admin() -> dict[str, str] | None:
    values: dict[str, str] = {}
    try:
        with connect() as conn:
            rows = conn.execute(
                """
                SELECT key, value_json
                FROM app_settings
                WHERE key IN ('auth_admin_username', 'auth_admin_password_hash')
                """
            ).fetchall()
    except sqlite3.OperationalError:
        return None
    for row in rows:
        try:
            values[row["key"]] = str(json.loads(row["value_json"]) or "")
        except json.JSONDecodeError:
            continue
    username = values.get("auth_admin_username", "").strip()
    password_hash = values.get("auth_admin_password_hash", "").strip()
    if not username or not password_hash:
        return None
    return {"username": username, "password_hash": password_hash}


def auth_admin_configured() -> bool:
    return get_auth_admin() is not None


def set_auth_admin(username: str, password_hash: str) -> dict[str, str]:
    clean_username = str(username or "").strip()[:80]
    clean_hash = str(password_hash or "").strip()
    if not clean_username or not clean_hash:
        raise ValueError("Username and password hash are required")
    now = utc_now()
    with connect() as conn:
        for key, value in {
            "auth_admin_username": clean_username,
            "auth_admin_password_hash": clean_hash,
        }.items():
            conn.execute(
                """
                INSERT INTO app_settings (key, value_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = excluded.updated_at
                """,
                (key, json.dumps(value, ensure_ascii=False), now),
            )
    return {"username": clean_username, "password_hash": clean_hash}


def get_parser_settings(include_secret: bool = False) -> dict[str, Any]:
    result = dict(DEFAULT_PARSER_SETTINGS)
    stored_cookie = ""
    stored_tiktok_cookie = ""
    stored_bilibili_cookie = ""
    try:
        with connect() as conn:
            rows = conn.execute("SELECT key, value_json FROM app_settings").fetchall()
    except sqlite3.OperationalError:
        rows = []
    for row in rows:
        if row["key"] not in result:
            continue
        try:
            value = json.loads(row["value_json"])
        except json.JSONDecodeError:
            continue
        result[row["key"]] = value
        if row["key"] == "douyin_cookie":
            stored_cookie = str(value or "")
        if row["key"] == "tiktok_cookie":
            stored_tiktok_cookie = str(value or "")
        if row["key"] == "bilibili_cookie":
            stored_bilibili_cookie = str(value or "")
    if result.get("parser_adapter") not in PARSER_ADAPTERS:
        result["parser_adapter"] = settings.parser_adapter
    result["douyin_signer_kind"] = "local_abogus"
    configured_cookie = str(result.get("douyin_cookie") or "")
    if not include_secret:
        result["douyin_cookie"] = ""
        result["douyin_cookie_configured"] = bool(configured_cookie)
        result["douyin_cookie_source"] = "database" if stored_cookie else ("environment" if settings.douyin_cookie else "none")
        configured_tiktok_cookie = str(result.get("tiktok_cookie") or "")
        result["tiktok_cookie"] = ""
        result["tiktok_cookie_configured"] = bool(configured_tiktok_cookie)
        result["tiktok_cookie_source"] = "database" if stored_tiktok_cookie else ("environment" if settings.tiktok_cookie else "none")
        configured_bilibili_cookie = str(result.get("bilibili_cookie") or "")
        result["bilibili_cookie"] = ""
        result["bilibili_cookie_configured"] = bool(configured_bilibili_cookie)
        result["bilibili_cookie_source"] = "database" if stored_bilibili_cookie else ("environment" if settings.bilibili_cookie else "none")
    return result


def update_app_settings(values: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_app_settings(values)
    now = utc_now()
    with connect() as conn:
        for key, value in normalized.items():
            conn.execute(
                """
                INSERT INTO app_settings (key, value_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = excluded.updated_at
                """,
                (key, json.dumps(value, ensure_ascii=False), now),
            )
    return get_app_settings()


def update_parser_settings(values: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_parser_settings(values)
    now = utc_now()
    with connect() as conn:
        for key, value in normalized.items():
            conn.execute(
                """
                INSERT INTO app_settings (key, value_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = excluded.updated_at
                """,
                (key, json.dumps(value, ensure_ascii=False), now),
            )
    return get_parser_settings()


def cleanup_parse_cache(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM parse_cache WHERE expires_at < ?", (utc_now(),))


def create_parse_cache(
    url: str,
    payload: dict[str, Any],
    ttl_seconds: int = PARSE_CACHE_TTL_SECONDS,
) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    cache_id = secrets.token_urlsafe(24)
    expires_at = (now + timedelta(seconds=ttl_seconds)).isoformat()
    with connect() as conn:
        cleanup_parse_cache(conn)
        conn.execute(
            """
            INSERT INTO parse_cache (id, url, payload_json, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                cache_id,
                url.strip(),
                json.dumps(payload, ensure_ascii=False),
                now.isoformat(),
                expires_at,
            ),
        )
    return {"id": cache_id, "expires_at": expires_at}


def get_parse_cache(cache_id: str | None) -> dict[str, Any] | None:
    cache_id = str(cache_id or "").strip()
    if not cache_id:
        return None
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM parse_cache WHERE id = ?",
            (cache_id,),
        ).fetchone()
        if not row:
            return None
        try:
            expires_at = datetime.fromisoformat(row["expires_at"])
        except ValueError:
            expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        if expires_at <= datetime.now(timezone.utc):
            conn.execute("DELETE FROM parse_cache WHERE id = ?", (cache_id,))
            return None
        try:
            payload = json.loads(row["payload_json"])
        except json.JSONDecodeError:
            return None
    if isinstance(payload, dict):
        payload["_clipnest_parse_cache"] = {
            "id": row["id"],
            "url": row["url"],
            "expires_at": row["expires_at"],
        }
    return {
        "id": row["id"],
        "url": row["url"],
        "payload": payload,
        "expires_at": row["expires_at"],
    }


def create_job(
    url: str,
    quality_preference: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    quality = normalize_quality_preference(quality_preference)
    metadata_fields = metadata_job_fields(metadata)
    now = utc_now()
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO jobs (
                url, status, progress, message, quality_preference,
                platform, video_id, author_name, author_id, description, title, cover_url, author_avatar_url,
                metadata_json, created_at, updated_at
            )
            VALUES (?, 'queued', 0, 'Queued', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                url.strip(),
                quality,
                metadata_fields.get("platform"),
                metadata_fields.get("video_id"),
                metadata_fields.get("author_name"),
                metadata_fields.get("author_id"),
                metadata_fields.get("description"),
                metadata_fields.get("title"),
                metadata_fields.get("cover_url"),
                metadata_fields.get("author_avatar_url"),
                json.dumps(metadata, ensure_ascii=False) if metadata else None,
                now,
                now,
            ),
        )
        _insert_event(
            conn,
            int(cur.lastrowid),
            "created",
            "Queued",
            {"url": url.strip(), "quality": quality, "cached_parse": bool(metadata)},
        )
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (cur.lastrowid,)).fetchone()
        return row_to_dict(row) or {}


def find_finished_by_url(url: str, quality_preference: str | None = None) -> dict[str, Any] | None:
    clean_url = str(url or "").strip()
    if not clean_url:
        return None
    quality = normalize_quality_preference(quality_preference)
    with connect() as conn:
        row = conn.execute(
            """
            SELECT * FROM jobs
            WHERE status = 'finished'
              AND url = ?
              AND COALESCE(quality_preference, 'best') = ?
              AND file_path IS NOT NULL
            ORDER BY id DESC
            LIMIT 1
            """,
            (clean_url, quality),
        ).fetchone()
    return row_to_dict(row)


def create_job_or_reuse_finished(
    url: str,
    quality_preference: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    found = find_finished_by_url(url, quality_preference=quality_preference)
    if found:
        found["reused"] = True
        return found
    created = create_job(url, quality_preference=quality_preference, metadata=metadata)
    created["reused"] = False
    return created


def author_crawl_row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    data["quality_preference"] = normalize_quality_preference(data.get("quality_preference"))
    data["has_more"] = bool(data.get("has_more"))
    return data


def author_name_for_sec_uid(conn: sqlite3.Connection, sec_uid: str) -> str:
    sec_uid = str(sec_uid or "").strip()
    if not sec_uid:
        return ""
    rows = conn.execute(
        """
        SELECT author_name, metadata_json
        FROM jobs
        WHERE COALESCE(metadata_json, '') LIKE ?
        ORDER BY id DESC
        LIMIT 50
        """,
        (f"%{sec_uid}%",),
    ).fetchall()
    for row in rows:
        author_name = str(row["author_name"] or "").strip()
        if author_name:
            return author_name
        try:
            metadata = json.loads(row["metadata_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        author_name = author_name_from_metadata(metadata)
        if author_name:
            return author_name
    return ""


def attach_author_crawl_names(conn: sqlite3.Connection, jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for job in jobs:
        if str(job.get("author_name") or "").strip():
            continue
        author_name = author_name_for_sec_uid(conn, str(job.get("sec_uid") or ""))
        if author_name:
            job["author_name"] = author_name
    return jobs


def latest_author_crawl_for(
    conn: sqlite3.Connection,
    author_name: str,
    sec_uid: str = "",
) -> dict[str, Any]:
    clauses = ["author_name = ?"]
    params: list[Any] = [author_name]
    if sec_uid:
        clauses.append("sec_uid = ?")
        params.append(sec_uid)
    row = conn.execute(
        f"""
        SELECT id, status, found_count, created_count, reused_count,
               pages_scanned, created_at, updated_at, finished_at
        FROM author_crawl_jobs
        WHERE {' OR '.join(clauses)}
        ORDER BY COALESCE(finished_at, updated_at, created_at) DESC, id DESC
        LIMIT 1
        """,
        params,
    ).fetchone()
    return dict(row) if row else {}


def normalize_author_crawl_mode(value: str | None) -> str:
    return "incremental" if str(value or "").strip().lower() in {"incremental", "inc"} else "full"


def _clamp_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def normalize_sync_source_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    data["enabled"] = bool(data.get("enabled"))
    data["include_images"] = bool(data.get("include_images"))
    data["quality_preference"] = normalize_quality_preference(data.get("quality_preference"))
    raw_avatar_path = str(data.get("avatar_path") or "")
    data["avatar_path"] = relative_asset_path(raw_avatar_path)
    if raw_avatar_path and not data["avatar_path"] and not Path(raw_avatar_path).is_absolute():
        data["avatar_path"] = raw_avatar_path.replace("\\", "/").lstrip("/")
    return data


def sync_source_payload(values: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    source = existing or {}
    mode = normalize_author_crawl_mode(values.get("sync_mode", source.get("sync_mode") or "incremental"))
    platform = str(values.get("platform", source.get("platform") or "douyin") or "douyin").strip().lower()
    if platform not in {"douyin", "tiktok", "bilibili"}:
        platform = "douyin"
    return {
        "platform": platform,
        "url": str(values.get("url", source.get("url") or "") or "").strip(),
        "author_name": str(values.get("author_name", source.get("author_name") or "") or "").strip()[:120],
        "sec_uid": str(values.get("sec_uid", source.get("sec_uid") or "") or "").strip(),
        "avatar_url": str(values.get("avatar_url", source.get("avatar_url") or "") or "").strip()[:2000],
        "avatar_path": str(values.get("avatar_path", source.get("avatar_path") or "") or "").strip()[:1000],
        "enabled": 1 if bool(values.get("enabled", source.get("enabled", True))) else 0,
        "sync_mode": mode,
        "max_items": _clamp_int(values.get("max_items", source.get("max_items") or 200), 200, 1, 1000),
        "max_pages": _clamp_int(values.get("max_pages", source.get("max_pages") or 80), 80, 1, 100),
        "delay_ms": _clamp_int(values.get("delay_ms", source.get("delay_ms") or 600), 600, 0, 5000),
        "quality_preference": normalize_quality_preference(values.get("quality_preference", source.get("quality_preference"))),
        "include_images": 1 if bool(values.get("include_images", source.get("include_images", False))) else 0,
        "stop_after_existing_pages": _clamp_int(
            values.get("stop_after_existing_pages", source.get("stop_after_existing_pages") or 2),
            2,
            1,
            20,
        ),
        "stop_after_existing_items": _clamp_int(
            values.get("stop_after_existing_items", source.get("stop_after_existing_items") or 36),
            36,
            1,
            300,
        ),
        "notes": str(values.get("notes", source.get("notes") or "") or "").strip()[:500],
    }


def get_author_sync_source(source_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM author_sync_sources WHERE id = ?", (int(source_id),)).fetchone()
    return normalize_sync_source_row(row)


def find_author_sync_source(
    platform: str | None = None,
    sec_uid: str | None = None,
    author_name: str | None = None,
    url: str | None = None,
) -> dict[str, Any] | None:
    clean_platform = str(platform or "douyin").strip().lower() or "douyin"
    clean_sec_uid = str(sec_uid or "").strip()
    clean_author = str(author_name or "").strip()
    clean_url = str(url or "").strip()
    clauses: list[str] = ["platform = ?"]
    params: list[Any] = [clean_platform]
    identity_clauses: list[str] = []
    if clean_sec_uid:
        identity_clauses.append("sec_uid = ?")
        params.append(clean_sec_uid)
    if clean_author:
        identity_clauses.append("author_name = ?")
        params.append(clean_author)
    if clean_url:
        identity_clauses.append("url = ?")
        params.append(clean_url)
    if not identity_clauses:
        return None
    with connect() as conn:
        row = conn.execute(
            f"""
            SELECT * FROM author_sync_sources
            WHERE {' AND '.join(clauses)} AND ({' OR '.join(identity_clauses)})
            ORDER BY
                CASE WHEN sec_uid != '' THEN 0 ELSE 1 END,
                updated_at DESC,
                id DESC
            LIMIT 1
            """,
            params,
        ).fetchone()
    return normalize_sync_source_row(row)


def upsert_author_sync_source(values: dict[str, Any]) -> dict[str, Any]:
    existing = None
    explicit_id = values.get("id")
    if explicit_id:
        existing = get_author_sync_source(int(explicit_id))
    if not existing:
        existing = find_author_sync_source(
            values.get("platform"),
            values.get("sec_uid"),
            values.get("author_name"),
            values.get("url"),
        )
    payload = sync_source_payload(values, existing)
    if not payload["url"] and payload["sec_uid"]:
        payload["url"] = (
            f"https://space.bilibili.com/{payload['sec_uid']}/upload/video"
            if payload["platform"] == "bilibili"
            else f"https://www.douyin.com/user/{payload['sec_uid']}"
        )
    if not payload["url"]:
        raise ValueError("同步源需要作者主页链接或主页 ID")
    if not payload["author_name"] and payload["sec_uid"]:
        payload["author_name"] = payload["sec_uid"]
    now = utc_now()
    with connect() as conn:
        if existing:
            conn.execute(
                """
                UPDATE author_sync_sources
                SET platform = ?, url = ?, author_name = ?, sec_uid = ?, avatar_url = ?, avatar_path = ?,
                    enabled = ?, sync_mode = ?, max_items = ?, max_pages = ?, delay_ms = ?,
                    quality_preference = ?, include_images = ?, stop_after_existing_pages = ?, stop_after_existing_items = ?,
                    notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    payload["platform"],
                    payload["url"],
                    payload["author_name"],
                    payload["sec_uid"],
                    payload["avatar_url"],
                    payload["avatar_path"],
                    payload["enabled"],
                    payload["sync_mode"],
                    payload["max_items"],
                    payload["max_pages"],
                    payload["delay_ms"],
                    payload["quality_preference"],
                    payload["include_images"],
                    payload["stop_after_existing_pages"],
                    payload["stop_after_existing_items"],
                    payload["notes"],
                    now,
                    int(existing["id"]),
                ),
            )
            source_id = int(existing["id"])
        else:
            cur = conn.execute(
                """
                INSERT INTO author_sync_sources (
                    platform, url, author_name, sec_uid, avatar_url, avatar_path, enabled, sync_mode,
                    max_items, max_pages, delay_ms, quality_preference, include_images, stop_after_existing_pages,
                    stop_after_existing_items, notes, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["platform"],
                    payload["url"],
                    payload["author_name"],
                    payload["sec_uid"],
                    payload["avatar_url"],
                    payload["avatar_path"],
                    payload["enabled"],
                    payload["sync_mode"],
                    payload["max_items"],
                    payload["max_pages"],
                    payload["delay_ms"],
                    payload["quality_preference"],
                    payload["include_images"],
                    payload["stop_after_existing_pages"],
                    payload["stop_after_existing_items"],
                    payload["notes"],
                    now,
                    now,
                ),
            )
            source_id = int(cur.lastrowid)
        row = conn.execute("SELECT * FROM author_sync_sources WHERE id = ?", (source_id,)).fetchone()
    return normalize_sync_source_row(row) or {}


def update_author_sync_source(source_id: int, values: dict[str, Any]) -> dict[str, Any]:
    existing = get_author_sync_source(source_id)
    if not existing:
        raise KeyError("Author sync source not found")
    return upsert_author_sync_source({**values, "id": source_id})


def delete_author_sync_source(source_id: int) -> bool:
    with connect() as conn:
        cur = conn.execute("DELETE FROM author_sync_sources WHERE id = ?", (int(source_id),))
        return cur.rowcount > 0


def list_author_sync_sources(
    page: int = 1,
    page_size: int = 24,
    q: str | None = None,
    platform: str | None = None,
    enabled: bool | None = None,
) -> dict[str, Any]:
    page = max(1, int(page or 1))
    page_size = max(1, min(100, int(page_size or 24)))
    clauses: list[str] = []
    params: list[Any] = []
    clean_platform = str(platform or "").strip().lower()
    if clean_platform:
        clauses.append("platform = ?")
        params.append(clean_platform)
    if enabled is not None:
        clauses.append("enabled = ?")
        params.append(1 if enabled else 0)
    if q:
        like = f"%{q}%"
        clauses.append("(author_name LIKE ? OR sec_uid LIKE ? OR url LIKE ? OR notes LIKE ?)")
        params.extend([like, like, like, like])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    offset = (page - 1) * page_size
    with connect() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM author_sync_sources {where}", params).fetchone()[0]
        stat_where_clauses: list[str] = []
        stat_params: list[Any] = []
        if clean_platform:
            stat_where_clauses.append("platform = ?")
            stat_params.append(clean_platform)
        stat_where = f"WHERE {' AND '.join(stat_where_clauses)}" if stat_where_clauses else ""
        stats_row = conn.execute(
            f"""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN enabled = 1 THEN 1 ELSE 0 END) AS enabled,
                   SUM(CASE WHEN enabled = 0 THEN 1 ELSE 0 END) AS disabled,
                   SUM(CASE WHEN COALESCE(sec_uid, '') = '' THEN 1 ELSE 0 END) AS missing_identity
            FROM author_sync_sources
            {stat_where}
            """,
            stat_params,
        ).fetchone()
        rows = conn.execute(
            f"""
            SELECT *
            FROM author_sync_sources
            {where}
            ORDER BY enabled DESC, COALESCE(last_sync_at, updated_at, created_at) DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (*params, page_size, offset),
        ).fetchall()
        sources = [normalize_sync_source_row(row) or {} for row in rows]
        enrich_author_sync_sources(conn, sources)
    return {
        "items": sources,
        "page": page,
        "page_size": page_size,
        "total": total or 0,
        "total_pages": max(1, (int(total or 0) + page_size - 1) // page_size),
        "stats": {
            "total": int(stats_row["total"] or 0) if stats_row else 0,
            "enabled": int(stats_row["enabled"] or 0) if stats_row else 0,
            "disabled": int(stats_row["disabled"] or 0) if stats_row else 0,
            "missing_identity": int(stats_row["missing_identity"] or 0) if stats_row else 0,
        },
    }


def enrich_author_sync_sources(conn: sqlite3.Connection, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for source in sources:
        platform = str(source.get("platform") or "").strip().lower()
        author_name = str(source.get("author_name") or "").strip()
        sec_uid = str(source.get("sec_uid") or "").strip()
        source_url = str(source.get("url") or "").strip()
        clauses: list[str] = []
        params: list[Any] = []
        if platform:
            clauses.append("COALESCE(platform, '') = ?")
            params.append(platform)
        identity_clauses: list[str] = []
        if author_name:
            identity_clauses.append("COALESCE(author_name, '') = ?")
            params.append(author_name)
        if sec_uid:
            identity_clauses.append("COALESCE(metadata_json, '') LIKE ?")
            params.append(f"%{sec_uid}%")
        if source_url:
            identity_clauses.append("url = ?")
            params.append(source_url)
        if not identity_clauses:
            source["media_total"] = 0
            source["media_finished"] = 0
            source["media_failed"] = 0
            source["media_bytes"] = 0
            source["latest_finished_at"] = ""
            source["latest_created_at"] = ""
            continue
        if identity_clauses:
            clauses.append(f"({' OR '.join(identity_clauses)})")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        stats = conn.execute(
            f"""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN status = 'finished' THEN 1 ELSE 0 END) AS finished,
                   SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
                   SUM(CASE WHEN status = 'finished' THEN COALESCE(size_bytes, 0) ELSE 0 END) AS bytes,
                   MAX(finished_at) AS latest_finished_at,
                   MAX(created_at) AS latest_created_at
            FROM jobs
            {where}
            """,
            params,
        ).fetchone()
        source["media_total"] = int(stats["total"] or 0) if stats else 0
        source["media_finished"] = int(stats["finished"] or 0) if stats else 0
        source["media_failed"] = int(stats["failed"] or 0) if stats else 0
        source["media_bytes"] = int(stats["bytes"] or 0) if stats else 0
        source["latest_finished_at"] = stats["latest_finished_at"] if stats else ""
        source["latest_created_at"] = stats["latest_created_at"] if stats else ""
        crawl_clauses: list[str] = []
        crawl_params: list[Any] = []
        if source.get("id"):
            crawl_clauses.append("sync_source_id = ?")
            crawl_params.append(int(source["id"]))
        if sec_uid:
            crawl_clauses.append("sec_uid = ?")
            crawl_params.append(sec_uid)
        if author_name:
            crawl_clauses.append("author_name = ?")
            crawl_params.append(author_name)
        if crawl_clauses:
            latest_crawl = conn.execute(
                f"""
                SELECT stop_reason, has_more
                FROM author_crawl_jobs
                WHERE {' OR '.join(crawl_clauses)}
                ORDER BY COALESCE(finished_at, updated_at, created_at) DESC, id DESC
                LIMIT 1
                """,
                crawl_params,
            ).fetchone()
            source["last_stop_reason"] = latest_crawl["stop_reason"] if latest_crawl else ""
            source["last_has_more"] = bool(latest_crawl["has_more"]) if latest_crawl else False
        if not source.get("avatar_url") or not source.get("avatar_path"):
            latest = conn.execute(
                f"""
                SELECT metadata_json, author_avatar_url, author_avatar_path
                FROM jobs
                {where}
                ORDER BY COALESCE(finished_at, created_at) DESC, id DESC
                LIMIT 1
                """,
                params,
            ).fetchone()
            metadata: dict[str, Any] = {}
            if latest and latest["metadata_json"]:
                try:
                    metadata = json.loads(latest["metadata_json"])
                except json.JSONDecodeError:
                    metadata = {}
            source["avatar_url"] = source.get("avatar_url") or (latest["author_avatar_url"] if latest else "") or author_avatar_url(metadata)
            source["avatar_path"] = source.get("avatar_path") or relative_asset_path(latest["author_avatar_path"] if latest else "")
    return sources


def import_author_sync_sources_from_library(platform: str | None = "douyin", limit: int = 2000) -> dict[str, Any]:
    authors = list_authors(limit=limit, platform=platform)
    created = 0
    updated = 0
    skipped = 0
    items: list[dict[str, Any]] = []
    for author in authors:
        sec_uid = str(author.get("sec_uid") or "").strip()
        if not sec_uid:
            skipped += 1
            continue
        before = find_author_sync_source(platform=platform, sec_uid=sec_uid, author_name=author.get("author"))
        payload = {
            "platform": platform or "douyin",
            "url": f"https://www.douyin.com/user/{sec_uid}",
            "author_name": author.get("author") or "",
            "sec_uid": sec_uid,
            "avatar_url": author.get("avatar_url") or "",
            "avatar_path": author.get("avatar_path") or "",
        }
        if not before:
            payload.update(
                {
                    "enabled": True,
                    "sync_mode": "incremental",
                    "max_items": 200,
                    "max_pages": 80,
                    "delay_ms": 600,
                    "include_images": False,
                }
            )
        source = upsert_author_sync_source(payload)
        if before:
            updated += 1
        else:
            created += 1
        items.append(source)
    return {"created": created, "updated": updated, "skipped": skipped, "items": items}


def create_author_crawl_job(
    url: str,
    max_items: int = 200,
    max_pages: int = 80,
    delay_ms: int = 600,
    quality_preference: str | None = None,
    author_name: str | None = None,
    sec_uid: str | None = None,
    cursor: int = 0,
    sync_mode: str | None = None,
    sync_source_id: int | None = None,
) -> dict[str, Any]:
    quality = normalize_quality_preference(quality_preference)
    mode = normalize_author_crawl_mode(sync_mode)
    now = utc_now()
    clean_author_name = str(author_name or "").strip()[:120]
    clean_sec_uid = str(sec_uid or "").strip()
    clean_cursor = max(0, int(cursor or 0))
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO author_crawl_jobs (
                sync_source_id, url, author_name, sec_uid, status, progress, message, quality_preference, sync_mode,
                max_items, max_pages, delay_ms, cursor, stop_reason, has_more, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 'queued', 0, '排队中', ?, ?, ?, ?, ?, ?, '', 0, ?, ?)
            """,
            (
                int(sync_source_id) if sync_source_id else None,
                url.strip(),
                clean_author_name,
                clean_sec_uid,
                quality,
                mode,
                max(1, min(1000, int(max_items or 200))),
                max(1, min(100, int(max_pages or 80))),
                max(0, min(5000, int(delay_ms or 0))),
                clean_cursor,
                now,
                now,
            ),
        )
        row = conn.execute("SELECT * FROM author_crawl_jobs WHERE id = ?", (cur.lastrowid,)).fetchone()
    return author_crawl_row_to_dict(row) or {}


def get_author_crawl_job(crawl_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM author_crawl_jobs WHERE id = ?", (crawl_id,)).fetchone()
        job = author_crawl_row_to_dict(row)
        if job:
            attach_author_crawl_names(conn, [job])
    return job


def list_author_crawl_jobs(limit: int = 20) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM author_crawl_jobs
            ORDER BY
                CASE
                    WHEN status IN ('running', 'pausing', 'cancelling') THEN 0
                    WHEN status = 'queued' THEN 1
                    WHEN status = 'paused' THEN 2
                    ELSE 3
                END,
                CASE WHEN status IN ('running', 'pausing', 'cancelling', 'queued', 'paused') THEN id ELSE -id END ASC
            LIMIT ?
            """,
            (max(1, min(100, int(limit or 20))),),
        ).fetchall()
        jobs = [author_crawl_row_to_dict(row) or {} for row in rows]
        attach_author_crawl_names(conn, jobs)
    return jobs


def list_author_crawl_history_for_source(source_id: int, limit: int = 30) -> list[dict[str, Any]]:
    source = get_author_sync_source(source_id)
    if not source:
        raise KeyError("Author sync source not found")
    clauses = ["sync_source_id = ?"]
    params: list[Any] = [int(source_id)]
    sec_uid = str(source.get("sec_uid") or "").strip()
    author_name = str(source.get("author_name") or "").strip()
    url = str(source.get("url") or "").strip()
    if sec_uid:
        clauses.append("sec_uid = ?")
        params.append(sec_uid)
    if author_name:
        clauses.append("author_name = ?")
        params.append(author_name)
    if url:
        clauses.append("url = ?")
        params.append(url)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM author_crawl_jobs
            WHERE {' OR '.join(clauses)}
            ORDER BY COALESCE(finished_at, updated_at, created_at) DESC, id DESC
            LIMIT ?
            """,
            (*params, max(1, min(100, int(limit or 30)))),
        ).fetchall()
        jobs = [author_crawl_row_to_dict(row) or {} for row in rows]
        attach_author_crawl_names(conn, jobs)
    return jobs


def author_sync_source_detail(source_id: int, history_limit: int = 30) -> dict[str, Any]:
    source = get_author_sync_source(source_id)
    if not source:
        raise KeyError("Author sync source not found")
    history = list_author_crawl_history_for_source(source_id, limit=history_limit)
    finished = [job for job in history if str(job.get("status") or "") == "finished"]
    failed = [job for job in history if str(job.get("status") or "") == "failed"]
    latest = history[0] if history else {}
    return {
        "source": source,
        "history": history,
        "summary": {
            "history_count": len(history),
            "finished_count": len(finished),
            "failed_count": len(failed),
            "latest_status": latest.get("status") or source.get("last_sync_status") or "",
            "latest_message": latest.get("message") or source.get("last_sync_message") or "",
            "latest_stop_reason": latest.get("stop_reason") or "",
            "latest_has_more": bool(latest.get("has_more")),
        },
    }


def update_author_crawl_job(crawl_id: int, **fields: Any) -> None:
    if not fields:
        return
    fields["updated_at"] = utc_now()
    columns = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values())
    values.append(crawl_id)
    with connect() as conn:
        conn.execute(f"UPDATE author_crawl_jobs SET {columns} WHERE id = ?", values)


def cleanup_author_crawl_jobs(statuses: list[str], limit: int = 500) -> dict[str, Any]:
    clean_statuses = [str(status or "").strip().lower() for status in statuses if str(status or "").strip()]
    allowed = {"finished", "failed", "cancelled"}
    clean_statuses = [status for status in clean_statuses if status in allowed]
    if not clean_statuses:
        return {"deleted": [], "skipped": []}
    placeholders = ", ".join("?" for _ in clean_statuses)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT id, status
            FROM author_crawl_jobs
            WHERE status IN ({placeholders})
            ORDER BY id DESC
            LIMIT ?
            """,
            (*clean_statuses, max(1, min(2000, int(limit or 500)))),
        ).fetchall()
        ids = [int(row["id"]) for row in rows]
        if ids:
            id_placeholders = ", ".join("?" for _ in ids)
            conn.execute(f"DELETE FROM author_crawl_jobs WHERE id IN ({id_placeholders})", ids)
    return {"deleted": ids, "skipped": []}


def active_author_crawl_for_source(source_id: int) -> dict[str, Any] | None:
    if not source_id:
        return None
    with connect() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM author_crawl_jobs
            WHERE sync_source_id = ?
              AND status IN ('queued', 'running', 'pausing', 'paused')
            ORDER BY id DESC
            LIMIT 1
            """,
            (int(source_id),),
        ).fetchone()
    return author_crawl_row_to_dict(row)


def claim_next_author_crawl_job() -> dict[str, Any] | None:
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        now = utc_now()
        row = conn.execute(
            """
            SELECT * FROM author_crawl_jobs
            WHERE status = 'queued'
            ORDER BY id ASC
            LIMIT 1
            """
        ).fetchone()
        if not row:
            return None
        conn.execute(
            """
            UPDATE author_crawl_jobs
            SET status = 'running',
                progress = CASE WHEN progress >= 100 THEN 0 ELSE progress END,
                message = '抓取中',
                started_at = COALESCE(started_at, ?),
                finished_at = NULL,
                updated_at = ?
            WHERE id = ? AND status = 'queued'
            """,
            (now, now, row["id"]),
        )
        claimed = conn.execute("SELECT * FROM author_crawl_jobs WHERE id = ?", (row["id"],)).fetchone()
    return author_crawl_row_to_dict(claimed)


def author_crawl_status(crawl_id: int) -> str:
    with connect() as conn:
        row = conn.execute("SELECT status FROM author_crawl_jobs WHERE id = ?", (crawl_id,)).fetchone()
    return str(row["status"] if row else "")


def update_author_sync_source_from_crawl(
    crawl_id: int,
    last_seen_video_id: str = "",
    last_seen_publish_time: int = 0,
    deleted_skipped_count: int = 0,
) -> None:
    with connect() as conn:
        crawl = conn.execute("SELECT * FROM author_crawl_jobs WHERE id = ?", (int(crawl_id),)).fetchone()
        if not crawl:
            return
        source_id = crawl["sync_source_id"]
        source: sqlite3.Row | None = None
        if source_id:
            source = conn.execute("SELECT * FROM author_sync_sources WHERE id = ?", (source_id,)).fetchone()
        if not source:
            source_platform = str((source or {}).get("platform") or "").strip().lower()
            if not source_platform:
                source_platform = "bilibili" if "space.bilibili.com" in str(crawl["url"] or "") else "douyin"
            found = find_author_sync_source(
                platform=source_platform,
                sec_uid=crawl["sec_uid"],
                author_name=crawl["author_name"],
                url=crawl["url"],
            )
            if found:
                source_id = int(found["id"])
        if not source_id:
            return
        now = utc_now()
        conn.execute(
            """
            UPDATE author_sync_sources
            SET url = CASE WHEN ? != '' THEN ? ELSE url END,
                author_name = CASE WHEN ? != '' THEN ? ELSE author_name END,
                sec_uid = CASE WHEN ? != '' THEN ? ELSE sec_uid END,
                last_cursor = ?,
                last_seen_video_id = CASE WHEN ? != '' THEN ? ELSE last_seen_video_id END,
                last_seen_publish_time = CASE WHEN ? > 0 THEN ? ELSE last_seen_publish_time END,
                last_sync_job_id = ?,
                last_sync_status = ?,
                last_sync_message = ?,
                last_sync_at = ?,
                last_finished_at = CASE WHEN ? IS NOT NULL THEN ? ELSE last_finished_at END,
                last_found_count = ?,
                last_created_count = ?,
                last_reused_count = ?,
                last_deleted_skipped_count = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                str(crawl["url"] or ""),
                str(crawl["url"] or ""),
                str(crawl["author_name"] or ""),
                str(crawl["author_name"] or ""),
                str(crawl["sec_uid"] or ""),
                str(crawl["sec_uid"] or ""),
                int(crawl["cursor"] or 0),
                last_seen_video_id,
                last_seen_video_id,
                int(last_seen_publish_time or 0),
                int(last_seen_publish_time or 0),
                int(crawl_id),
                str(crawl["status"] or ""),
                str(crawl["message"] or ""),
                now,
                crawl["finished_at"],
                crawl["finished_at"],
                int(crawl["found_count"] or 0),
                int(crawl["created_count"] or 0),
                int(crawl["reused_count"] or 0),
                int(deleted_skipped_count or 0),
                now,
                int(source_id),
            ),
        )


def delete_job(job_id: int) -> bool:
    with connect() as conn:
        conn.execute("DELETE FROM job_events WHERE job_id = ?", (job_id,))
        cur = conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        return cur.rowcount > 0


def mark_deleted_media(job: dict[str, Any], reason: str = "manual") -> None:
    if not job:
        return
    metadata = job.get("metadata") if isinstance(job.get("metadata"), dict) else {}
    metadata_fields = metadata_job_fields(metadata)
    platform = str(job.get("platform") or metadata_fields.get("platform") or "").strip() or "douyin"
    video_id = str(job.get("video_id") or metadata_fields.get("video_id") or "").strip()
    url = str(job.get("url") or "").strip()
    if not platform and not video_id and not url:
        return
    author_name = str(job.get("author_name") or metadata_fields.get("author_name") or "").strip()
    title = str(job.get("title") or job.get("description") or metadata_fields.get("title") or "").strip()
    now = utc_now()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO deleted_media (
                platform, video_id, url, author_name, title, source_job_id, reason, deleted_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                platform,
                video_id,
                url,
                author_name,
                title,
                int(job.get("id") or 0) or None,
                str(reason or "manual")[:40],
                now,
            ),
        )


def is_deleted_media(platform: str | None = None, video_id: str | None = None, url: str | None = None) -> bool:
    clean_platform = str(platform or "").strip()
    clean_video_id = str(video_id or "").strip()
    clean_url = str(url or "").strip()
    clauses: list[str] = []
    params: list[Any] = []
    if clean_video_id:
        if clean_platform:
            clauses.append("(video_id = ? AND (platform = ? OR platform = ''))")
            params.extend([clean_video_id, clean_platform])
        else:
            clauses.append("video_id = ?")
            params.append(clean_video_id)
    if clean_url:
        clauses.append("url = ?")
        params.append(clean_url)
    if not clauses:
        return False
    with connect() as conn:
        row = conn.execute(
            f"SELECT 1 FROM deleted_media WHERE {' OR '.join(clauses)} LIMIT 1",
            params,
        ).fetchone()
    return row is not None


def list_author_jobs(author: str, platform: str | None = None) -> list[dict[str, Any]]:
    author = str(author or "Unknown")
    clauses = ["COALESCE(author_name, 'Unknown') = ?"]
    params: list[Any] = [author]
    clean_platform = str(platform or "").strip().lower()
    if clean_platform:
        clauses.append("COALESCE(platform, '') = ?")
        params.append(clean_platform)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM jobs
            WHERE {' AND '.join(clauses)}
            ORDER BY id ASC
            """,
            params,
        ).fetchall()
    return [row_to_dict(row) or {} for row in rows]


def get_job(job_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return row_to_dict(row)


def list_jobs(
    limit: int = 100,
    status: str | None = None,
    author: str | None = None,
    q: str | None = None,
    platform: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if status:
        if status == "active":
            clauses.append("status IN ('queued', 'retry', 'parsing', 'downloading', 'cancelling')")
        else:
            clauses.append("status = ?")
            params.append(status)
    if author:
        clauses.append("COALESCE(author_name, 'Unknown') = ?")
        params.append(author)
    if platform:
        clauses.append("COALESCE(platform, '') = ?")
        params.append(str(platform).strip().lower())
    if q:
        like = f"%{q}%"
        clauses.append(
            """
            (
                url LIKE ? OR
                COALESCE(title, '') LIKE ? OR
                COALESCE(description, '') LIKE ? OR
                COALESCE(author_name, '') LIKE ? OR
                COALESCE(video_id, '') LIKE ?
            )
            """
        )
        params.extend([like, like, like, like, like])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM jobs {where} ORDER BY {JOB_LIST_ORDER_SQL} LIMIT ?",
            (*params, limit),
        ).fetchall()
        return [row_to_dict(row) or {} for row in rows]


def job_filter_clauses(
    status: str | None = None,
    author: str | None = None,
    q: str | None = None,
    platform: str | None = None,
) -> tuple[list[str], list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if status:
        if status == "active":
            clauses.append("status IN ('queued', 'retry', 'parsing', 'downloading', 'cancelling')")
        else:
            clauses.append("status = ?")
            params.append(status)
    if author:
        clauses.append("COALESCE(author_name, 'Unknown') = ?")
        params.append(author)
    if platform:
        clauses.append("COALESCE(platform, '') = ?")
        params.append(platform)
    if q:
        like = f"%{q}%"
        clauses.append(
            """
            (
                url LIKE ? OR
                COALESCE(title, '') LIKE ? OR
                COALESCE(description, '') LIKE ? OR
                COALESCE(author_name, '') LIKE ? OR
                COALESCE(video_id, '') LIKE ?
            )
            """
        )
        params.extend([like, like, like, like, like])
    return clauses, params


def list_jobs_page(
    page: int = 1,
    page_size: int = 50,
    status: str | None = None,
    author: str | None = None,
    q: str | None = None,
    platform: str | None = None,
) -> dict[str, Any]:
    page = max(1, int(page or 1))
    page_size = max(1, min(100, int(page_size or 50)))
    clauses, params = job_filter_clauses(status=status, author=author, q=q, platform=platform)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    offset = (page - 1) * page_size
    with connect() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM jobs {where}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM jobs {where} ORDER BY {JOB_LIST_ORDER_SQL} LIMIT ? OFFSET ?",
            (*params, page_size, offset),
        ).fetchall()
    return {
        "items": [row_to_dict(row) or {} for row in rows],
        "page": page,
        "page_size": page_size,
        "total": total or 0,
        "total_pages": max(1, (int(total or 0) + page_size - 1) // page_size),
    }


def find_finished_video(platform: str, video_id: str, exclude_job_id: int | None = None) -> dict[str, Any] | None:
    platform = str(platform or "").strip()
    video_id = str(video_id or "").strip()
    if not platform or not video_id:
        return None
    clauses = [
        "status = 'finished'",
        "platform = ?",
        "video_id = ?",
        "file_path IS NOT NULL",
    ]
    params: list[Any] = [platform, video_id]
    if exclude_job_id is not None:
        clauses.append("id != ?")
        params.append(exclude_job_id)
    with connect() as conn:
        row = conn.execute(
            f"SELECT * FROM jobs WHERE {' AND '.join(clauses)} ORDER BY id DESC LIMIT 1",
            params,
        ).fetchone()
    return row_to_dict(row)


def find_existing_video_job(
    platform: str,
    video_id: str,
    quality_preference: str | None = None,
    match_quality: bool = True,
) -> dict[str, Any] | None:
    platform = str(platform or "").strip()
    video_id = str(video_id or "").strip()
    if not platform or not video_id:
        return None
    with connect() as conn:
        if not match_quality:
            row = conn.execute(
                """
                SELECT * FROM jobs
                WHERE platform = ?
                  AND video_id = ?
                  AND status NOT IN ('failed', 'cancelled')
                ORDER BY id DESC
                LIMIT 1
                """,
                (platform, video_id),
            ).fetchone()
            return row_to_dict(row)
        quality = normalize_quality_preference(quality_preference)
        row = conn.execute(
            """
            SELECT * FROM jobs
            WHERE platform = ?
              AND video_id = ?
              AND COALESCE(quality_preference, 'best') = ?
              AND status NOT IN ('failed', 'cancelled')
            ORDER BY id DESC
            LIMIT 1
            """,
            (platform, video_id, quality),
        ).fetchone()
    return row_to_dict(row)


def claim_next_job() -> dict[str, Any] | None:
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        now = utc_now()
        row = conn.execute(
            """
            SELECT * FROM jobs
            WHERE status IN ('queued', 'retry')
              AND (next_attempt_at IS NULL OR next_attempt_at <= ?)
            ORDER BY id ASC
            LIMIT 1
            """,
            (now,),
        ).fetchone()
        if not row:
            return None
        conn.execute(
            """
            UPDATE jobs
            SET status = 'parsing', progress = 2, message = 'Parsing',
                started_at = COALESCE(started_at, ?), next_attempt_at = NULL, updated_at = ?
            WHERE id = ? AND status IN ('queued', 'retry')
            """,
            (now, now, row["id"]),
        )
        claimed = conn.execute("SELECT * FROM jobs WHERE id = ?", (row["id"],)).fetchone()
        return row_to_dict(claimed)


def is_cancel_requested(job_id: int) -> bool:
    with connect() as conn:
        row = conn.execute("SELECT status FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return bool(row and row["status"] in {"cancelling", "cancelled"})


def update_job(job_id: int, **fields: Any) -> None:
    if not fields:
        return
    original_fields = dict(fields)
    fields["updated_at"] = utc_now()
    if "metadata" in fields:
        fields["metadata_json"] = json.dumps(fields.pop("metadata"), ensure_ascii=False)
    columns = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values())
    values.append(job_id)
    with connect() as conn:
        previous = conn.execute("SELECT status FROM jobs WHERE id = ?", (job_id,)).fetchone()
        conn.execute(f"UPDATE jobs SET {columns} WHERE id = ?", values)
        new_status = original_fields.get("status")
        if previous and new_status and previous["status"] != new_status:
            _insert_event(
                conn,
                job_id,
                f"status:{new_status}",
                str(original_fields.get("message") or new_status),
                {"from": previous["status"], "to": new_status},
            )


def list_events(job_id: int) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM job_events
            WHERE job_id = ?
            ORDER BY id DESC
            LIMIT 100
            """,
            (job_id,),
        ).fetchall()
    events: list[dict[str, Any]] = []
    for row in rows:
        event = dict(row)
        if event.get("data_json"):
            try:
                event["data"] = json.loads(event["data_json"])
            except json.JSONDecodeError:
                event["data"] = {}
        else:
            event["data"] = {}
        event.pop("data_json", None)
        events.append(event)
    return events


def normalize_event_row(row: sqlite3.Row) -> dict[str, Any]:
    event = dict(row)
    if event.get("data_json"):
        try:
            event["data"] = json.loads(event["data_json"])
        except json.JSONDecodeError:
            event["data"] = {}
    else:
        event["data"] = {}
    event.pop("data_json", None)
    return event


def list_recent_events(limit: int = 100) -> list[dict[str, Any]]:
    return list_events_page(page=1, page_size=max(1, min(500, int(limit)))).get("items", [])


def list_events_page(
    page: int = 1,
    page_size: int = 30,
    q: str | None = None,
    event_type: str | None = None,
    platform: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    page = max(1, int(page or 1))
    page_size = max(1, min(100, int(page_size or 30)))
    clauses: list[str] = []
    params: list[Any] = []
    clean_event_type = str(event_type or "").strip()
    if clean_event_type:
        clauses.append("job_events.event_type = ?")
        params.append(clean_event_type)
    clean_platform = str(platform or "").strip().lower()
    if clean_platform:
        clauses.append("COALESCE(jobs.platform, '') = ?")
        params.append(clean_platform)
    clean_status = str(status or "").strip().lower()
    if clean_status:
        clauses.append("COALESCE(jobs.status, '') = ?")
        params.append(clean_status)
    if q:
        like = f"%{q}%"
        clauses.append(
            """
            (
                job_events.message LIKE ? OR
                job_events.event_type LIKE ? OR
                COALESCE(jobs.title, '') LIKE ? OR
                COALESCE(jobs.description, '') LIKE ? OR
                COALESCE(jobs.author_name, '') LIKE ? OR
                COALESCE(jobs.url, '') LIKE ? OR
                COALESCE(jobs.video_id, '') LIKE ?
            )
            """
        )
        params.extend([like, like, like, like, like, like, like])
    if date_from:
        clauses.append("job_events.created_at >= ?")
        params.append(day_start(date_from))
    if date_to:
        clauses.append("job_events.created_at <= ?")
        params.append(day_end(date_to))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    offset = (page - 1) * page_size
    with connect() as conn:
        total = conn.execute(
            f"""
            SELECT COUNT(*)
            FROM job_events
            LEFT JOIN jobs ON jobs.id = job_events.job_id
            {where}
            """,
            params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT job_events.*,
                   jobs.title,
                   jobs.description,
                   jobs.author_name,
                   jobs.platform,
                   jobs.status AS job_status,
                   jobs.video_id,
                   jobs.url
            FROM job_events
            LEFT JOIN jobs ON jobs.id = job_events.job_id
            {where}
            ORDER BY job_events.id DESC
            LIMIT ? OFFSET ?
            """,
            (*params, page_size, offset),
        ).fetchall()
        type_rows = conn.execute(
            """
            SELECT event_type, COUNT(*) AS count
            FROM job_events
            GROUP BY event_type
            ORDER BY count DESC, event_type ASC
            LIMIT 50
            """
        ).fetchall()
    return {
        "items": [normalize_event_row(row) for row in rows],
        "page": page,
        "page_size": page_size,
        "total": total or 0,
        "total_pages": max(1, (int(total or 0) + page_size - 1) // page_size),
        "event_types": [dict(row) for row in type_rows],
    }


def checkpoint() -> None:
    with connect() as conn:
        conn.execute("PRAGMA wal_checkpoint(FULL)")


def get_stats() -> dict[str, Any]:
    with connect() as conn:
        totals = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'finished' THEN 1 ELSE 0 END) AS finished,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
                SUM(CASE WHEN status IN ('queued', 'retry') THEN 1 ELSE 0 END) AS queued,
                SUM(CASE WHEN status IN ('parsing', 'downloading', 'cancelling') THEN 1 ELSE 0 END) AS running,
                SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled,
                SUM(COALESCE(size_bytes, 0)) AS bytes
            FROM jobs
            """
        ).fetchone()
        platform_rows = conn.execute(
            """
            SELECT COALESCE(platform, 'unknown') AS platform,
                   COUNT(*) AS total,
                   SUM(CASE WHEN status = 'finished' THEN 1 ELSE 0 END) AS finished,
                   SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
                   SUM(COALESCE(size_bytes, 0)) AS bytes
            FROM jobs
            GROUP BY COALESCE(platform, 'unknown')
            ORDER BY finished DESC, total DESC
            """
        ).fetchall()
        media_rows = conn.execute(
            f"""
            SELECT
                SUM(CASE WHEN status = 'finished' AND ({media_type_clause("image")}) THEN 1 ELSE 0 END) AS images,
                SUM(CASE WHEN status = 'finished' AND NOT ({media_type_clause("image")}) THEN 1 ELSE 0 END) AS videos
            FROM jobs
            """
        ).fetchone()
        chart_rows = conn.execute(
            """
            SELECT substr(COALESCE(finished_at, created_at), 1, 10) AS day,
                   SUM(CASE WHEN status = 'finished' THEN 1 ELSE 0 END) AS finished,
                   SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
                   SUM(CASE WHEN status = 'finished' THEN COALESCE(size_bytes, 0) ELSE 0 END) AS bytes
            FROM jobs
            WHERE COALESCE(finished_at, created_at) >= datetime('now', '-13 days')
            GROUP BY day
            ORDER BY day ASC
            """
        ).fetchall()
        recent_rows = conn.execute(
            """
            SELECT id, title, description, author_name, platform, status, size_bytes, resolution,
                   created_at, finished_at, error
            FROM jobs
            WHERE status IN ('finished', 'failed')
            ORDER BY COALESCE(finished_at, updated_at, created_at) DESC, id DESC
            LIMIT 8
            """
        ).fetchall()
        deleted_count = conn.execute("SELECT COUNT(*) FROM deleted_media").fetchone()[0]
        authors = conn.execute(
            """
            SELECT COALESCE(author_name, 'Unknown') AS author,
                   COUNT(*) AS count,
                   SUM(COALESCE(size_bytes, 0)) AS bytes
            FROM jobs
            WHERE status = 'finished'
            GROUP BY COALESCE(author_name, 'Unknown')
            ORDER BY count DESC, bytes DESC
            LIMIT 50
            """
        ).fetchall()
    return {
        "total": totals["total"] or 0,
        "finished": totals["finished"] or 0,
        "failed": totals["failed"] or 0,
        "queued": totals["queued"] or 0,
        "running": totals["running"] or 0,
        "cancelled": totals["cancelled"] or 0,
        "bytes": totals["bytes"] or 0,
        "deleted": deleted_count or 0,
        "platforms": [dict(row) for row in platform_rows],
        "media": {
            "videos": media_rows["videos"] or 0,
            "images": media_rows["images"] or 0,
        },
        "chart": [dict(row) for row in chart_rows],
        "recent": [dict(row) for row in recent_rows],
        "authors": [dict(row) for row in authors],
    }


def list_deleted_media(
    page: int = 1,
    page_size: int = 30,
    q: str | None = None,
    platform: str | None = None,
    author: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    page = max(1, int(page or 1))
    page_size = max(1, min(100, int(page_size or 30)))
    clauses: list[str] = []
    params: list[Any] = []
    clean_platform = str(platform or "").strip().lower()
    if clean_platform:
        clauses.append("platform = ?")
        params.append(clean_platform)
    clean_author = str(author or "").strip()
    if clean_author:
        clauses.append("author_name = ?")
        params.append(clean_author)
    if date_from:
        clauses.append("deleted_at >= ?")
        params.append(day_start(date_from))
    if date_to:
        clauses.append("deleted_at <= ?")
        params.append(day_end(date_to))
    if q:
        like = f"%{q}%"
        clauses.append(
            """
            (
                COALESCE(title, '') LIKE ? OR
                COALESCE(author_name, '') LIKE ? OR
                COALESCE(video_id, '') LIKE ? OR
                COALESCE(url, '') LIKE ?
            )
            """
        )
        params.extend([like, like, like, like])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    offset = (page - 1) * page_size
    with connect() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM deleted_media {where}", params).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT *
            FROM deleted_media
            {where}
            ORDER BY deleted_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (*params, page_size, offset),
        ).fetchall()
    return {
        "items": [dict(row) for row in rows],
        "page": page,
        "page_size": page_size,
        "total": total or 0,
        "total_pages": max(1, (int(total or 0) + page_size - 1) // page_size),
    }


def delete_deleted_media_record(record_id: int) -> bool:
    with connect() as conn:
        cur = conn.execute("DELETE FROM deleted_media WHERE id = ?", (int(record_id),))
        return cur.rowcount > 0


def clear_deleted_media_records(
    platform: str | None = None,
    author_name: str | None = None,
    q: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> int:
    clauses: list[str] = []
    params: list[Any] = []
    clean_platform = str(platform or "").strip().lower()
    if clean_platform:
        clauses.append("platform = ?")
        params.append(clean_platform)
    clean_author = str(author_name or "").strip()
    if clean_author:
        clauses.append("author_name = ?")
        params.append(clean_author)
    if date_from:
        clauses.append("deleted_at >= ?")
        params.append(day_start(date_from))
    if date_to:
        clauses.append("deleted_at <= ?")
        params.append(day_end(date_to))
    if q:
        like = f"%{q}%"
        clauses.append(
            """
            (
                COALESCE(title, '') LIKE ? OR
                COALESCE(author_name, '') LIKE ? OR
                COALESCE(video_id, '') LIKE ? OR
                COALESCE(url, '') LIKE ?
            )
            """
        )
        params.extend([like, like, like, like])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect() as conn:
        cur = conn.execute(f"DELETE FROM deleted_media {where}", params)
        return cur.rowcount


def list_authors(limit: int = 100, platform: str | None = None) -> list[dict[str, Any]]:
    clean_platform = str(platform or "").strip().lower()
    where = "WHERE COALESCE(platform, '') = ?" if clean_platform else ""
    params: list[Any] = [clean_platform] if clean_platform else []
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT COALESCE(author_name, 'Unknown') AS author,
                   COUNT(*) AS total,
                   SUM(CASE WHEN status = 'finished' THEN 1 ELSE 0 END) AS finished,
                   SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
                   SUM(COALESCE(size_bytes, 0)) AS bytes,
                   MAX(created_at) AS latest_created_at,
                   MAX(finished_at) AS latest_finished_at
            FROM jobs
            {where}
            GROUP BY COALESCE(author_name, 'Unknown')
            ORDER BY finished DESC, total DESC, bytes DESC
            LIMIT ?
            """,
            (*params, max(1, min(500, int(limit)))),
        ).fetchall()
        authors = [dict(row) for row in rows]
        attach_author_assets(conn, authors, platform=clean_platform or None)
    return authors


def attach_author_assets(
    conn: sqlite3.Connection,
    authors: list[dict[str, Any]],
    platform: str | None = None,
) -> list[dict[str, Any]]:
    clean_platform = str(platform or "").strip().lower()
    for author in authors:
        clauses = ["COALESCE(author_name, 'Unknown') = ?"]
        params: list[Any] = [author["author"]]
        if clean_platform:
            clauses.append("COALESCE(platform, '') = ?")
            params.append(clean_platform)
        latest = conn.execute(
            f"""
            SELECT metadata_json, cover_url, cover_path, author_avatar_url, author_avatar_path
            FROM jobs
            WHERE {' AND '.join(clauses)}
            ORDER BY COALESCE(finished_at, created_at) DESC, id DESC
            LIMIT 1
            """,
            params,
        ).fetchone()
        metadata: dict[str, Any] = {}
        if latest and latest["metadata_json"]:
            try:
                metadata = json.loads(latest["metadata_json"])
            except json.JSONDecodeError:
                metadata = {}
        author["avatar_url"] = (latest["author_avatar_url"] if latest else "") or author_avatar_url(metadata)
        author["avatar_path"] = relative_asset_path(latest["author_avatar_path"] if latest else "")
        author["cover_url"] = latest["cover_url"] if latest else ""
        author["cover_path"] = relative_asset_path(latest["cover_path"] if latest else "")
        author["sec_uid"] = author_sec_uid_from_history(conn, author["author"], metadata, platform=clean_platform or None)
        sync = latest_author_crawl_for(conn, author["author"], author["sec_uid"])
        author["last_sync_at"] = sync.get("finished_at") or sync.get("updated_at") or sync.get("created_at") or ""
        author["last_sync_status"] = sync.get("status") or ""
        author["last_sync_created_count"] = sync.get("created_count") or 0
        author["last_sync_reused_count"] = sync.get("reused_count") or 0
        author["last_sync_found_count"] = sync.get("found_count") or 0
    return authors


def list_authors_page(
    page: int = 1,
    page_size: int = 24,
    q: str | None = None,
    platform: str | None = None,
) -> dict[str, Any]:
    page = max(1, int(page or 1))
    page_size = max(1, min(100, int(page_size or 24)))
    clauses: list[str] = []
    params: list[Any] = []
    clean_platform = str(platform or "").strip().lower()
    if clean_platform:
        clauses.append("COALESCE(platform, '') = ?")
        params.append(clean_platform)
    if q:
        clauses.append("COALESCE(author_name, 'Unknown') LIKE ?")
        params.append(f"%{q}%")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    offset = (page - 1) * page_size
    with connect() as conn:
        total = conn.execute(
            f"""
            SELECT COUNT(*) FROM (
                SELECT COALESCE(author_name, 'Unknown') AS author
                FROM jobs
                {where}
                GROUP BY COALESCE(author_name, 'Unknown')
            )
            """,
            params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT COALESCE(author_name, 'Unknown') AS author,
                   COUNT(*) AS total,
                   SUM(CASE WHEN status = 'finished' THEN 1 ELSE 0 END) AS finished,
                   SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
                   SUM(COALESCE(size_bytes, 0)) AS bytes,
                   MAX(created_at) AS latest_created_at,
                   MAX(finished_at) AS latest_finished_at
            FROM jobs
            {where}
            GROUP BY COALESCE(author_name, 'Unknown')
            ORDER BY finished DESC, total DESC, bytes DESC
            LIMIT ? OFFSET ?
            """,
            (*params, page_size, offset),
        ).fetchall()
        items = attach_author_assets(conn, [dict(row) for row in rows], platform=clean_platform or None)
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total or 0,
        "total_pages": max(1, (int(total or 0) + page_size - 1) // page_size),
    }


def media_type_clause(media_type: str | None) -> str:
    if media_type == "image":
        return """
            (
                COALESCE(metadata_json, '') LIKE '%"type": "image"%' OR
                LOWER(COALESCE(file_path, '')) LIKE '%.jpg' OR
                LOWER(COALESCE(file_path, '')) LIKE '%.jpeg' OR
                LOWER(COALESCE(file_path, '')) LIKE '%.png' OR
                LOWER(COALESCE(file_path, '')) LIKE '%.webp'
            )
        """
    if media_type == "video":
        return """
            NOT (
                COALESCE(metadata_json, '') LIKE '%"type": "image"%' OR
                LOWER(COALESCE(file_path, '')) LIKE '%.jpg' OR
                LOWER(COALESCE(file_path, '')) LIKE '%.jpeg' OR
                LOWER(COALESCE(file_path, '')) LIKE '%.png' OR
                LOWER(COALESCE(file_path, '')) LIKE '%.webp'
            )
        """
    return ""


def library_identity_sql(alias: str = "jobs") -> str:
    prefix = f"{alias}." if alias else ""
    return f"""
        CASE
            WHEN COALESCE({prefix}platform, '') != '' AND COALESCE({prefix}video_id, '') != ''
                THEN 'video:' || COALESCE({prefix}platform, '') || ':' || COALESCE({prefix}video_id, '')
            WHEN COALESCE({prefix}file_path, '') != ''
                THEN 'file:' || COALESCE({prefix}file_path, '')
            ELSE 'url:' || COALESCE({prefix}url, '')
        END
    """


def library_sort_sql(sort: str | None) -> str:
    if sort == "publish_desc":
        return """
            CAST(COALESCE(json_extract(metadata_json, '$.create_time'), 0) AS INTEGER) DESC,
            COALESCE(finished_at, created_at) DESC,
            id DESC
        """
    if sort == "oldest":
        return "COALESCE(finished_at, created_at) ASC, id ASC"
    if sort == "size_desc":
        return "COALESCE(size_bytes, 0) DESC, id DESC"
    if sort == "size_asc":
        return "COALESCE(size_bytes, 0) ASC, id DESC"
    if sort == "title":
        return "COALESCE(title, description, video_id, url, '') COLLATE NOCASE ASC, id DESC"
    return "COALESCE(finished_at, created_at) DESC, id DESC"


def day_start(value: str | None) -> str:
    text = str(value or "").strip()
    return f"{text}T00:00:00" if text and "T" not in text else text


def day_end(value: str | None) -> str:
    text = str(value or "").strip()
    return f"{text}T23:59:59" if text and "T" not in text else text


def library_publish_time_value(item: dict[str, Any]) -> int:
    metadata = item.get("metadata") if isinstance(item, dict) else {}
    if not isinstance(metadata, dict):
        return 0
    try:
        return int(metadata.get("create_time") or 0)
    except (TypeError, ValueError):
        return 0


def library_fallback_time_value(item: dict[str, Any]) -> str:
    return str(item.get("finished_at") or item.get("created_at") or "")


def list_library_jobs_page(
    page: int = 1,
    page_size: int = 30,
    author: str | None = None,
    media_type: str | None = None,
    q: str | None = None,
    sort: str | None = None,
    platform: str | None = None,
    status: str | None = None,
    date_field: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    page = max(1, int(page or 1))
    page_size = max(1, min(100, int(page_size or 30)))
    clean_status = str(status or "finished").strip().lower()
    valid_statuses = {"finished", "failed", "cancelled", "queued", "retry", "parsing", "downloading", "cancelling", "active", "all"}
    if clean_status not in valid_statuses:
        clean_status = "finished"
    if clean_status == "all":
        clauses: list[str] = []
    elif clean_status == "active":
        clauses = ["status IN ('queued', 'retry', 'parsing', 'downloading', 'cancelling')"]
    else:
        clauses = ["status = ?"]
    params: list[Any] = [] if clean_status in {"all", "active"} else [clean_status]
    clean_platform = str(platform or "").strip().lower()
    if clean_platform:
        clauses.append("COALESCE(platform, '') = ?")
        params.append(clean_platform)
    if author:
        clauses.append("COALESCE(author_name, 'Unknown') = ?")
        params.append(author)
    type_clause = media_type_clause(media_type)
    if type_clause:
        clauses.append(type_clause)
    if q:
        like = f"%{q}%"
        clauses.append(
            """
            (
                url LIKE ? OR
                COALESCE(title, '') LIKE ? OR
                COALESCE(description, '') LIKE ? OR
                COALESCE(author_name, '') LIKE ? OR
                COALESCE(video_id, '') LIKE ?
            )
            """
        )
        params.extend([like, like, like, like, like])
    field = str(date_field or "download").strip().lower()
    if field == "publish":
        date_expr = "datetime(CAST(COALESCE(json_extract(metadata_json, '$.create_time'), 0) AS INTEGER), 'unixepoch')"
    elif field == "created":
        date_expr = "created_at"
    else:
        date_expr = "COALESCE(finished_at, updated_at, created_at)"
    if date_from:
        clauses.append(f"{date_expr} >= ?")
        params.append(day_start(date_from))
    if date_to:
        clauses.append(f"{date_expr} <= ?")
        params.append(day_end(date_to))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    offset = (page - 1) * page_size
    identity_sql = library_identity_sql()
    with connect() as conn:
        total = conn.execute(
            f"""
            SELECT COUNT(*) FROM (
                SELECT {identity_sql} AS library_identity
                FROM jobs
                {where}
                GROUP BY library_identity
            )
            """,
            params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT * FROM jobs
            WHERE id IN (
                SELECT MAX(id)
                FROM jobs
                {where}
                GROUP BY {identity_sql}
            )
            ORDER BY {library_sort_sql(sort)}
            LIMIT ? OFFSET ?
            """,
            (*params, page_size, offset),
        ).fetchall()
    items = [row_to_dict(row) or {} for row in rows]
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total or 0,
        "total_pages": max(1, (int(total or 0) + page_size - 1) // page_size),
    }


def author_detail(author: str, platform: str | None = None) -> dict[str, Any]:
    author = str(author or "Unknown")
    image_clause = media_type_clause("image")
    clean_platform = str(platform or "").strip().lower()
    clauses = ["COALESCE(author_name, 'Unknown') = ?"]
    params: list[Any] = [author]
    if clean_platform:
        clauses.append("COALESCE(platform, '') = ?")
        params.append(clean_platform)
    where = f"WHERE {' AND '.join(clauses)}"
    with connect() as conn:
        totals = conn.execute(
            f"""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'finished' THEN 1 ELSE 0 END) AS finished,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
                SUM(CASE WHEN status = 'finished' AND ({image_clause}) THEN 1 ELSE 0 END) AS images,
                SUM(CASE WHEN status = 'finished' AND NOT ({image_clause}) THEN 1 ELSE 0 END) AS videos,
                SUM(CASE WHEN status = 'finished' THEN COALESCE(size_bytes, 0) ELSE 0 END) AS bytes,
                MAX(created_at) AS latest_created_at,
                MAX(finished_at) AS latest_finished_at
            FROM jobs
            {where}
            """,
            params,
        ).fetchone()
        item = dict(totals) if totals else {}
        item["author"] = author
        attach_author_assets(conn, [item], platform=clean_platform or None)
        latest = conn.execute(
            f"""
            SELECT metadata_json
            FROM jobs
            {where}
              AND metadata_json IS NOT NULL
            ORDER BY id DESC
            LIMIT 1
            """,
            params,
        ).fetchone()
        metadata: dict[str, Any] = {}
        if latest and latest["metadata_json"]:
            try:
                metadata = json.loads(latest["metadata_json"])
            except json.JSONDecodeError:
                metadata = {}
        item["sec_uid"] = author_sec_uid_from_history(conn, author, metadata, platform=clean_platform or None)
        item["sync_source"] = find_author_sync_source(
            platform=clean_platform or "douyin",
            sec_uid=item.get("sec_uid") or "",
            author_name=author,
        )
    return item


def cookie_activity() -> dict[str, Any]:
    with connect() as conn:
        latest_success = conn.execute(
            """
            SELECT * FROM job_events
            WHERE event_type = 'parse:success'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
        latest_parse_failure = conn.execute(
            """
            SELECT id, url, error_type, error, updated_at
            FROM jobs
            WHERE error_type = 'parse'
            ORDER BY updated_at DESC
            LIMIT 1
            """
        ).fetchone()
    return {
        "latest_parse_success": dict(latest_success) if latest_success else None,
        "latest_parse_failure": dict(latest_parse_failure) if latest_parse_failure else None,
    }


def referenced_media_paths() -> set[str]:
    with connect() as conn:
        rows = conn.execute("SELECT file_path, preview_path FROM jobs").fetchall()
    paths: set[str] = set()
    for row in rows:
        for key in ("file_path", "preview_path"):
            value = row[key]
            if value:
                paths.add(str(Path(value).resolve()))
    return paths


def scan_orphan_files(delete: bool = False, limit: int = 500) -> dict[str, Any]:
    root = Path(settings.download_dir).resolve()
    referenced = referenced_media_paths()
    orphans: list[dict[str, Any]] = []
    removed: list[str] = []
    if not root.exists():
        return {"root": str(root), "orphans": [], "removed": [], "truncated": False}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        resolved = str(path.resolve())
        if resolved in referenced:
            continue
        item = {"path": resolved, "size_bytes": path.stat().st_size}
        if delete:
            try:
                path.unlink()
                removed.append(resolved)
            except OSError as exc:
                item["error"] = str(exc)
                orphans.append(item)
        else:
            orphans.append(item)
        if len(orphans) + len(removed) >= limit:
            return {"root": str(root), "orphans": orphans, "removed": removed, "truncated": True}
    return {"root": str(root), "orphans": orphans, "removed": removed, "truncated": False}


def _duplicate_media_groups(conn: sqlite3.Connection, limit: int = 100) -> dict[str, Any]:
    limit = max(1, min(500, int(limit or 100)))
    identity_sql = library_identity_sql()
    group_rows = conn.execute(
        f"""
        SELECT {identity_sql} AS library_identity,
               COUNT(*) AS total,
               MAX(id) AS keep_job_id,
               MAX(COALESCE(finished_at, created_at)) AS latest_at
        FROM jobs
        WHERE status = 'finished'
        GROUP BY library_identity
        HAVING COUNT(*) > 1
        ORDER BY total DESC, latest_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    groups: list[dict[str, Any]] = []
    duplicate_count = 0
    duplicate_bytes = 0
    for group in group_rows:
        jobs = conn.execute(
            f"""
            SELECT * FROM jobs
            WHERE status = 'finished'
              AND ({identity_sql}) = ?
            ORDER BY id DESC
            """,
            (group["library_identity"],),
        ).fetchall()
        keep_job_id = int(group["keep_job_id"])
        keep_job = None
        duplicates: list[dict[str, Any]] = []
        for row in jobs:
            item = row_to_dict(row) or {}
            if int(item.get("id") or 0) == keep_job_id:
                keep_job = item
            else:
                duplicates.append(item)
                duplicate_count += 1
                duplicate_bytes += int(item.get("size_bytes") or 0)
        groups.append(
            {
                "identity": group["library_identity"],
                "total": int(group["total"] or 0),
                "keep_job": keep_job,
                "duplicates": duplicates,
                "duplicate_count": len(duplicates),
            }
        )
    return {
        "groups": groups,
        "group_count": len(groups),
        "duplicate_count": duplicate_count,
        "duplicate_bytes": duplicate_bytes,
        "truncated": len(group_rows) >= limit,
    }


def scan_duplicate_media_jobs(limit: int = 100) -> dict[str, Any]:
    with connect() as conn:
        return _duplicate_media_groups(conn, limit=limit)


def cleanup_duplicate_media_jobs(limit: int = 500) -> dict[str, Any]:
    with connect() as conn:
        scan = _duplicate_media_groups(conn, limit=limit)
        duplicate_ids = [
            int(item["id"])
            for group in scan["groups"]
            for item in group["duplicates"]
            if item.get("id")
        ][: max(1, min(500, int(limit or 500)))]
        for job_id in duplicate_ids:
            conn.execute("DELETE FROM job_events WHERE job_id = ?", (job_id,))
            conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    return {
        **scan,
        "deleted_job_ids": duplicate_ids,
        "deleted_count": len(duplicate_ids),
    }
