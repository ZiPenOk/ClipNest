import threading
import time
from typing import Any


RUNNING_STATUSES = {"queued", "retry", "parsing", "downloading", "cancelling"}
_LOCK = threading.Lock()
_JOB_PROGRESS: dict[int, dict[str, Any]] = {}


def set_job_progress(job_id: int, progress: float) -> None:
    with _LOCK:
        _JOB_PROGRESS[int(job_id)] = {
            "progress": round(float(progress), 2),
            "runtime_progress_at": time.time(),
        }


def clear_job_progress(job_id: int) -> None:
    with _LOCK:
        _JOB_PROGRESS.pop(int(job_id), None)


def overlay_job(job: dict[str, Any] | None) -> dict[str, Any] | None:
    if not job:
        return job
    job_id = int(job.get("id") or 0)
    status = str(job.get("status") or "")
    with _LOCK:
        progress = dict(_JOB_PROGRESS.get(job_id) or {})
    if not progress or status not in RUNNING_STATUSES:
        return job
    merged = dict(job)
    merged.update(progress)
    return merged


def overlay_jobs(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [overlay_job(job) or job for job in jobs]


def overlay_jobs_page(page: dict[str, Any]) -> dict[str, Any]:
    merged = dict(page)
    items = merged.get("items")
    if isinstance(items, list):
        merged["items"] = overlay_jobs(items)
    return merged
