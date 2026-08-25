from functools import lru_cache
from pathlib import Path
import tempfile

from pydantic_settings import BaseSettings, SettingsConfigDict


RESOURCE_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    max_upload_mb: int = 10
    image_compression_max_upload_mb: int = 50
    excel_max_upload_mb: int = 50
    image_compression_max_dimension: int = 16000
    max_image_dimension: int = 2048
    inference_concurrency: int = 2
    inference_wait_seconds: float = 0.1
    cutout_inference_max_dimension: int = 1024
    pdf_max_pages: int = 30
    pdf_result_ttl_seconds: int = 30
    pdf_conversion_concurrency: int = 1
    pdf_conversion_wait_seconds: float = 1.0
    pdf_conversion_timeout_seconds: float = 120.0
    pdf_temp_dir: Path = Path(tempfile.gettempdir()) / "wechat-pdf-conversions"
    screen_recording_temp_dir: Path = (
        Path(tempfile.gettempdir()) / "wechat-image-tools" / "recordings"
    )
    screen_recording_abandoned_ttl_seconds: int = 900
    screen_recording_result_ttl_seconds: int = 900
    screen_recording_max_chunk_mb: int = 32
    screen_recording_conversion_timeout_seconds: float = 3600.0
    screen_recording_conversion_wait_seconds: float = 5.0
    video_compression_temp_dir: Path = (
        Path(tempfile.gettempdir()) / "wechat-image-tools" / "video-compressions"
    )
    video_compression_online_max_upload_mb: int = 500
    video_compression_desktop_max_upload_mb: int = 2048
    video_compression_result_ttl_seconds: int = 900
    video_compression_timeout_seconds: float = 14400.0
    ocr_font_path: Path | None = None
    modnet_model_path: Path = RESOURCE_ROOT / "server/models/modnet_photographic.onnx"
    modnet_model_sha256: str = ""
    web_dist_path: Path = RESOURCE_ROOT / "web/dist"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def screen_recording_max_chunk_bytes(self) -> int:
        return self.screen_recording_max_chunk_mb * 1024 * 1024

    @property
    def image_compression_max_upload_bytes(self) -> int:
        return self.image_compression_max_upload_mb * 1024 * 1024

    @property
    def video_compression_max_upload_bytes(self) -> int:
        limit_mb = (
            self.video_compression_desktop_max_upload_mb
            if self.app_env == "desktop"
            else self.video_compression_online_max_upload_mb
        )
        return limit_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
