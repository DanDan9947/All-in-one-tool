from io import BytesIO

from PIL import Image

from app.services.ink_cutout import remove_white_background


def test_white_background_becomes_transparent_and_ink_remains():
    source = Image.new("RGB", (3, 1), "white")
    source.putpixel((1, 0), (20, 90, 180))
    source.putpixel((2, 0), (0, 0, 0))

    result = Image.open(BytesIO(remove_white_background(source, threshold=18)))

    assert result.mode == "RGBA"
    assert result.getpixel((0, 0))[3] == 0
    assert result.getpixel((1, 0))[3] > 240
    assert result.getpixel((2, 0))[3] == 255


def test_threshold_removes_near_white_jpeg_noise():
    source = Image.new("RGB", (2, 1), (248, 249, 247))
    source.putpixel((1, 0), (220, 220, 220))

    result = Image.open(BytesIO(remove_white_background(source, threshold=18)))

    assert result.getpixel((0, 0))[3] == 0
    assert result.getpixel((1, 0))[3] > 0
