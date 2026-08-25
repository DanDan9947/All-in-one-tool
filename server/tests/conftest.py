from io import BytesIO
from pathlib import Path
import shutil
import sys
import uuid

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from reportlab.pdfgen import canvas

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402


class FakeOcrService:
    ready = True

    def recognize(self, image):
        return [{"text": "测试文字", "score": 0.99}]


class FakeCutoutService:
    ready = True

    def remove_background(self, image):
        output = BytesIO()
        image.convert("RGBA").save(output, "PNG")
        return output.getvalue()


class FakePdfConversionRunner:
    ready = True

    def run(self, input_path, output_path, output_format):
        output_path.write_bytes(f"converted-{output_format}".encode())


class FakeScreenRecordingTranscoder:
    ready = True

    def convert(self, input_path, output_path):
        output_path.write_bytes(input_path.read_bytes())


@pytest.fixture
def png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (80, 60), "white").save(output, "PNG")
    return output.getvalue()


@pytest.fixture
def pdf_bytes() -> bytes:
    output = BytesIO()
    document = canvas.Canvas(output)
    document.drawString(72, 720, "Editable PDF text")
    document.save()
    return output.getvalue()


@pytest.fixture
def work_dir():
    path = Path("tmp") / "tests" / str(uuid.uuid4())
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def client(work_dir, monkeypatch):
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "pdf_temp_dir", work_dir / "conversions")
    monkeypatch.setattr(settings, "screen_recording_temp_dir", work_dir / "recordings")
    monkeypatch.setattr(settings, "video_compression_temp_dir", work_dir / "video-compressions")
    with TestClient(app) as test_client:
        app.state.ocr_service = FakeOcrService()
        app.state.cutout_service = FakeCutoutService()
        app.state.pdf_conversion_runner = FakePdfConversionRunner()
        app.state.screen_recording_transcoder = FakeScreenRecordingTranscoder()
        yield test_client
