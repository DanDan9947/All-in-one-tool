from __future__ import annotations

import os
import secrets
import shutil
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import BinaryIO


class RecordingNotFoundError(Exception):
    pass


class RecordingSequenceError(Exception):
    def __init__(self, expected: int) -> None:
        super().__init__(f"Expected chunk sequence {expected}")
        self.expected = expected


@dataclass
class RecordingSession:
    recording_id: str
    path: Path
    mime_type: str
    handle: BinaryIO
    next_sequence: int
    size_bytes: int
    last_activity: datetime


@dataclass(frozen=True)
class RecordingArtifact:
    token: str
    path: Path
    file_name: str
    mime_type: str
    size_bytes: int
    expires_at: datetime


@dataclass(frozen=True)
class FinishedRecording:
    path: Path
    mime_type: str
    size_bytes: int


class ScreenRecordingStore:
    def __init__(
        self,
        root: Path,
        abandoned_ttl_seconds: int,
        result_ttl_seconds: int,
    ) -> None:
        self.root = root.resolve()
        self.abandoned_ttl_seconds = abandoned_ttl_seconds
        self.result_ttl_seconds = result_ttl_seconds
        self._sessions: dict[str, RecordingSession] = {}
        self._artifacts: dict[str, RecordingArtifact] = {}
        self._lock = threading.RLock()

    def initialize(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for child in self.root.iterdir():
            if not child.name.startswith(("recording-", "transcode-", "result-")):
                continue
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)

    def create(self, mime_type: str) -> RecordingSession:
        now = datetime.now(timezone.utc)
        with self._lock:
            for _ in range(10):
                recording_id = secrets.token_urlsafe(24)
                path = self.root / f"recording-{recording_id}.webm"
                try:
                    handle = path.open("xb")
                except FileExistsError:
                    continue
                session = RecordingSession(
                    recording_id=recording_id,
                    path=path,
                    mime_type=mime_type,
                    handle=handle,
                    next_sequence=0,
                    size_bytes=0,
                    last_activity=now,
                )
                self._sessions[recording_id] = session
                return session
        raise RuntimeError("Unable to allocate screen recording file")

    def append(self, recording_id: str, sequence: int, data: bytes) -> RecordingSession:
        with self._lock:
            session = self._sessions.get(recording_id)
            if session is None:
                raise RecordingNotFoundError(recording_id)
            if sequence == session.next_sequence - 1:
                session.last_activity = datetime.now(timezone.utc)
                return session
            if sequence != session.next_sequence:
                raise RecordingSequenceError(session.next_sequence)
            try:
                session.handle.write(data)
                session.handle.flush()
            except OSError:
                self._discard_session_locked(recording_id)
                raise
            session.next_sequence += 1
            session.size_bytes += len(data)
            session.last_activity = datetime.now(timezone.utc)
            return session

    def finish_input(self, recording_id: str) -> FinishedRecording:
        with self._lock:
            session = self._sessions.pop(recording_id, None)
            if session is None:
                raise RecordingNotFoundError(recording_id)
            session.handle.close()
            if session.size_bytes == 0:
                session.path.unlink(missing_ok=True)
                raise ValueError("Recording contains no data")

            return FinishedRecording(
                path=session.path,
                mime_type=session.mime_type,
                size_bytes=session.size_bytes,
            )

    def create_transcode_path(self) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root / f"transcode-{secrets.token_urlsafe(24)}.mp4"

    def publish_mp4(self, source: Path, file_name: str) -> RecordingArtifact:
        with self._lock:
            token = secrets.token_urlsafe(32)
            destination = self.root / f"result-{token}.mp4"
            os.replace(source, destination)
            now = datetime.now(timezone.utc)
            artifact = RecordingArtifact(
                token=token,
                path=destination,
                file_name=safe_recording_name(file_name),
                mime_type="video/mp4",
                size_bytes=destination.stat().st_size,
                expires_at=now + timedelta(seconds=self.result_ttl_seconds),
            )
            self._artifacts[token] = artifact
            return artifact

    def cancel(self, recording_id: str) -> bool:
        with self._lock:
            return self._discard_session_locked(recording_id)

    def get_artifact(self, token: str) -> RecordingArtifact | None:
        with self._lock:
            artifact = self._artifacts.get(token)
            if artifact is None:
                return None
            if artifact.expires_at <= datetime.now(timezone.utc) or not artifact.path.is_file():
                self._artifacts.pop(token, None)
                artifact.path.unlink(missing_ok=True)
                return None
            return artifact

    def delete_artifact(self, token: str) -> None:
        with self._lock:
            artifact = self._artifacts.pop(token, None)
        if artifact is not None:
            artifact.path.unlink(missing_ok=True)

    def cleanup_expired(self) -> None:
        now = datetime.now(timezone.utc)
        abandoned_cutoff = now - timedelta(seconds=self.abandoned_ttl_seconds)
        with self._lock:
            abandoned = [
                recording_id
                for recording_id, session in self._sessions.items()
                if session.last_activity <= abandoned_cutoff
            ]
            for recording_id in abandoned:
                self._discard_session_locked(recording_id)

            expired = [
                token
                for token, artifact in self._artifacts.items()
                if artifact.expires_at <= now or not artifact.path.is_file()
            ]
            artifacts = [self._artifacts.pop(token) for token in expired]
        for artifact in artifacts:
            artifact.path.unlink(missing_ok=True)

    def clear(self) -> None:
        with self._lock:
            recording_ids = list(self._sessions)
            for recording_id in recording_ids:
                self._discard_session_locked(recording_id)
            artifacts = list(self._artifacts.values())
            self._artifacts.clear()
        for artifact in artifacts:
            artifact.path.unlink(missing_ok=True)
        for child in self.root.glob(("recording-*")):
            child.unlink(missing_ok=True)
        for child in self.root.glob(("transcode-*")):
            child.unlink(missing_ok=True)
        for child in self.root.glob(("result-*")):
            child.unlink(missing_ok=True)

    def _discard_session_locked(self, recording_id: str) -> bool:
        session = self._sessions.pop(recording_id, None)
        if session is None:
            return False
        try:
            session.handle.close()
        finally:
            session.path.unlink(missing_ok=True)
        return True


def safe_recording_name(file_name: str) -> str:
    candidate = Path(file_name or "screen-recording.mp4").name
    stem = candidate.removesuffix(".mp4").strip(" .")
    forbidden = '<>:"/\\|?*'
    stem = "".join("_" if character in forbidden or ord(character) < 32 else character for character in stem)
    return f"{(stem or 'screen-recording')[:100]}.mp4"
