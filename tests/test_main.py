import asyncio
from typing import Any

import pytest
from PIL import Image

from pixelpiper.callbacks import PipelineCallback, TimingCallback
from pixelpiper.decorators import max_retries, provides, requires, step, timeout
from pixelpiper.exceptions import MissingContextError, StepExecutionError, StepFailedError
from pixelpiper.pipeline import Pipeline, PipelineConfig, PipelineStep, StepResult, StepStatus

# ===== Mock Steps for Testing =====


class SimpleTestStep(PipelineStep):
    @step(name="test_step")
    @provides("test_value")
    async def process(self, image: Image.Image, context: dict[str, Any]) -> StepResult:
        return StepResult(status=StepStatus.COMPLETED, data={"test_value": "test_success"})


class RequiresContextStep(PipelineStep):
    @step(name="requires_context_step")
    @requires("input_value")
    @provides("output_value")
    async def process(self, image: Image.Image, context: dict[str, Any]) -> StepResult:
        input_value = context["input_value"]
        output_value = f"processed_{input_value}"
        return StepResult(status=StepStatus.COMPLETED, data={"output_value": output_value})


class FailingStep(PipelineStep):
    @step(name="failing_step")
    async def process(self, image: Image.Image, context: dict[str, Any]) -> StepResult:
        return StepResult(status=StepStatus.FAILED, data={}, error="Intentional failure for testing")


class ErrorRaisingStep(PipelineStep):
    @step(name="error_step")
    async def process(self, image: Image.Image, context: dict[str, Any]) -> StepResult:
        raise ValueError("TestError")


class RetryableStep(PipelineStep):
    def __init__(self, succeed_on_attempt: int = 3):
        super().__init__(name="retryable_step")
        self.attempts = 0
        self.succeed_on_attempt = succeed_on_attempt

    @step()
    @provides("retry_result")
    async def process(self, image: Image.Image, context: dict[str, Any]) -> StepResult:
        self.attempts += 1
        if self.attempts >= self.succeed_on_attempt:
            return StepResult(
                status=StepStatus.COMPLETED,
                data={"retry_result": f"Succeeded after {self.attempts} attempts"},
            )
        else:
            raise RuntimeError("AttemptFailed")


class SlowStep(PipelineStep):
    @step(name="slow_step")
    @timeout(0.5)
    async def process(self, image: Image.Image, context: dict[str, Any]) -> StepResult:
        try:
            await asyncio.sleep(1.0)
            return StepResult(status=StepStatus.COMPLETED, data={"slow_result": "completed"})
        except asyncio.CancelledError as err:
            raise asyncio.CancelledError("Timeout") from err


class ImageProcessingStep(PipelineStep):
    @step(name="image_processor")
    @provides("width", "height", "format")
    async def process(self, image: Image.Image, context: dict[str, Any]) -> StepResult:
        width, height = image.size
        return StepResult(
            status=StepStatus.COMPLETED,
            data={"width": width, "height": height, "format": image.format or "unknown"},
        )


class MockCallback(PipelineCallback):
    def __init__(self):
        self.before_calls = []
        self.after_calls = []

    async def before_step(self, step_name: str) -> None:
        self.before_calls.append(step_name)

    async def after_step(self, step_name: str, result: StepResult) -> None:
        self.after_calls.append((step_name, result.status))


# ===== Test Fixtures =====


@pytest.fixture
def test_image():
    return Image.new("RGB", (100, 100), color="white")


@pytest.fixture
def basic_pipeline():
    config = PipelineConfig(max_retries=2, timeout=5.0)
    return Pipeline(config)


# ===== Tests =====


@pytest.mark.asyncio
async def test_pipeline_basic(test_image, basic_pipeline):
    basic_pipeline.add_step(SimpleTestStep())
    result = await basic_pipeline.run(test_image)
    assert result["test_value"] == "test_success"


@pytest.mark.asyncio
async def test_pipeline_multiple_steps(test_image, basic_pipeline):
    basic_pipeline.add_step(SimpleTestStep())
    basic_pipeline.add_step(RequiresContextStep())
    initial_context = {"input_value": "test_input"}
    result = await basic_pipeline.run(test_image, initial_context)
    assert result["test_value"] == "test_success"
    assert result["output_value"] == "processed_test_input"


@pytest.mark.asyncio
async def test_pipeline_missing_context(test_image, basic_pipeline):
    basic_pipeline.add_step(RequiresContextStep())
    with pytest.raises(MissingContextError):
        await basic_pipeline.run(test_image)


@pytest.mark.asyncio
async def test_pipeline_step_failure(test_image, basic_pipeline):
    basic_pipeline.add_step(FailingStep())
    with pytest.raises(StepFailedError):
        await basic_pipeline.run(test_image)


@pytest.mark.asyncio
async def test_pipeline_exception_handling(test_image, basic_pipeline):
    basic_pipeline.add_step(ErrorRaisingStep())
    with pytest.raises(StepExecutionError) as excinfo:
        await basic_pipeline.run(test_image)
    assert "TestError" in str(excinfo.value)


@pytest.mark.asyncio
async def test_pipeline_retry_mechanism(test_image):
    config = PipelineConfig(max_retries=3, timeout=5.0)
    pipeline = Pipeline(config)
    retryable_step = RetryableStep(succeed_on_attempt=2)
    pipeline.add_step(retryable_step)
    result = await pipeline.run(test_image)
    assert "Succeeded after 2 attempts" in result["retry_result"]


@pytest.mark.asyncio
async def test_pipeline_retry_behavior(test_image):
    config = PipelineConfig(max_retries=2, timeout=5.0)
    pipeline = Pipeline(config)

    class CountingStep(PipelineStep):
        def __init__(self):
            super().__init__(name="counting_step")
            self.attempt_count = 0

        @step()
        async def process(self, image: Image.Image, context: dict[str, Any]) -> StepResult:
            self.attempt_count += 1
            raise ValueError("CountingStepFailed")

    counting_step = CountingStep()
    pipeline.add_step(counting_step)
    with pytest.raises(StepExecutionError):
        await pipeline.run(test_image)
    assert counting_step.attempt_count == 2


@pytest.mark.asyncio
async def test_pipeline_step_timeout(test_image, basic_pipeline):
    basic_pipeline.add_step(SlowStep())
    with pytest.raises(StepExecutionError):
        await basic_pipeline.run(test_image)


@pytest.mark.asyncio
async def test_pipeline_callbacks(test_image, basic_pipeline):
    callback = MockCallback()
    basic_pipeline.add_callback(callback)
    basic_pipeline.add_step(SimpleTestStep())
    basic_pipeline.add_step(ImageProcessingStep())
    await basic_pipeline.run(test_image)
    assert callback.before_calls == ["test_step", "image_processor"]
    assert len(callback.after_calls) == 2


@pytest.mark.asyncio
async def test_timing_callback(test_image, basic_pipeline):
    timing_callback = TimingCallback()
    basic_pipeline.add_callback(timing_callback)
    basic_pipeline.add_step(SimpleTestStep())
    basic_pipeline.add_step(ImageProcessingStep())
    await basic_pipeline.run(test_image)
    assert set(timing_callback.step_timings.keys()) == {"test_step", "image_processor"}
    for timing in timing_callback.step_timings.values():
        assert timing >= 0


@pytest.mark.asyncio
async def test_pipeline_custom_step_configuration(test_image):
    config = PipelineConfig(max_retries=1, timeout=10.0)
    pipeline = Pipeline(config)

    class CustomConfigStep(PipelineStep):
        @step(name="custom_config")
        @max_retries(3)
        @timeout(0.1)
        async def process(self, image: Image.Image, context: dict[str, Any]) -> StepResult:
            await asyncio.sleep(0.05)
            return StepResult(status=StepStatus.COMPLETED, data={"custom_config": "success"})

    pipeline.add_step(CustomConfigStep())
    result = await pipeline.run(test_image)
    assert result["custom_config"] == "success"
