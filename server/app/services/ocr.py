from pathlib import Path
from typing import Any

from ..errors import AppError
from ..image_utils import image_to_bgr


class OcrService:
    def __init__(self, font_path: Path | None = None) -> None:
        self._engine: Any = None
        self.font_path = font_path
        self.error: str | None = None

    @property
    def ready(self) -> bool:
        return self._engine is not None

    def load(self) -> None:
        if self.ready:
            return
        try:
            from rapidocr import RapidOCR

            font_path = self._resolve_font_path()
            self._engine = RapidOCR(params={"Global.font_path": str(font_path)})
            self.error = None
        except Exception as exc:  # model/package errors are reported by health endpoint
            self.error = type(exc).__name__

    def _resolve_font_path(self) -> Path:
        candidates = [
            self.font_path,
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("C:/Windows/Fonts/msyh.ttc"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ]
        for candidate in candidates:
            if candidate is not None and candidate.is_file():
                return candidate
        raise FileNotFoundError(
            "RapidOCR requires a local TTF/TTC font; set OCR_FONT_PATH"
        )

    def recognize(self, image) -> list[dict[str, float | str]]:
        if not self.ready:
            raise AppError("OCR_UNAVAILABLE", "文字识别模型尚未就绪", 503)
        try:
            result = self._engine(image_to_bgr(image))
            texts = getattr(result, "txts", None)
            scores = getattr(result, "scores", None)
            if texts is None and isinstance(result, tuple):
                rows = result[0] or []
                return [
                    {"text": str(row[1]), "score": round(float(row[2]), 4)}
                    for row in rows
                    if len(row) >= 3
                ]
            return [
                {"text": str(text), "score": round(float(score), 4)}
                for text, score in zip(texts or [], scores or [])
            ]
        except AppError:
            raise
        except Exception as exc:
            raise AppError("OCR_FAILED", "文字识别失败，请更换清晰图片重试", 500) from exc
