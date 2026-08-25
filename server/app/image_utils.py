from dataclasses import dataclass
from io import BytesIO

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from .errors import AppError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


@dataclass(frozen=True)
class DecodedImage:
    image: Image.Image
    original_format: str


def decode_image(data: bytes, max_dimension: int) -> DecodedImage:
    if not data:
        raise AppError("EMPTY_FILE", "请选择图片")

    try:
        with Image.open(BytesIO(data)) as source:
            source.verify()
        with Image.open(BytesIO(data)) as source:
            image_format = (source.format or "").upper()
            if image_format not in ALLOWED_FORMATS:
                raise AppError("UNSUPPORTED_IMAGE", "仅支持 JPG、PNG 和 WebP 图片")
            image = ImageOps.exif_transpose(source).convert("RGB")
    except AppError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise AppError("INVALID_IMAGE", "图片已损坏或格式不正确") from exc

    if max(image.size) > max_dimension:
        image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

    return DecodedImage(image=image.copy(), original_format=image_format)


def image_to_bgr(image: Image.Image) -> np.ndarray:
    rgb = np.asarray(image, dtype=np.uint8)
    return rgb[:, :, ::-1].copy()


def rgba_png(image: Image.Image, alpha: np.ndarray) -> bytes:
    alpha_image = Image.fromarray(alpha.astype(np.uint8))
    if alpha_image.size != image.size:
        alpha_image = alpha_image.resize(image.size, Image.Resampling.LANCZOS)
    rgba = image.convert("RGBA")
    rgba.putalpha(alpha_image)
    output = BytesIO()
    rgba.save(output, format="PNG", optimize=True)
    return output.getvalue()
