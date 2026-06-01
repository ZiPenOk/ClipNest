import os
import signal
import subprocess
import sys
import time


def terminate_processes(processes: dict[str, subprocess.Popen]) -> None:
    for process in processes.values():
        if process.poll() is None:
            process.terminate()

    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if all(process.poll() is not None for process in processes.values()):
            return
        time.sleep(0.2)

    for process in processes.values():
        if process.poll() is None:
            process.kill()


def main() -> int:
    host = os.getenv("CLIPNEST_HOST", "0.0.0.0")
    port = os.getenv("CLIPNEST_INTERNAL_PORT", "8080")

    web_env = os.environ.copy()
    web_env["CLIPNEST_WORKER_ENABLED"] = "false"

    worker_env = os.environ.copy()
    worker_env["CLIPNEST_WORKER_ENABLED"] = "true"

    processes = {
        "worker": subprocess.Popen([sys.executable, "-m", "app.worker_process"], env=worker_env),
        "web": subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                host,
                "--port",
                port,
                "--no-access-log",
            ],
            env=web_env,
        ),
    }
    stopping = {"requested": False}

    def request_stop(signum, _frame):
        print(f"Received signal {signum}, stopping ClipNest", flush=True)
        stopping["requested"] = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    while True:
        if stopping["requested"]:
            terminate_processes(processes)
            return 0

        for name, process in processes.items():
            return_code = process.poll()
            if return_code is None:
                continue
            print(f"{name} process exited with code {return_code}", file=sys.stderr, flush=True)
            terminate_processes(processes)
            return return_code or 1

        time.sleep(0.5)


if __name__ == "__main__":
    raise SystemExit(main())
