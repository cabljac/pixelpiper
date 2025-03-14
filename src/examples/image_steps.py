# image_steps.py
from typing import Any

from PIL import Image

from pixelpiper.decorators import max_retries, provides, requires, step, timeout
from pixelpiper.pipeline import PipelineStep, StepResult, StepStatus


class ImageResizeStep(PipelineStep):
    """Resizes an image according to an input size factor."""

    @step(name="image_resize")
    @requires("input_size")
    @provides("resized_image", "resize_factor")
    @timeout(10.0)
    @max_retries(2)
    async def process(self, image: Image.Image, context: dict[str, Any]) -> StepResult:
        try:
            target_size = context["input_size"]
            width, height = image.size
            resize_factor = target_size / max(width, height)
            new_size = (int(width * resize_factor), int(height * resize_factor))
            resized_image = image.resize(new_size)
            return StepResult(
                status=StepStatus.COMPLETED, data={"resized_image": resized_image, "resize_factor": resize_factor}
            )
        except Exception as e:
            return StepResult(status=StepStatus.FAILED, data={}, error=str(e))
