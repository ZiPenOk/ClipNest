from __future__ import annotations

import asyncio
import re
import threading
from typing import Any
from urllib.parse import urlsplit

import httpx

from . import db
from .notifier import send_telegram_message


URL_RE = re.compile(r"https?://\S+")
TRAILING_URL_PUNCTUATION = ".,;:!?)]}>，。；：！？）】》"
DOUYIN_HOST_RE = re.compile(r"(^|\.)((douyin|iesdouyin)\.com)$", re.I)
RUNNING_CRAWL_STATUSES = {"queued", "running", "paused", "pausing", "cancelling"}
STATUS_LABELS = {
    "queued": "排队中",
    "retry": "等待重试",
    "parsing": "解析中",
    "downloading": "下载中",
    "finished": "已完成",
    "failed": "失败",
    "cancelled": "已取消",
    "cancelling": "取消中",
}
CRAWL_STATUS_LABELS = {
    "queued": "排队中",
    "running": "抓取中",
    "paused": "已暂停",
    "pausing": "暂停中",
    "cancelling": "取消中",
    "cancelled": "已取消",
    "finished": "已完成",
    "failed": "失败",
}


def clean_url(value: str) -> str:
    return value.strip().rstrip(TRAILING_URL_PUNCTUATION)


def is_douyin_url(url: str) -> bool:
    try:
        host = urlsplit(url).hostname or ""
    except ValueError:
        return False
    return bool(DOUYIN_HOST_RE.search(host))


def is_author_url(url: str) -> bool:
    try:
        path = urlsplit(url).path
    except ValueError:
        return False
    return path.startswith("/user/") or path.startswith("/share/user/")


def extract_douyin_urls(text: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for candidate in URL_RE.findall(text or ""):
        url = clean_url(candidate)
        if url in seen or not is_douyin_url(url):
            continue
        urls.append(url)
        seen.add(url)
    return urls


def short_text(value: Any, limit: int = 56) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def job_title(job: dict[str, Any]) -> str:
    return short_text(job.get("title") or job.get("description") or job.get("url") or f"#{job.get('id')}")


def status_keyboard(job_id: int) -> dict[str, Any]:
    return {"inline_keyboard": [[{"text": "刷新状态", "callback_data": f"status:{job_id}"}]]}


def crawl_status_keyboard(crawl_id: int) -> dict[str, Any]:
    return {"inline_keyboard": [[{"text": "刷新作者抓取", "callback_data": f"crawl:{crawl_id}"}]]}


def job_status_text(job: dict[str, Any] | None) -> str:
    if not job:
        return "任务不存在或已被删除。"
    status = str(job.get("status") or "")
    progress = float(job.get("progress") or 0)
    lines = [
        f"任务 #{job.get('id')} · {STATUS_LABELS.get(status, status or '-')}",
        f"标题：{job_title(job)}",
    ]
    author = str(job.get("author_name") or "").strip()
    if author:
        lines.append(f"作者：{author}")
    if status in {"queued", "retry", "parsing", "downloading", "cancelling"}:
        lines.append(f"进度：{progress:.1f}%")
    if status == "finished":
        if job.get("resolution") or job.get("codec"):
            lines.append(f"清晰度：{job.get('resolution') or '-'} / {job.get('codec') or '-'}")
        if job.get("file_path"):
            lines.append(f"文件：{job.get('file_path')}")
    if status == "failed":
        error = str(job.get("error") or "").splitlines()[0][:220]
        if error:
            lines.append(f"错误：{error}")
    return "\n".join(lines)


def crawl_status_text(crawl: dict[str, Any] | None) -> str:
    if not crawl:
        return "作者抓取任务不存在或已被删除。"
    status = str(crawl.get("status") or "")
    lines = [
        f"作者抓取 #{crawl.get('id')} · {CRAWL_STATUS_LABELS.get(status, status or '-')}",
        f"进度：{float(crawl.get('progress') or 0):.1f}%",
        f"发现：{int(crawl.get('found_count') or 0)}",
        f"新建：{int(crawl.get('created_count') or 0)}",
        f"复用：{int(crawl.get('reused_count') or 0)}",
    ]
    message = str(crawl.get("message") or "").strip()
    if message:
        lines.append(f"状态：{message}")
    error = str(crawl.get("error") or "").strip()
    if error:
        lines.append(f"错误：{error.splitlines()[0][:220]}")
    return "\n".join(lines)


def active_jobs_text(limit: int = 8) -> str:
    jobs = db.list_jobs(limit=limit, status="active")
    crawls = [
        crawl
        for crawl in db.list_author_crawl_jobs(limit=limit)
        if str(crawl.get("status") or "") in RUNNING_CRAWL_STATUSES
    ]
    if not jobs and not crawls:
        return "当前没有排队、下载或作者抓取任务。"
    lines = ["当前任务："]
    for job in jobs:
        status = STATUS_LABELS.get(str(job.get("status") or ""), str(job.get("status") or "-"))
        progress = float(job.get("progress") or 0)
        lines.append(f"#{job.get('id')} · {status} · {progress:.1f}% · {job_title(job)}")
    for crawl in crawls:
        status = CRAWL_STATUS_LABELS.get(str(crawl.get("status") or ""), str(crawl.get("status") or "-"))
        progress = float(crawl.get("progress") or 0)
        lines.append(f"作者抓取 #{crawl.get('id')} · {status} · {progress:.1f}% · 发现 {int(crawl.get('found_count') or 0)}")
    return "\n".join(lines)


async def telegram_request(token: str, method: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"https://api.telegram.org/bot{token}/{method}"
    async with httpx.AsyncClient(timeout=httpx.Timeout(35, connect=10)) as client:
        response = await client.post(url, json=payload)
    if response.status_code >= 400:
        raise RuntimeError(f"Telegram {method} HTTP {response.status_code}: {response.text[:240]}")
    data = response.json()
    return data if isinstance(data, dict) else {"ok": True}


async def get_updates(token: str, offset: int | None, timeout: int) -> list[dict[str, Any]]:
    payload: dict[str, Any] = {"timeout": timeout, "allowed_updates": ["message", "callback_query"]}
    if offset is not None:
        payload["offset"] = offset
    data = await telegram_request(token, "getUpdates", payload)
    result = data.get("result") if isinstance(data, dict) else None
    return result if isinstance(result, list) else []


async def answer_callback(token: str, callback_id: str, text: str = "") -> None:
    payload = {"callback_query_id": callback_id}
    if text:
        payload["text"] = text
    await telegram_request(token, "answerCallbackQuery", payload)


async def edit_message(token: str, chat_id: str, message_id: int, text: str, reply_markup: dict[str, Any] | None = None) -> None:
    payload: dict[str, Any] = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    await telegram_request(token, "editMessageText", payload)


class TelegramBotWorker:
    def __init__(self):
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._thread_main, name="clipnest-telegram-bot", daemon=True)
        self._thread.start()

    async def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            await asyncio.to_thread(self._thread.join, 10)

    def _thread_main(self) -> None:
        asyncio.run(self._run())

    async def _run(self) -> None:
        offset: int | None = None
        token_seen = ""
        while not self._stop.is_set():
            app_settings = db.get_app_settings()
            token = str(app_settings.get("telegram_bot_token") or "").strip()
            enabled = bool(app_settings.get("telegram_enabled"))
            if not enabled or not token:
                offset = None
                token_seen = ""
                await asyncio.sleep(5)
                continue
            try:
                if token != token_seen:
                    offset = None
                    token_seen = token
                updates = await get_updates(token, offset, 25)
                for update in updates:
                    update_id = int(update.get("update_id") or 0)
                    offset = max(offset or 0, update_id + 1)
                    await self.handle_update(token, db.get_app_settings(), update)
            except Exception as exc:
                print(f"Telegram bot worker error: {exc}", flush=True)
                await asyncio.sleep(5)

    async def authorized(self, token: str, chat_id: str, app_settings: dict[str, Any]) -> bool:
        configured_chat = str(app_settings.get("telegram_chat_id") or "").strip()
        if not configured_chat:
            await send_telegram_message(
                token,
                chat_id,
                f"ClipNest 尚未配置 Telegram Chat ID。\n请把这个 Chat ID 填到设置里：{chat_id}",
            )
            return False
        if chat_id != configured_chat:
            await send_telegram_message(token, chat_id, f"此聊天未授权。\n当前 Chat ID：{chat_id}")
            return False
        return True

    async def handle_update(self, token: str, app_settings: dict[str, Any], update: dict[str, Any]) -> None:
        if isinstance(update.get("callback_query"), dict):
            await self.handle_callback(token, app_settings, update["callback_query"])
            return
        if isinstance(update.get("message"), dict):
            await self.handle_message(token, app_settings, update["message"])

    async def handle_callback(self, token: str, app_settings: dict[str, Any], callback: dict[str, Any]) -> None:
        message = callback.get("message") if isinstance(callback.get("message"), dict) else {}
        chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
        chat_id = str(chat.get("id") or "")
        if not chat_id or not await self.authorized(token, chat_id, app_settings):
            return
        data = str(callback.get("data") or "")
        callback_id = str(callback.get("id") or "")
        if data.startswith("status:"):
            try:
                job_id = int(data.split(":", 1)[1])
            except ValueError:
                await answer_callback(token, callback_id, "任务 ID 无效")
                return
            job = db.get_job(job_id)
            await edit_message(
                token,
                chat_id,
                int(message.get("message_id") or 0),
                job_status_text(job),
                status_keyboard(job_id) if job else None,
            )
            await answer_callback(token, callback_id, "已刷新")
            return
        if data.startswith("crawl:"):
            try:
                crawl_id = int(data.split(":", 1)[1])
            except ValueError:
                await answer_callback(token, callback_id, "作者抓取 ID 无效")
                return
            crawl = db.get_author_crawl_job(crawl_id)
            await edit_message(
                token,
                chat_id,
                int(message.get("message_id") or 0),
                crawl_status_text(crawl),
                crawl_status_keyboard(crawl_id) if crawl else None,
            )
            await answer_callback(token, callback_id, "已刷新")
            return
        await answer_callback(token, callback_id, "未知操作")

    async def send_received_messages(self, token: str, chat_id: str, message_id: int, urls: list[str]) -> None:
        for url in urls:
            kind = "作者主页链接" if is_author_url(url) else "下载链接"
            await send_telegram_message(
                token,
                chat_id,
                f"📥 ClipNest 已收到{kind}\n\n🔗 链接：{url}",
                reply_to_message_id=message_id,
            )

    async def send_created_messages(
        self,
        token: str,
        chat_id: str,
        message_id: int,
        jobs: list[dict[str, Any]],
        crawls: list[dict[str, Any]],
    ) -> None:
        for crawl in crawls:
            await send_telegram_message(
                token,
                chat_id,
                (
                    "🧾 ClipNest 作者抓取任务已创建\n\n"
                    f"🔗 链接：{crawl.get('url')}\n"
                    f"🧾 任务：作者抓取 #{crawl.get('id')}"
                ),
                reply_markup=crawl_status_keyboard(int(crawl["id"])),
                reply_to_message_id=message_id,
            )
        for job in jobs:
            reused = bool(job.get("reused"))
            title = "♻️ ClipNest 媒体库已存在" if reused else "🧾 ClipNest 下载任务已创建"
            await send_telegram_message(
                token,
                chat_id,
                (
                    f"{title}\n\n"
                    f"🔗 链接：{job.get('url')}\n"
                    f"🧾 任务：#{job.get('id')}"
                ),
                reply_markup=status_keyboard(int(job["id"])),
                reply_to_message_id=message_id,
            )

    async def handle_message(self, token: str, app_settings: dict[str, Any], message: dict[str, Any]) -> None:
        chat = message.get("chat") if isinstance(message.get("chat"), dict) else {}
        chat_id = str(chat.get("id") or "")
        if not chat_id or not await self.authorized(token, chat_id, app_settings):
            return
        text = str(message.get("text") or message.get("caption") or "").strip()
        message_id = int(message.get("message_id") or 0)
        if text.startswith("/start") or text.startswith("/help"):
            await send_telegram_message(
                token,
                chat_id,
                "把抖音作品链接或作者主页链接发给我，我会加入 ClipNest 队列。\n/status 查看当前任务。",
                reply_to_message_id=message_id,
            )
            return
        if text.startswith("/status"):
            await send_telegram_message(token, chat_id, active_jobs_text(), reply_to_message_id=message_id)
            return
        urls = extract_douyin_urls(text)
        if not urls:
            await send_telegram_message(
                token,
                chat_id,
                "没有识别到抖音链接。\n直接发送作品链接/作者主页链接，或发送 /status 查看队列。",
                reply_to_message_id=message_id,
            )
            return

        await self.send_received_messages(token, chat_id, message_id, urls)
        author_urls = [url for url in urls if is_author_url(url)]
        video_urls = [url for url in urls if not is_author_url(url)]
        crawls = [
            db.create_author_crawl_job(
                url,
                max_items=200,
                max_pages=30,
                delay_ms=600,
                quality_preference="best",
            )
            for url in author_urls
        ]
        jobs = [db.create_job_or_reuse_finished(url, quality_preference="best") for url in video_urls]
        for job in jobs:
            db.add_event(int(job["id"]), "telegram:enqueue", "Queued from Telegram", {"chat_id": chat_id})
        for crawl in crawls:
            db.update_author_crawl_job(int(crawl["id"]), message="来自 Telegram 的作者抓取")
        await self.send_created_messages(token, chat_id, message_id, jobs, crawls)
