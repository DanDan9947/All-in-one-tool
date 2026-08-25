from __future__ import annotations

import ctypes
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

import pystray
import uvicorn
from PIL import Image


APP_NAME = "蛋蛋小工具"
APP_HOST = "127.0.0.1"
APP_PORT = 8765
APP_URL = f"http://{APP_HOST}:{APP_PORT}/"
HEALTH_URL = f"http://{APP_HOST}:{APP_PORT}/api/v1/health"
MUTEX_NAME = "Local\\WechatImageToolsDesktop-72B0A759"

_mutex_handle = None


def _message(text: str, error: bool = False) -> None:
    flags = 0x10 if error else 0x40
    ctypes.windll.user32.MessageBoxW(None, text, APP_NAME, flags)


def _acquire_single_instance() -> bool:
    global _mutex_handle
    if os.name != "nt":
        return True
    _mutex_handle = ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_NAME)
    return ctypes.windll.kernel32.GetLastError() != 183


def _health_ready(timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=timeout) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def _port_in_use() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.settimeout(0.3)
        return connection.connect_ex((APP_HOST, APP_PORT)) == 0


def _wait_and_open(timeout_seconds: int = 120) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if _health_ready():
            if os.getenv("WECHAT_TOOLS_NO_BROWSER") != "1":
                webbrowser.open(APP_URL)
            return True
        time.sleep(0.4)
    return False


def _tray_image() -> Image.Image:
    runtime_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    logo_path = runtime_root / "deploy" / "assets" / "dandan-logo.png"
    with Image.open(logo_path) as source:
        logo = source.convert("RGBA")
        logo.thumbnail((64, 64), Image.Resampling.LANCZOS)
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    image.alpha_composite(logo, ((64 - logo.width) // 2, (64 - logo.height) // 2))
    return image


def main() -> None:
    if not _acquire_single_instance():
        if not _wait_and_open():
            _message("蛋蛋小工具正在启动，请稍后重试。", error=True)
        return

    if _port_in_use():
        if _health_ready():
            webbrowser.open(APP_URL)
        else:
            _message(f"本机端口 {APP_PORT} 已被其他程序占用，蛋蛋小工具无法启动。", error=True)
        return

    os.environ.setdefault("APP_ENV", "desktop")
    os.environ.setdefault("APP_HOST", APP_HOST)
    os.environ.setdefault("APP_PORT", str(APP_PORT))
    os.environ.setdefault(
        "MODNET_MODEL_SHA256",
        "5069a5e306b9f5e9f4f2b0360264c9f8ea13b257c7c39943c7cf6a2ec3a102ae",
    )

    from server.app.config import get_settings

    get_settings.cache_clear()
    from server.app.main import app

    config = uvicorn.Config(
        app,
        host=APP_HOST,
        port=APP_PORT,
        log_config=None,
        log_level="warning",
        access_log=False,
        loop="asyncio",
        http="h11",
        ws="none",
    )
    server = uvicorn.Server(config)
    server.install_signal_handlers = lambda: None
    server_thread = threading.Thread(target=server.run, name="local-web-server", daemon=True)
    server_thread.start()

    icon = pystray.Icon(APP_NAME, _tray_image(), APP_NAME)

    def open_page(_icon=None, _item=None) -> None:
        webbrowser.open(APP_URL)

    def exit_app(tray_icon, _item=None) -> None:
        server.should_exit = True
        tray_icon.stop()

    icon.menu = pystray.Menu(
        pystray.MenuItem("打开页面", open_page, default=True),
        pystray.MenuItem("退出", exit_app),
    )

    def open_when_ready() -> None:
        if not _wait_and_open():
            _message("本地服务启动超时，请退出后重试。", error=True)

    threading.Thread(target=open_when_ready, name="browser-opener", daemon=True).start()
    try:
        icon.run()
    finally:
        server.should_exit = True
        server_thread.join(timeout=20)


if __name__ == "__main__":
    main()
