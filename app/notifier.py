from __future__ import annotations

from typing import Any

import httpx

from . import db


def enabled(settings: dict[str, Any], event: str) -> bool:
    if not settings.get("telegram_enabled"):
        return False
    if not settings.get("telegram_bot_token") or not settings.get("telegram_chat_id"):
        return False
    if event == "success" and not settings.get("telegram_notify_success", True):
        return False
    if event == "failure" and not settings.get("telegram_notify_failure", False):
        return False
    return True


def job_title(job: dict[str, Any]) -> str:
    return str(job.get("title") or job.get("description") or job.get("url") or f"#{job.get('id')}")


def fmt_bytes(value: Any) -> str:
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


def fmt_duration(value: Any) -> str:
    try:
        seconds = int(round(float(value or 0)))
    except (TypeError, ValueError):
        return "-"
    if seconds <= 0:
        return "-"
    minutes, sec = divmod(seconds, 60)
    hours, minute = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minute:02d}:{sec:02d}"
    return f"{minute}:{sec:02d}"


def telegram_text(job: dict[str, Any], event: str) -> str:
    if event == "success":
        quality = f"{job.get('resolution') or '-'} / {str(job.get('codec') or '-').upper()}"
        lines = [
            "✅ ClipNest 下载完成",
            "",
            f"🎬 标题：{job_title(job)}",
            f"👤 作者：{job.get('author_name') or 'Unknown'}",
            f"🎞️ 清晰度：{quality}",
        ]
        size = fmt_bytes(job.get("size_bytes"))
        duration = fmt_duration(job.get("duration_seconds"))
        if size != "-":
            lines.append(f"📦 大小：{size}")
        if duration != "-":
            lines.append(f"⏱️ 时长：{duration}")
        if job.get("file_path"):
            lines.extend(["", f"📁 文件：{job.get('file_path')}"])
        return "\n".join(lines)
    lines = [
        "❌ ClipNest 下载失败",
        "",
        f"🎬 标题：{job_title(job)}",
        f"👤 作者：{job.get('author_name') or 'Unknown'}",
        f"⚠️ 类型：{job.get('error_type') or 'unknown'}",
    ]
    error = str(job.get("error") or "").splitlines()[0][:260]
    if error:
        lines.append(f"🧯 错误：{error}")
    return "\n".join(lines)


async def send_telegram(settings: dict[str, Any], text: str) -> dict[str, Any]:
    token = str(settings.get("telegram_bot_token") or "").strip()
    chat_id = str(settings.get("telegram_chat_id") or "").strip()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(url, json={"chat_id": chat_id, "text": text})
    if response.status_code >= 400:
        description = response.text[:240]
        try:
            data = response.json()
            description = str(data.get("description") or description)[:240]
        except ValueError:
            pass
        raise RuntimeError(f"Telegram HTTP {response.status_code}: {description}")
    try:
        data = response.json()
    except ValueError:
        data = {"ok": True}
    return data if isinstance(data, dict) else {"ok": True}


async def notify_job(job: dict[str, Any] | None, event: str) -> None:
    if not job:
        return
    settings = db.get_app_settings()
    if not enabled(settings, event):
        return
    try:
        await send_telegram(settings, telegram_text(job, event))
        db.add_event(int(job["id"]), f"notify:telegram:{event}", "Telegram notification sent")
    except Exception as exc:
        db.add_event(int(job["id"]), "notify:telegram_failed", f"Telegram notification failed: {exc}", {"error": str(exc)})
