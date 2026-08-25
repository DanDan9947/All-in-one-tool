"""Local development entry point.

Right-click this file in PyCharm and select Run to start the API.
"""

import os
import signal
import subprocess
import sys
from pathlib import Path

import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.app.config import get_settings  # noqa: E402


def _listening_pids_on_port(port: int) -> set[int]:
    """Return Windows PIDs listening on the configured TCP port."""
    if os.name != "nt":
        return set()

    result = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"],
        capture_output=True,
        text=True,
        encoding="gbk",
        errors="ignore",
        check=False,
    )
    if result.returncode != 0:
        return set()

    pids: set[int] = set()
    current_pid = os.getpid()
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0].upper() != "TCP":
            continue
        local_address, state, pid_text = parts[1], parts[3].upper(), parts[4]
        if state != "LISTENING":
            continue
        if not local_address.rsplit(":", 1)[-1] == str(port):
            continue
        try:
            pid = int(pid_text)
        except ValueError:
            continue
        if pid != current_pid:
            pids.add(pid)
    return pids


def _clear_port(port: int) -> None:
    pids = _listening_pids_on_port(port)
    if not pids:
        return

    for pid in sorted(pids):
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                capture_output=True,
                text=True,
                check=False,
            )
    print(f"Cleared port {port}: stopped PID(s) {', '.join(map(str, sorted(pids)))}")


def main() -> None:
    os.chdir(PROJECT_ROOT)
    settings = get_settings()
    _clear_port(settings.app_port)
    reload_enabled = os.getenv("UVICORN_RELOAD", "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    uvicorn.run(
        "server.app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=reload_enabled,
        reload_dirs=[str(PROJECT_ROOT / "server")] if reload_enabled else None,
    )


if __name__ == "__main__":
    main()
