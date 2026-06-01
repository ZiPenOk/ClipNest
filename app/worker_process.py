import asyncio
from pathlib import Path
import signal

from . import db
from .config import settings
from .worker import AuthorCrawlWorker, DownloadWorker


def cleanup_partial_downloads() -> None:
    root = Path(settings.download_dir)
    if not root.exists():
        return
    for partial in root.rglob("*.part"):
        try:
            partial.unlink()
        except OSError:
            pass


async def main() -> None:
    db.init_db()
    Path(settings.download_dir).mkdir(parents=True, exist_ok=True)
    cleanup_partial_downloads()
    worker = DownloadWorker()
    author_worker = AuthorCrawlWorker()

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    worker_task = asyncio.create_task(worker.run_forever())
    author_worker_task = asyncio.create_task(author_worker.run_forever())
    stop_task = asyncio.create_task(stop_event.wait())
    try:
        done, pending = await asyncio.wait(
            {worker_task, author_worker_task, stop_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in done:
            task.result()
    finally:
        worker.request_stop()
        author_worker.request_stop()
        stop_task.cancel()
        for task in (worker_task, author_worker_task):
            if not task.done():
                await task


if __name__ == "__main__":
    asyncio.run(main())
