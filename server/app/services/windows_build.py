from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

from ..config import get_settings
from ..errors import AppError


class WindowsBuildManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._process: subprocess.Popen | None = None
        self._source_root: Path | None = None
        self._target_directory: Path | None = None

    async def start(
        self, authorization: str | None, target_directory: str | None = None
    ) -> dict:
        if os.name != "nt":
            raise AppError("WINDOWS_REQUIRED", "Windows 打包仅支持在 Windows 本机运行", 400)
        if not authorization:
            raise AppError("LOGIN_REQUIRED", "请先登录有打包权限的账号", 401)
        await asyncio.to_thread(self._verify_permission, authorization)

        source_root = self._find_source_root()
        helper = source_root / "deploy" / "run-windows-build.ps1"
        log_path = source_root / "logs" / "windows-build-latest.log"
        status_file = source_root / "logs" / "build-status.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        status_file.unlink(missing_ok=True)

        target_path = (
            Path(target_directory).resolve()
            if target_directory and target_directory.strip()
            else (source_root / "dist").resolve()
        )

        with self._lock:
            if self._process is not None and self._process.poll() is None:
                raise AppError("BUILD_RUNNING", "Windows 打包任务正在运行，请勿重复启动", 409)
            wait_for_pid = os.getpid() if getattr(sys, "frozen", False) else 0
            creation_flags = (
                getattr(subprocess, "CREATE_NO_WINDOW", 0)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            )
            self._process = subprocess.Popen(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(helper),
                    "-ProjectRoot",
                    str(source_root),
                    "-WaitForProcessId",
                    str(wait_for_pid),
                    "-TargetDirectory",
                    str(target_path),
                    "-RestartService",
                ],
                cwd=source_root,
                creationflags=creation_flags,
            )
            self._source_root = source_root
            self._target_directory = target_path

        return {
            "status": "waiting-for-exit" if wait_for_pid else "running",
            "requiresAppExit": bool(wait_for_pid),
            "logPath": str(log_path),
            "outputDirectory": str(target_path),
        }

    def status(self) -> dict:
        with self._lock:
            process = self._process
            source_root = self._source_root
            target_directory = self._target_directory
        if source_root is None:
            source_root = self._find_source_root_safe()
        if target_directory is None and source_root is not None:
            target_directory = source_root / "dist"

        if process is None:
            status_file = source_root / "logs" / "build-status.json" if source_root else None
            if status_file and status_file.is_file():
                try:
                    data = json.loads(status_file.read_text(encoding="utf-8-sig"))
                    # If updated in the last 15 minutes, report that status
                    if time.time() - status_file.stat().st_mtime < 900:
                        state = data.get("status", "idle")
                        exit_code = 0 if state == "completed" else 1
                        if data.get("targetDirectory"):
                            target_directory = Path(data["targetDirectory"])
                    else:
                        state = "idle"
                        exit_code = None
                except Exception:
                    state = "idle"
                    exit_code = None
            else:
                state = "idle"
                exit_code = None
        else:
            exit_code = process.poll()
            if exit_code is None:
                state = "running"
            elif exit_code == 0:
                state = "completed"
            else:
                state = "failed"

        artifacts = []
        search_dirs = []
        if target_directory and target_directory.is_dir():
            search_dirs.append(target_directory)
        if source_root and (source_root / "dist").is_dir() and (source_root / "dist") not in search_dirs:
            search_dirs.append(source_root / "dist")

        seen_names = set()
        for sdir in search_dirs:
            for filename in ["DandanTools-Setup.exe", "DandanTools-windows-x64.zip"]:
                if filename in seen_names:
                    continue
                filepath = sdir / filename
                if filepath.is_file():
                    stat = filepath.stat()
                    artifacts.append(
                        {
                            "name": filename,
                            "sizeBytes": stat.st_size,
                            "sizeMb": round(stat.st_size / (1024 * 1024), 2),
                            "modifiedAt": stat.st_mtime,
                        }
                    )
                    seen_names.add(filename)

        log_path = str(source_root / "logs" / "windows-build-latest.log") if source_root else ""
        return {
            "status": state,
            "exitCode": exit_code,
            "logPath": log_path,
            "outputDirectory": str(target_directory) if target_directory else "",
            "artifacts": artifacts,
        }

    def get_artifact_path(self, filename: str) -> Path | None:
        safe_name = Path(filename).name
        if safe_name != filename or not filename.endswith((".exe", ".zip")):
            return None
        source_root = self._source_root or self._find_source_root_safe()
        candidates: list[Path] = []
        if self._target_directory:
            candidates.append(self._target_directory / safe_name)
        if source_root:
            candidates.append(source_root / "dist" / safe_name)
        for cand in candidates:
            if cand.is_file():
                return cand
        return None

    def _find_source_root_safe(self) -> Path | None:
        try:
            return self._find_source_root()
        except Exception:
            return None

    def _verify_permission(self, authorization: str) -> None:
        settings = get_settings()
        endpoint = f"{settings.account_api_root.rstrip('/')}/c/user/permission/me"
        request = urllib.request.Request(
            endpoint,
            headers={
                "Authorization": authorization,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, ValueError) as exc:
            raise AppError("PERMISSION_SERVICE_UNAVAILABLE", "无法连接权限服务，请稍后重试", 503) from exc
        if not payload.get("success"):
            raise AppError("PERMISSION_DENIED", payload.get("message") or "没有 Windows 打包权限", 403)
        codes = (payload.get("data") or {}).get("permissionCodes") or []
        if settings.windows_build_permission_code not in codes:
            raise AppError("PERMISSION_DENIED", "当前账号没有 Windows 打包权限", 403)

    def _find_source_root(self) -> Path:
        explicit_root = os.getenv("DANDAN_SOURCE_ROOT")
        candidates: list[Path] = []
        if explicit_root:
            candidates.append(Path(explicit_root))
        candidates.extend([Path.cwd(), Path(sys.executable).resolve().parent])
        candidates.extend(Path(sys.executable).resolve().parents)
        candidates.extend(Path(__file__).resolve().parents)
        for candidate in candidates:
            if (candidate / "deploy" / "build-windows.ps1").is_file() and (
                candidate / "deploy" / "build-installer.ps1"
            ).is_file():
                return candidate.resolve()
        raise AppError(
            "SOURCE_ROOT_NOT_FOUND",
            "未找到项目源码目录，请设置 DANDAN_SOURCE_ROOT 后重试",
            400,
        )
