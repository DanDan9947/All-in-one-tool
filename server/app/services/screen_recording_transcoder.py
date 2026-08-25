from __future__ import annotations

import os
import subprocess
from pathlib import Path


class RecordingTranscodeError(Exception):
    pass


class RecordingTranscodeTimeoutError(RecordingTranscodeError):
    pass


class ScreenRecordingTranscoder:
    def __init__(self, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds

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

    def convert(self, input_path: Path, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            self.executable,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(input_path),
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-vf",
            self._timer_filter(),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_seconds,
                creationflags=creation_flags,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            output_path.unlink(missing_ok=True)
            raise RecordingTranscodeTimeoutError("MP4 conversion timed out") from exc
        if completed.returncode != 0 or not output_path.is_file() or output_path.stat().st_size == 0:
            output_path.unlink(missing_ok=True)
            detail = (completed.stderr or completed.stdout or "unknown ffmpeg error").strip()
            raise RecordingTranscodeError(detail[-1000:])

    @staticmethod
    def _timer_filter() -> str:
        font_candidates = [
            Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "arial.ttf",
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ]
        font_path = next((path for path in font_candidates if path.is_file()), None)
        font_option = ""
        if font_path is not None:
            escaped_font = font_path.as_posix().replace(":", r"\:").replace("'", r"\'")
            font_option = f"fontfile='{escaped_font}':"
        return (
            "drawbox=x=w-268:y=24:w=244:h=62:color=black@0.68:t=fill,"
            "drawbox=x=w-250:y=47:w=15:h=15:color=red@0.95:t=fill,"
            f"drawtext={font_option}text='%{{pts\\:hms}}':"
            "fontcolor=white:fontsize=28:x=w-tw-34:y=39"
        )
