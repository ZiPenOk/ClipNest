import asyncio
from datetime import datetime, timedelta, timezone
import threading
import traceback

from . import db, runtime_state
from .config import settings
from .downloader import DownloadCancelled, process_download
from .notifier import notify_job
from .parser import NativeDouyinParserAdapter


def retry_at(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=max(0, seconds))).isoformat()


def classify_error(exc: Exception) -> str:
    text = f"{type(exc).__name__}: {exc}".lower()
    if isinstance(exc, DownloadCancelled):
        return "cancelled"
    if "http 403" in text or "403 forbidden" in text:
        return "http_403"
    if "http 404" in text or "404 not found" in text:
        return "http_404"
    if "timeout" in text or "timed out" in text:
        return "timeout"
    if "parser" in text or "parse" in text or "aweme" in text:
        return "parse"
    if "ffmpeg" in text:
        return "media"
    if "incomplete download" in text:
        return "incomplete"
    return "unknown"


class DownloadWorker:
    def __init__(self):
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._thread_main, name="clipnest-download-worker", daemon=True)
        self._thread.start()

    async def stop(self) -> None:
        self.request_stop()
        if self._thread and self._thread.is_alive():
            await asyncio.to_thread(self._thread.join, 10)

    def request_stop(self) -> None:
        self._stop.set()

    async def run_forever(self) -> None:
        if self._thread and self._thread.is_alive():
            raise RuntimeError("Download worker thread is already running")
        self._stop.clear()
        await self._run()

    def _thread_main(self) -> None:
        asyncio.run(self._run())

    async def _run(self) -> None:
        active: set[asyncio.Task] = set()
        while not self._stop.is_set():
            app_settings = db.get_app_settings()
            max_concurrent = int(app_settings.get("max_concurrent_downloads") or 1)
            queue_paused = bool(app_settings.get("queue_paused"))

            if not queue_paused:
                while len(active) < max_concurrent and not self._stop.is_set():
                    job = db.claim_next_job()
                    if not job:
                        break
                    task = asyncio.create_task(self._process(job))
                    active.add(task)
                    task.add_done_callback(active.discard)

            if active:
                done, _ = await asyncio.wait(
                    set(active),
                    timeout=settings.poll_interval_seconds,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in done:
                    task.result()
            else:
                await asyncio.sleep(settings.poll_interval_seconds)

        if active:
            await asyncio.gather(*active, return_exceptions=True)

    async def _process(self, job: dict):
        job_id = int(job["id"])
        runtime_state.clear_job_progress(job_id)

        async def update_cb(**fields):
            if set(fields) == {"progress"}:
                runtime_state.set_job_progress(job_id, float(fields["progress"]))
                return
            db.update_job(job_id, **fields)
            if "progress" in fields:
                runtime_state.set_job_progress(job_id, float(fields["progress"]))

        async def cancel_check() -> bool:
            return self._stop.is_set() or db.is_cancel_requested(job_id)

        try:
            await process_download(job, update_cb, cancel_check=cancel_check)
            await notify_job(db.get_job(job_id), "success")
        except DownloadCancelled:
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
            db.add_event(job_id, "cancelled", "Download cancelled")
        except Exception as exc:
            error_text = f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=8)}"
            error_type = classify_error(exc)
            app_settings = db.get_app_settings()
            max_retries = int(app_settings.get("auto_retry_attempts") or 0)
            retry_delay = int(app_settings.get("auto_retry_delay_seconds") or 0)
            attempt_count = int(job.get("attempt_count") or 0)
            if attempt_count < max_retries:
                next_attempt_count = attempt_count + 1
                next_attempt_at = retry_at(retry_delay)
                db.update_job(
                    job_id,
                    status="retry",
                    progress=0,
                    message=f"Auto retry scheduled ({next_attempt_count}/{max_retries})",
                    error=error_text,
                    error_type=error_type,
                    attempt_count=next_attempt_count,
                    next_attempt_at=next_attempt_at,
                    started_at=None,
                )
                db.add_event(
                    job_id,
                    "auto_retry",
                    f"Auto retry scheduled ({next_attempt_count}/{max_retries})",
                    {
                        "attempt": next_attempt_count,
                        "max_attempts": max_retries,
                        "next_attempt_at": next_attempt_at,
                        "error_type": error_type,
                    },
                )
            else:
                db.update_job(
                    job_id,
                    status="failed",
                    progress=100,
                    message="Failed",
                    error=error_text,
                    error_type=error_type,
                    next_attempt_at=None,
                )
                await notify_job(db.get_job(job_id), "failure")
        finally:
            runtime_state.clear_job_progress(job_id)


class AuthorCrawlWorker:
    def __init__(self):
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._thread_main, name="clipnest-author-crawl-worker", daemon=True)
        self._thread.start()

    async def stop(self) -> None:
        self.request_stop()
        if self._thread and self._thread.is_alive():
            await asyncio.to_thread(self._thread.join, 10)

    def request_stop(self) -> None:
        self._stop.set()

    async def run_forever(self) -> None:
        if self._thread and self._thread.is_alive():
            raise RuntimeError("Author crawl worker thread is already running")
        self._stop.clear()
        await self._run()

    def _thread_main(self) -> None:
        asyncio.run(self._run())

    async def _run(self) -> None:
        while not self._stop.is_set():
            job = db.claim_next_author_crawl_job()
            if not job:
                await asyncio.sleep(settings.poll_interval_seconds)
                continue
            await self._process(job)

    async def _process(self, job: dict):
        crawl_id = int(job["id"])
        quality = db.normalize_quality_preference(job.get("quality_preference"))
        max_items = max(1, min(1000, int(job.get("max_items") or 200)))
        max_pages = max(1, min(100, int(job.get("max_pages") or 30)))
        delay_ms = max(0, min(5000, int(job.get("delay_ms") or 0)))
        pages = int(job.get("pages_scanned") or 0)
        found = int(job.get("found_count") or 0)
        created = int(job.get("created_count") or 0)
        reused = int(job.get("reused_count") or 0)
        cursor = int(job.get("cursor") or 0)
        seen: set[str] = set()

        async def should_stop_or_pause() -> str:
            if self._stop.is_set():
                return "cancelling"
            return db.author_crawl_status(crawl_id)

        def progress() -> float:
            return round(min(99, max(1, (found / max_items) * 100)), 2)

        try:
            parser_settings = db.get_parser_settings(include_secret=True)
            crawler = NativeDouyinParserAdapter(parser_settings=parser_settings)
            sec_uid = str(job.get("sec_uid") or "")
            if not sec_uid:
                db.update_author_crawl_job(crawl_id, message="正在解析作者主页", progress=1)
                sec_uid = await crawler.resolve_sec_uid(str(job.get("url") or ""))
                db.update_author_crawl_job(crawl_id, sec_uid=sec_uid)

            has_more = True
            while has_more and pages < max_pages and found < max_items:
                status = await should_stop_or_pause()
                if status in {"cancelling", "cancelled"}:
                    db.update_author_crawl_job(
                        crawl_id,
                        status="cancelled",
                        progress=100,
                        message="已取消",
                        finished_at=db.utc_now(),
                    )
                    return
                if status in {"pausing", "paused"}:
                    db.update_author_crawl_job(crawl_id, status="paused", message="已暂停", progress=progress())
                    return

                previous_cursor = cursor
                db.update_author_crawl_job(
                    crawl_id,
                    status="running",
                    progress=progress(),
                    message=f"正在抓取第 {pages + 1} 页",
                )
                page = await crawler.fetch_author_post_page(sec_uid, max_cursor=cursor, count=18)
                pages += 1
                page_items = crawler.author_items_from_page(page, sec_uid)
                for item in page_items:
                    aweme_id = str(item.get("aweme_id") or "").strip()
                    if not aweme_id or aweme_id in seen:
                        continue
                    seen.add(aweme_id)
                    found += 1
                    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
                    platform = str(metadata.get("platform") or "douyin")
                    video_id = str(metadata.get("video_id") or aweme_id)
                    existing = db.find_existing_video_job(platform, video_id, quality_preference=quality)
                    if existing:
                        reused += 1
                    else:
                        db.create_job(str(item.get("url") or ""), quality_preference=quality, metadata=metadata)
                        created += 1
                    if found >= max_items:
                        break

                has_more = bool(page.get("has_more"))
                try:
                    cursor = int(page.get("max_cursor") or page.get("cursor") or 0)
                except (TypeError, ValueError):
                    cursor = 0
                db.update_author_crawl_job(
                    crawl_id,
                    cursor=cursor,
                    pages_scanned=pages,
                    found_count=found,
                    created_count=created,
                    reused_count=reused,
                    progress=progress(),
                    message=f"已发现 {found} 个，新建 {created} 个，已存在 {reused} 个",
                )
                if has_more and cursor == previous_cursor and not page_items:
                    raise RuntimeError("Author page did not advance cursor")
                if has_more and pages < max_pages and found < max_items and delay_ms:
                    await asyncio.sleep(delay_ms / 1000)

            limit_reached = bool(has_more and (pages >= max_pages or found >= max_items))
            db.update_author_crawl_job(
                crawl_id,
                status="finished",
                progress=100,
                message=(
                    f"已完成，还有更多作品：发现 {found} 个，新建 {created} 个，已存在 {reused} 个"
                    if limit_reached
                    else f"已完成：发现 {found} 个，新建 {created} 个，已存在 {reused} 个"
                ),
                cursor=cursor,
                pages_scanned=pages,
                found_count=found,
                created_count=created,
                reused_count=reused,
                error="",
                finished_at=db.utc_now(),
            )
        except Exception as exc:
            db.update_author_crawl_job(
                crawl_id,
                status="failed",
                progress=100,
                message="失败",
                error=f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=8)}",
                finished_at=db.utc_now(),
            )
