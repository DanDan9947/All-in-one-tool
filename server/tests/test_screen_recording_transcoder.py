from pathlib import Path
import subprocess

import pytest

from app.services.screen_recording_transcoder import (
    RecordingTranscodeError,
    RecordingTranscodeTimeoutError,
    ScreenRecordingTranscoder,
)


def test_transcoder_builds_h264_aac_mp4_command(monkeypatch, work_dir):
    source = work_dir / "input.webm"
    output = work_dir / "output.mp4"
    source.write_bytes(b"webm")
    commands = []

    monkeypatch.setattr(
        ScreenRecordingTranscoder,
        "executable",
        property(lambda self: "ffmpeg.exe"),
    )

    def run(command, **kwargs):
        commands.append(command)
        output.write_bytes(b"mp4")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", run)
    ScreenRecordingTranscoder(timeout_seconds=30).convert(source, output)
    command = commands[0]
    assert ["-c:v", "libx264"] == command[command.index("-c:v") : command.index("-c:v") + 2]
    assert ["-c:a", "aac"] == command[command.index("-c:a") : command.index("-c:a") + 2]
    video_filter = command[command.index("-vf") + 1]
    assert "drawbox=" in video_filter
    assert "drawtext=" in video_filter
    assert "pts\\:hms" in video_filter
    assert "+faststart" in command


def test_transcoder_rejects_empty_output(monkeypatch, work_dir):
    source = work_dir / "input.webm"
    output = work_dir / "output.mp4"
    source.write_bytes(b"webm")
    monkeypatch.setattr(
        ScreenRecordingTranscoder,
        "executable",
        property(lambda self: "ffmpeg.exe"),
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "", ""),
    )
    with pytest.raises(RecordingTranscodeError):
        ScreenRecordingTranscoder(timeout_seconds=30).convert(source, output)


def test_transcoder_maps_timeout(monkeypatch, work_dir):
    source = work_dir / "input.webm"
    output = work_dir / "output.mp4"
    source.write_bytes(b"webm")
    monkeypatch.setattr(
        ScreenRecordingTranscoder,
        "executable",
        property(lambda self: "ffmpeg.exe"),
    )

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 30)

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(RecordingTranscodeTimeoutError):
        ScreenRecordingTranscoder(timeout_seconds=30).convert(source, output)
