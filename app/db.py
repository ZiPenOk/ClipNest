import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .assets import cover_url_from_payload, relative_asset_path
from .config import settings


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
    "douyin_signer_kind": "local_abogus",
}
PARSER_ADAPTERS = {"native_douyin", "native_douyin_share"}
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
                url TEXT NOT NULL,
                sec_uid TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'queued',
                progress REAL NOT NULL DEFAULT 0,
                message TEXT NOT NULL DEFAULT '',
                quality_preference TEXT,
                max_items INTEGER NOT NULL DEFAULT 200,
                max_pages INTEGER NOT NULL DEFAULT 30,
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
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_author ON jobs(author_name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_next_attempt ON jobs(status, next_attempt_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_job_events_job ON job_events(job_id, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_parse_cache_expires ON parse_cache(expires_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_author_crawl_status ON author_crawl_jobs(status, id)")


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
        normalized["douyin_cookie"] = str(values["douyin_cookie"] or "").strip()[:20000]
    if "douyin_user_agent" in values:
        douyin_user_agent = str(values["douyin_user_agent"] or "").strip()
        normalized["douyin_user_agent"] = (douyin_user_agent or settings.douyin_user_agent)[:500]
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


def get_parser_settings(include_secret: bool = False) -> dict[str, Any]:
    result = dict(DEFAULT_PARSER_SETTINGS)
    stored_cookie = ""
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
    if result.get("parser_adapter") not in PARSER_ADAPTERS:
        result["parser_adapter"] = settings.parser_adapter
    result["douyin_signer_kind"] = "local_abogus"
    configured_cookie = str(result.get("douyin_cookie") or "")
    if not include_secret:
        result["douyin_cookie"] = ""
        result["douyin_cookie_configured"] = bool(configured_cookie)
        result["douyin_cookie_source"] = "database" if stored_cookie else ("environment" if settings.douyin_cookie else "none")
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
    return data


def create_author_crawl_job(
    url: str,
    max_items: int = 200,
    max_pages: int = 30,
    delay_ms: int = 600,
    quality_preference: str | None = None,
) -> dict[str, Any]:
    quality = normalize_quality_preference(quality_preference)
    now = utc_now()
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO author_crawl_jobs (
                url, status, progress, message, quality_preference,
                max_items, max_pages, delay_ms, created_at, updated_at
            )
            VALUES (?, 'queued', 0, '排队中', ?, ?, ?, ?, ?, ?)
            """,
            (
                url.strip(),
                quality,
                max(1, min(1000, int(max_items or 200))),
                max(1, min(100, int(max_pages or 30))),
                max(0, min(5000, int(delay_ms or 0))),
                now,
                now,
            ),
        )
        row = conn.execute("SELECT * FROM author_crawl_jobs WHERE id = ?", (cur.lastrowid,)).fetchone()
    return author_crawl_row_to_dict(row) or {}


def get_author_crawl_job(crawl_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM author_crawl_jobs WHERE id = ?", (crawl_id,)).fetchone()
    return author_crawl_row_to_dict(row)


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
    return [author_crawl_row_to_dict(row) or {} for row in rows]


def update_author_crawl_job(crawl_id: int, **fields: Any) -> None:
    if not fields:
        return
    fields["updated_at"] = utc_now()
    columns = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values())
    values.append(crawl_id)
    with connect() as conn:
        conn.execute(f"UPDATE author_crawl_jobs SET {columns} WHERE id = ?", values)


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


def delete_job(job_id: int) -> bool:
    with connect() as conn:
        conn.execute("DELETE FROM job_events WHERE job_id = ?", (job_id,))
        cur = conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        return cur.rowcount > 0


def get_job(job_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return row_to_dict(row)


def list_jobs(
    limit: int = 100,
    status: str | None = None,
    author: str | None = None,
    q: str | None = None,
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
) -> dict[str, Any]:
    page = max(1, int(page or 1))
    page_size = max(1, min(100, int(page_size or 50)))
    clauses, params = job_filter_clauses(status=status, author=author, q=q)
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
) -> dict[str, Any] | None:
    platform = str(platform or "").strip()
    video_id = str(video_id or "").strip()
    if not platform or not video_id:
        return None
    quality = normalize_quality_preference(quality_preference)
    with connect() as conn:
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


def list_recent_events(limit: int = 100) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT job_events.*, jobs.title, jobs.author_name, jobs.status AS job_status
            FROM job_events
            LEFT JOIN jobs ON jobs.id = job_events.job_id
            ORDER BY job_events.id DESC
            LIMIT ?
            """,
            (max(1, min(500, int(limit))),),
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
        "authors": [dict(row) for row in authors],
    }


def list_authors(limit: int = 100) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT COALESCE(author_name, 'Unknown') AS author,
                   COUNT(*) AS total,
                   SUM(CASE WHEN status = 'finished' THEN 1 ELSE 0 END) AS finished,
                   SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
                   SUM(COALESCE(size_bytes, 0)) AS bytes,
                   MAX(created_at) AS latest_created_at,
                   MAX(finished_at) AS latest_finished_at
            FROM jobs
            GROUP BY COALESCE(author_name, 'Unknown')
            ORDER BY finished DESC, total DESC, bytes DESC
            LIMIT ?
            """,
            (max(1, min(500, int(limit))),),
        ).fetchall()
        authors = [dict(row) for row in rows]
        for author in authors:
            latest = conn.execute(
                """
                SELECT metadata_json, cover_url, cover_path, author_avatar_url, author_avatar_path
                FROM jobs
                WHERE COALESCE(author_name, 'Unknown') = ?
                ORDER BY COALESCE(finished_at, created_at) DESC, id DESC
                LIMIT 1
                """,
                (author["author"],),
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
    return authors


def attach_author_assets(conn: sqlite3.Connection, authors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for author in authors:
        latest = conn.execute(
            """
            SELECT metadata_json, cover_url, cover_path, author_avatar_url, author_avatar_path
            FROM jobs
            WHERE COALESCE(author_name, 'Unknown') = ?
            ORDER BY COALESCE(finished_at, created_at) DESC, id DESC
            LIMIT 1
            """,
            (author["author"],),
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
    return authors


def list_authors_page(page: int = 1, page_size: int = 24, q: str | None = None) -> dict[str, Any]:
    page = max(1, int(page or 1))
    page_size = max(1, min(100, int(page_size or 24)))
    clauses: list[str] = []
    params: list[Any] = []
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
        items = attach_author_assets(conn, [dict(row) for row in rows])
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
    if sort == "oldest":
        return "COALESCE(finished_at, created_at) ASC, id ASC"
    if sort == "size_desc":
        return "COALESCE(size_bytes, 0) DESC, id DESC"
    if sort == "size_asc":
        return "COALESCE(size_bytes, 0) ASC, id DESC"
    if sort == "title":
        return "COALESCE(title, description, video_id, url, '') COLLATE NOCASE ASC, id DESC"
    return "COALESCE(finished_at, created_at) DESC, id DESC"


def list_library_jobs_page(
    page: int = 1,
    page_size: int = 30,
    author: str | None = None,
    media_type: str | None = None,
    q: str | None = None,
    sort: str | None = None,
) -> dict[str, Any]:
    page = max(1, int(page or 1))
    page_size = max(1, min(100, int(page_size or 30)))
    clauses = ["status = 'finished'"]
    params: list[Any] = []
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
    where = f"WHERE {' AND '.join(clauses)}"
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


def author_detail(author: str) -> dict[str, Any]:
    author = str(author or "Unknown")
    image_clause = media_type_clause("image")
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
            WHERE COALESCE(author_name, 'Unknown') = ?
            """,
            (author,),
        ).fetchone()
        item = dict(totals) if totals else {}
        item["author"] = author
        attach_author_assets(conn, [item])
        latest = conn.execute(
            """
            SELECT metadata_json
            FROM jobs
            WHERE COALESCE(author_name, 'Unknown') = ?
              AND metadata_json IS NOT NULL
            ORDER BY id DESC
            LIMIT 1
            """,
            (author,),
        ).fetchone()
        metadata: dict[str, Any] = {}
        if latest and latest["metadata_json"]:
            try:
                metadata = json.loads(latest["metadata_json"])
            except json.JSONDecodeError:
                metadata = {}
        item["sec_uid"] = author_sec_uid(metadata)
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
