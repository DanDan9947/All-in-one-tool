import hashlib
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from ..errors import AppError
from ..image_utils import rgba_png


class CutoutService:
    def __init__(
        self,
        model_path: Path,
        expected_sha256: str = "",
        inference_max_dimension: int = 1024,
    ) -> None:
        self.model_path = model_path
        self.expected_sha256 = expected_sha256.strip().lower()
        self.inference_max_dimension = max(32, inference_max_dimension)
        self._session: Any = None
        self._input_name = ""
        self.error: str | None = None

    @property
    def ready(self) -> bool:
        return self._session is not None

    def load(self) -> None:
        if self.ready:
            return
        if not self.model_path.is_file():
            self.error = "MODEL_NOT_FOUND"
            return
        if self.expected_sha256:
            digest = hashlib.sha256(self.model_path.read_bytes()).hexdigest()
            if digest != self.expected_sha256:
                self.error = "MODEL_HASH_MISMATCH"
                return
        try:
            import onnxruntime as ort

            self._session = ort.InferenceSession(
                str(self.model_path), providers=["CPUExecutionProvider"]
            )
            self._input_name = self._session.get_inputs()[0].name
            self.error = None
        except Exception as exc:
            self.error = type(exc).__name__

    def remove_background(self, image: Image.Image) -> bytes:
        if not self.ready:
            raise AppError("CUTOUT_UNAVAILABLE", "人像抠图模型尚未就绪", 503)
        try:
            tensor, crop = self._prepare_input(image)
            tensor = (tensor - 0.5) / 0.5
            tensor = np.transpose(tensor, (2, 0, 1))[None, ...]
            output = self._session.run(None, {self._input_name: tensor})[0]
            matte = np.squeeze(output).astype(np.float32)
            left, top, width, height = crop
            matte = matte[top : top + height, left : left + width]
            matte = np.clip(matte, 0.0, 1.0)
            alpha = (matte * 255.0).round().astype(np.uint8)
            return rgba_png(image, alpha)
        except AppError:
            raise
        except Exception as exc:
            raise AppError("CUTOUT_FAILED", "人像抠图失败，请更换图片重试", 500) from exc

    def _prepare_input(
        self, image: Image.Image
    ) -> tuple[np.ndarray, tuple[int, int, int, int]]:
        width, height = image.size
        scale = min(1.0, self.inference_max_dimension / max(width, height))
        resized_width = max(1, round(width * scale))
        resized_height = max(1, round(height * scale))
        resized = image.resize(
            (resized_width, resized_height), Image.Resampling.LANCZOS
        )

        padded_width = max(32, math.ceil(resized_width / 32) * 32)
        padded_height = max(32, math.ceil(resized_height / 32) * 32)
        left = (padded_width - resized_width) // 2
        right = padded_width - resized_width - left
        top = (padded_height - resized_height) // 2
        bottom = padded_height - resized_height - top

        pixels = np.asarray(resized, dtype=np.float32) / 255.0
        if left or right or top or bottom:
            pixels = np.pad(
                pixels,
                ((top, bottom), (left, right), (0, 0)),
                mode="edge",
            )
        return pixels, (left, top, resized_width, resized_height)
