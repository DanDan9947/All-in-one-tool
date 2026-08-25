from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from ..errors import AppError


PRESETS = {
    "small": (1600, 60),
    "balanced": (2560, 75),
    "high": (None, 88),
}
OUTPUT_FORMATS = {"auto", "jpeg", "webp", "png"}


@dataclass(frozen=True)
class ImageCompressionResult:
    content: bytes
    output_format: str
    width: int
    height: int
    original_size: int
    skipped: bool
    target_reached: bool

    @property
    def media_type(self) -> str:
        return {
            "JPEG": "image/jpeg",
            "PNG": "image/png",
            "WEBP": "image/webp",
        }[self.output_format]

    @property
    def extension(self) -> str:
        return {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}[self.output_format]


def compress_image(
    data: bytes,
    *,
    preset: str,
    max_dimension: int | None,
    quality: int | None,
    target_bytes: int | None,
    output_format: str,
    absolute_max_dimension: int,
) -> ImageCompressionResult:
    if preset not in {*PRESETS, "custom"}:
        raise AppError("INVALID_COMPRESSION_PRESET", "图片压缩预设不正确", 422)
    output_format = output_format.lower()
    if output_format not in OUTPUT_FORMATS:
        raise AppError("INVALID_OUTPUT_FORMAT", "图片输出格式不正确", 422)
    if quality is not None and not 35 <= quality <= 95:
        raise AppError("INVALID_IMAGE_QUALITY", "图片质量必须在 35 到 95 之间", 422)
    if max_dimension is not None and not 320 <= max_dimension <= absolute_max_dimension:
        raise AppError(
            "INVALID_IMAGE_DIMENSION",
            f"图片最长边必须在 320 到 {absolute_max_dimension} 像素之间",
            422,
        )
    if target_bytes is not None and target_bytes < 16 * 1024:
        raise AppError("INVALID_TARGET_SIZE", "目标大小不能低于 16KB", 422)

    try:
        with Image.open(BytesIO(data)) as source:
            source.load()
            original_format = (source.format or "").upper()
            if original_format not in {"JPEG", "PNG", "WEBP"}:
                raise AppError("UNSUPPORTED_IMAGE", "仅支持 JPG、PNG 和 WebP 图片", 415)
            image = ImageOps.exif_transpose(source).copy()
    except AppError:
        raise
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise AppError("INVALID_IMAGE", "图片已损坏或格式不正确") from exc

    if max(image.size) > absolute_max_dimension:
        raise AppError(
            "IMAGE_DIMENSION_TOO_LARGE",
            f"图片最长边不能超过 {absolute_max_dimension} 像素",
            413,
        )

    preset_dimension, preset_quality = PRESETS.get(preset, (None, 75))
    requested_dimension = max_dimension if preset == "custom" else preset_dimension
    requested_quality = quality if quality is not None else preset_quality
    working = _resize_to_limit(image, requested_dimension)
    has_alpha = _has_transparency(working)
    selected_format = _select_format(output_format, has_alpha)

    encoded, selected_format = _encode_best(working, selected_format, requested_quality, has_alpha)
    target_reached = target_bytes is None or len(encoded) <= target_bytes
    if target_bytes is not None and not target_reached:
        encoded, selected_format, working, target_reached = _compress_to_target(
            working, selected_format, has_alpha, target_bytes
        )

    skipped = False
    if target_bytes is None and len(encoded) >= len(data):
        encoded = data
        selected_format = original_format
        skipped = True

    return ImageCompressionResult(
        content=encoded,
        output_format=selected_format,
        width=working.width if not skipped else image.width,
        height=working.height if not skipped else image.height,
        original_size=len(data),
        skipped=skipped,
        target_reached=target_reached,
    )


def _resize_to_limit(image: Image.Image, max_dimension: int | None) -> Image.Image:
    result = image.copy()
    if max_dimension is not None and max(result.size) > max_dimension:
        result.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
    return result


def _has_transparency(image: Image.Image) -> bool:
    if image.mode in {"RGBA", "LA"}:
        return image.getextrema()[-1][0] < 255
    return image.mode == "P" and "transparency" in image.info


def _select_format(requested: str, has_alpha: bool) -> str:
    if has_alpha:
        return "PNG"
    if requested == "auto":
        return "AUTO"
    return requested.upper().replace("JPG", "JPEG")


def _encode_best(
    image: Image.Image, output_format: str, quality: int, has_alpha: bool
) -> tuple[bytes, str]:
    if output_format == "AUTO":
        candidates = [
            (_encode(image, "JPEG", quality), "JPEG"),
            (_encode(image, "WEBP", quality), "WEBP"),
        ]
        return min(candidates, key=lambda item: len(item[0]))
    return _encode(image, output_format, quality, has_alpha), output_format


def _encode(
    image: Image.Image, output_format: str, quality: int, has_alpha: bool = False
) -> bytes:
    output = BytesIO()
    if output_format == "PNG":
        converted = image.convert("RGBA" if has_alpha else "RGB")
        converted.save(output, format="PNG", optimize=True, compress_level=9)
    elif output_format == "WEBP":
        image.convert("RGBA" if has_alpha else "RGB").save(
            output, format="WEBP", quality=quality, method=6
        )
    else:
        image.convert("RGB").save(
            output, format="JPEG", quality=quality, optimize=True, progressive=True
        )
    return output.getvalue()


def _compress_to_target(
    image: Image.Image,
    output_format: str,
    has_alpha: bool,
    target_bytes: int,
) -> tuple[bytes, str, Image.Image, bool]:
    working = image.copy()
    best = _encode_best(working, output_format, 35, has_alpha)
    while True:
        if output_format != "PNG":
            low, high = 35, 95
            while low <= high:
                mid = (low + high) // 2
                candidate = _encode_best(working, output_format, mid, has_alpha)
                if len(candidate[0]) <= target_bytes:
                    best = candidate
                    low = mid + 1
                else:
                    high = mid - 1
            if len(best[0]) <= target_bytes:
                return best[0], best[1], working, True
        else:
            best = _encode_best(working, output_format, 35, has_alpha)
            if len(best[0]) <= target_bytes:
                return best[0], best[1], working, True

        longest = max(working.size)
        if longest <= 320:
            return best[0], best[1], working, False
        next_longest = max(320, int(longest * 0.9))
        working = _resize_to_limit(working, next_longest)
        best = _encode_best(working, output_format, 35, has_alpha)
