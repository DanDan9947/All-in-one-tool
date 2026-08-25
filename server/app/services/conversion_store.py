from __future__ import annotations

import os
import re
import secrets
import shutil
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass(frozen=True)
class ConversionArtifact:
    token: str
    path: Path
    file_name: str
    output_format: str
    media_type: str
    expires_at: datetime


class ConversionResultStore:
    _OUTPUT_MEDIA_TYPES = {
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }

    def __init__(self, root: Path, ttl_seconds: int) -> None:
        self.root = root.resolve()
        self.ttl_seconds = ttl_seconds
        self._artifacts: dict[str, ConversionArtifact] = {}
        self._lock = threading.Lock()

    def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for child in self.root.iterdir():
            if not child.name.startswith(("job-", "result-")):
                continue
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)

    def create_job_dir(self) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        for _ in range(10):
            job_dir = self.root / f"job-{secrets.token_urlsafe(12)}"
            try:
                job_dir.mkdir()
                return job_dir
            except FileExistsError:
                continue
        raise RuntimeError("Unable to allocate PDF conversion work directory")

    def publish(
        self, source: Path, original_name: str, output_format: str
    ) -> ConversionArtifact:
        token = secrets.token_urlsafe(32)
        destination = self.root / f"result-{token}.{output_format}"
        os.replace(source, destination)
        now = datetime.now(timezone.utc)
        artifact = ConversionArtifact(
            token=token,
            path=destination,
            file_name=f"{safe_file_stem(original_name)}.{output_format}",
            output_format=output_format,
            media_type=self._OUTPUT_MEDIA_TYPES[output_format],
            expires_at=now + timedelta(seconds=self.ttl_seconds),
        )
        with self._lock:
            self._artifacts[token] = artifact
        return artifact

    def get(self, token: str) -> ConversionArtifact | None:
        with self._lock:
            artifact = self._artifacts.get(token)
            if artifact is None:
                return None
            if artifact.expires_at <= datetime.now(timezone.utc) or not artifact.path.is_file():
                self._artifacts.pop(token, None)
                artifact.path.unlink(missing_ok=True)
                return None
            return artifact

    def cleanup_expired(self) -> None:
        now = datetime.now(timezone.utc)
        with self._lock:
            expired = [
                token
                for token, artifact in self._artifacts.items()
                if artifact.expires_at <= now or not artifact.path.is_file()
            ]
            artifacts = [self._artifacts.pop(token) for token in expired]
        for artifact in artifacts:
            artifact.path.unlink(missing_ok=True)

        cutoff = now.timestamp() - self.ttl_seconds
        for child in self.root.glob("result-*"):
            try:
                if child.stat().st_mtime <= cutoff:
                    child.unlink(missing_ok=True)
            except OSError:
                continue

    def clear(self) -> None:
        with self._lock:
            artifacts = list(self._artifacts.values())
            self._artifacts.clear()
        for artifact in artifacts:
            artifact.path.unlink(missing_ok=True)
        for child in self.root.glob("job-*"):
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)


def safe_file_stem(file_name: str) -> str:
    stem = Path(file_name or "converted").stem.strip()
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", stem)
    stem = re.sub(r"\s+", " ", stem).strip(" .")
    return (stem or "converted")[:80]
