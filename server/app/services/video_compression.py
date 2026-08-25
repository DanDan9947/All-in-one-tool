from __future__ import annotations

import asyncio
import os
import re
import secrets
import shutil
import subprocess
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path


class VideoCompressionError(Exception):
    pass


@dataclass(frozen=True)
class VideoCompressionOptions:
    preset: str
    max_height: int | None = None
    crf: int | None = None
    target_size_mb: int | None = None


@dataclass
class VideoCompressionJob:
    job_id: str
    input_path: Path
    output_path: Path
    file_name: str
    options: VideoCompressionOptions
    status: str = "queued"
    progress: int = 0
    original_size: int = 0
    output_size: int = 0
    duration_seconds: float = 0
    token: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)
    process: subprocess.Popen[str] | None = field(default=None, repr=False)


PRESETS = {
    "small": (720, 30, "96k"),
    "balanced": (1080, 26, "128k"),
    "high": (None, 22, "160k"),
}


class VideoCompressionManager:
    def __init__(self, root: Path, ttl_seconds: int, timeout_seconds: float) -> None:
        self.root = root.resolve()
        self.ttl_seconds = ttl_seconds
        self.timeout_seconds = timeout_seconds
        self._jobs: dict[str, VideoCompressionJob] = {}
        self._tokens: dict[str, str] = {}
        self._tasks: set[asyncio.Task] = set()
        self._lock = threading.RLock()

    @property
    def executable(self) -> str:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()

    @property
    def ready(self) -> bool:
        try:
            return Path(self.executable).is_file()
        except Exception:
            return False

    def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for child in self.root.iterdir():
            if child.name.startswith(("upload-", "output-")):
                child.unlink(missing_ok=True)

    def allocate_upload(self, suffix: str) -> tuple[str, Path]:
        job_id = secrets.token_urlsafe(24)
        return job_id, self.root / f"upload-{job_id}{suffix}"

    def register(
        self,
        job_id: str,
        input_path: Path,
        file_name: str,
        options: VideoCompressionOptions,
    ) -> VideoCompressionJob:
        output_path = self.root / f"output-{job_id}.mp4"
        job = VideoCompressionJob(
            job_id=job_id,
            input_path=input_path,
            output_path=output_path,
            file_name=_safe_mp4_name(file_name),
            options=options,
            original_size=input_path.stat().st_size,
        )
        with self._lock:
            self._jobs[job_id] = job
        return job

    def start(self, job_id: str, semaphore: asyncio.Semaphore) -> None:
        task = asyncio.create_task(self._run(job_id, semaphore))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run(self, job_id: str, semaphore: asyncio.Semaphore) -> None:
        async with semaphore:
            job = self.get(job_id)
            if job is None or job.cancel_event.is_set():
                return
            job.status = "processing"
            try:
                await asyncio.to_thread(self._compress, job)
            except VideoCompressionError as exc:
                if job.cancel_event.is_set():
                    job.status = "cancelled"
                else:
                    job.status = "failed"
                    job.error_code = "VIDEO_COMPRESSION_FAILED"
                    job.error_message = str(exc) or "视频压缩失败"
                job.output_path.unlink(missing_ok=True)
            except OSError:
                job.status = "failed"
                job.error_code = "VIDEO_STORAGE_ERROR"
                job.error_message = "磁盘空间不足或无法写入临时文件"
                job.output_path.unlink(missing_ok=True)
            finally:
                job.input_path.unlink(missing_ok=True)

    def _compress(self, job: VideoCompressionJob) -> None:
        duration = self._probe_duration(job.input_path)
        job.duration_seconds = duration
        height, crf, audio_bitrate = _resolved_settings(job.options)
        command = [
            self.executable,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(job.input_path),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
        ]
        if height is not None:
            command += ["-vf", f"scale=-2:min({height}\\,ih)"]
        command += ["-c:v", "libx264", "-preset", "veryfast"]
        if job.options.target_size_mb:
            target_kbits = job.options.target_size_mb * 8192
            audio_kbps = int(audio_bitrate.removesuffix("k"))
            video_kbps = max(300, int(target_kbits / duration) - audio_kbps)
            command += ["-b:v", f"{video_kbps}k", "-maxrate", f"{video_kbps * 2}k"]
        else:
            command += ["-crf", str(crf)]
        command += [
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            audio_bitrate,
            "-movflags",
            "+faststart",
            "-progress",
            "pipe:1",
            "-nostats",
            str(job.output_path),
        ]
        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creation_flags,
        )
        job.process = process
        started = datetime.now(timezone.utc)
        assert process.stdout is not None
        for line in process.stdout:
            if job.cancel_event.is_set():
                process.kill()
                break
            if (datetime.now(timezone.utc) - started).total_seconds() > self.timeout_seconds:
                process.kill()
                raise VideoCompressionError("视频压缩超时")
            key, _, value = line.strip().partition("=")
            if key in {"out_time_us", "out_time_ms"} and value.isdigit():
                seconds = int(value) / 1_000_000
                job.progress = min(99, max(job.progress, int(seconds / duration * 100)))
        stderr = process.stderr.read() if process.stderr else ""
        return_code = process.wait()
        job.process = None
        if job.cancel_event.is_set():
            job.status = "cancelled"
            job.output_path.unlink(missing_ok=True)
            return
        if return_code != 0 or not job.output_path.is_file() or job.output_path.stat().st_size == 0:
            raise VideoCompressionError((stderr or "FFmpeg 无法处理该视频")[-800:])
        job.output_size = job.output_path.stat().st_size
        job.progress = 100
        job.status = "completed"
        job.token = secrets.token_urlsafe(32)
        job.expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.ttl_seconds)
        with self._lock:
            self._tokens[job.token] = job.job_id

    def _probe_duration(self, input_path: Path) -> float:
        completed = subprocess.run(
            [self.executable, "-hide_banner", "-i", str(input_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            check=False,
        )
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", completed.stderr)
        if not match:
            raise VideoCompressionError("无法读取视频时长，文件可能已损坏或不含视频轨道")
        duration = int(match[1]) * 3600 + int(match[2]) * 60 + float(match[3])
        if duration <= 0:
            raise VideoCompressionError("视频时长不正确")
        return duration

    def get(self, job_id: str) -> VideoCompressionJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def get_result(self, token: str) -> VideoCompressionJob | None:
        with self._lock:
            job_id = self._tokens.get(token)
            job = self._jobs.get(job_id) if job_id else None
        if job and job.expires_at and job.expires_at > datetime.now(timezone.utc):
            return job
        return None

    def cancel(self, job_id: str) -> bool:
        job = self.get(job_id)
        if job is None:
            return False
        job.cancel_event.set()
        if job.process and job.process.poll() is None:
            job.process.kill()
        job.status = "cancelled"
        job.input_path.unlink(missing_ok=True)
        job.output_path.unlink(missing_ok=True)
        return True

    def cleanup_expired(self) -> None:
        now = datetime.now(timezone.utc)
        with self._lock:
            expired = [
                job_id
                for job_id, job in self._jobs.items()
                if job.expires_at is not None and job.expires_at <= now
            ]
            jobs = [self._jobs.pop(job_id) for job_id in expired]
            for job in jobs:
                if job.token:
                    self._tokens.pop(job.token, None)
        for job in jobs:
            job.output_path.unlink(missing_ok=True)

    async def shutdown(self) -> None:
        for job_id in list(self._jobs):
            self.cancel(job_id)
        if self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)
        shutil.rmtree(self.root, ignore_errors=True)


def _resolved_settings(options: VideoCompressionOptions) -> tuple[int | None, int, str]:
    if options.preset not in {*PRESETS, "custom"}:
        raise VideoCompressionError("视频压缩预设不正确")
    height, crf, audio = PRESETS.get(options.preset, (None, 26, "128k"))
    if options.preset == "custom":
        height = options.max_height
        crf = options.crf or 26
    return height, crf, audio


def _safe_mp4_name(file_name: str) -> str:
    stem = Path(file_name or "compressed-video").stem.strip(" .")
    forbidden = '<>:"/\\|?*'
    stem = "".join("_" if character in forbidden else character for character in stem)
    return f"{(stem or 'compressed-video')[:100]}-compressed.mp4"
