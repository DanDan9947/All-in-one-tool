from io import BytesIO

import numpy as np
from PIL import Image

from app.image_utils import decode_image, rgba_png


def test_decode_resizes_long_edge():
    output = BytesIO()
    Image.new("RGB", (400, 200), "white").save(output, "JPEG")
    decoded = decode_image(output.getvalue(), max_dimension=100)
    assert decoded.image.size == (100, 50)


def test_rgba_png_contains_alpha():
    image = Image.new("RGB", (10, 10), "red")
    alpha = np.zeros((10, 10), dtype=np.uint8)
    data = rgba_png(image, alpha)
    result = Image.open(BytesIO(data))
    assert result.mode == "RGBA"
    assert result.getpixel((0, 0))[3] == 0

