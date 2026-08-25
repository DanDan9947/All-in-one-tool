from io import BytesIO

import numpy as np
from PIL import Image


def remove_white_background(image: Image.Image, threshold: int = 18) -> bytes:
    """Turn white paper transparent while preserving colored and dark ink."""
    rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
    ink_strength = 255.0 - np.min(rgb, axis=2)
    full_opacity_strength = max(96, threshold + 1)
    alpha = (ink_strength - threshold) * (
        255.0 / (full_opacity_strength - threshold)
    )
    alpha = np.clip(alpha, 0.0, 255.0).astype(np.uint8)

    rgba = np.dstack((rgb.astype(np.uint8), alpha))
    output = BytesIO()
    Image.fromarray(rgba).save(output, format="PNG", optimize=True)
    return output.getvalue()
