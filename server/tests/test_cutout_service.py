from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

from app.services.cutout import CutoutService


class RecordingSession:
    def __init__(self) -> None:
        self.input_shape: tuple[int, ...] | None = None

    def run(self, _outputs, inputs):
        tensor = next(iter(inputs.values()))
        self.input_shape = tensor.shape
        return [np.ones((1, 1, tensor.shape[2], tensor.shape[3]), dtype=np.float32)]


def test_cutout_preserves_aspect_ratio_and_output_resolution():
    service = CutoutService(Path("unused.onnx"), inference_max_dimension=1024)
    session = RecordingSession()
    service._session = session
    service._input_name = "input"
    source = Image.new("RGB", (1600, 900), "blue")

    result = Image.open(BytesIO(service.remove_background(source)))

    assert result.size == source.size
    assert result.mode == "RGBA"
    assert session.input_shape is not None
    _, _, model_height, model_width = session.input_shape
    assert model_width == 1024
    assert model_height == 576
    assert model_width % 32 == 0
    assert model_height % 32 == 0


def test_cutout_pads_to_model_multiple_without_stretching():
    service = CutoutService(Path("unused.onnx"), inference_max_dimension=1024)
    pixels, crop = service._prepare_input(Image.new("RGB", (1000, 667), "white"))

    assert pixels.shape[:2] == (672, 1024)
    left, top, width, height = crop
    assert (width, height) == (1000, 667)
    assert left + width <= pixels.shape[1]
    assert top + height <= pixels.shape[0]
