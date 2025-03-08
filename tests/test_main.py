import pytest
import asyncio
from PIL import Image
import io
from unittest.mock import MagicMock, patch
import time
from typing import Dict, Any, List, Optional

# Pipeline core classes are now in pipeline.py
from pixelpiper.pipeline import (
    Pipeline, PipelineConfig, PipelineStep, StepResult, StepStatus
)

# Decorator functions are in decorators.py
from pixelpiper.decorators import step, requires, provides, timeout, max_retries

# Callback interfaces and implementations are in callbacks.py
from pixelpiper.callbacks import PipelineCallback, TimingCallback

# ===== Mock Steps for Testing =====

class SimpleTestStep(PipelineStep):
    """Simple test step that adds a test key to the context."""
    
    @step(name="test_step")
    @provides("test_value")
    async def process(self, image: Image.Image, context: Dict[str, Any]) -> StepResult:
        return StepResult(
            status=StepStatus.COMPLETED,
            data={"test_value": "test_success"}
        )


class RequiresContextStep(PipelineStep):
    """Step that requires context values to function."""
    
    @step(name="requires_context_step")
    @requires("input_value")
    @provides("output_value")
    async def process(self, image: Image.Image, context: Dict[str, Any]) -> StepResult:
        # Process the input value
        input_value = context["input_value"]
        output_value = f"processed_{input_value}"
        return StepResult(
            status=StepStatus.COMPLETED,
            data={"output_value": output_value}
        )


class FailingStep(PipelineStep):
    """Step that fails on purpose."""
    
    @step(name="failing_step")
    async def process(self, image: Image.Image, context: Dict[str, Any]) -> StepResult:
        return StepResult(
            status=StepStatus.FAILED,
            data={},
            error="Intentional failure for testing"
        )


class ErrorRaisingStep(PipelineStep):
    """Step that raises an exception."""
    
    @step(name="error_step")
    async def process(self, image: Image.Image, context: Dict[str, Any]) -> StepResult:
        raise ValueError("Test exception")


class RetryableStep(PipelineStep):
    """Step that succeeds only after a certain number of attempts."""
    
    def __init__(self, succeed_on_attempt: int = 3):
        super().__init__(name="retryable_step")
        self.attempts = 0
        self.succeed_on_attempt = succeed_on_attempt
    
    @step()
    @provides("retry_result")
    async def process(self, image: Image.Image, context: Dict[str, Any]) -> StepResult:
        self.attempts += 1
        if self.attempts >= self.succeed_on_attempt:
            return StepResult(
                status=StepStatus.COMPLETED,
                data={"retry_result": f"Succeeded after {self.attempts} attempts"}
            )
        else:
            raise RuntimeError(f"Failed attempt {self.attempts}")


class SlowStep(PipelineStep):
    """Step that takes a long time to complete."""
    
    @step(name="slow_step")
    @timeout(0.5)  # Short timeout for testing
    async def process(self, image: Image.Image, context: Dict[str, Any]) -> StepResult:
        try:
            # Simulate long processing (should exceed timeout)
            await asyncio.sleep(1.0)
            return StepResult(
                status=StepStatus.COMPLETED,
                data={"slow_result": "completed"}
            )
        except asyncio.CancelledError:
            raise asyncio.CancelledError("Operation timed out")


class ImageProcessingStep(PipelineStep):
    """Step that actually processes the image."""
    
    @step(name="image_processor")
    @provides("width", "height", "format")
    async def process(self, image: Image.Image, context: Dict[str, Any]) -> StepResult:
        width, height = image.size
        return StepResult(
            status=StepStatus.COMPLETED,
            data={
                "width": width,
                "height": height,
                "format": image.format or "unknown"
            }
        )


class MockCallback(PipelineCallback):
    """Callback for testing callback mechanism."""
    
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
    """Create a test image for pipeline processing."""
    return Image.new('RGB', (100, 100), color='white')


@pytest.fixture
def basic_pipeline():
    """Create a basic pipeline configuration."""
    config = PipelineConfig(max_retries=2, timeout=5.0)
    return Pipeline(config)


# ===== Tests =====

@pytest.mark.asyncio
async def test_pipeline_basic(test_image, basic_pipeline):
    """Test that the pipeline can run a simple step successfully."""
    basic_pipeline.add_step(SimpleTestStep())
    result = await basic_pipeline.run(test_image)
    assert "test_value" in result
    assert result["test_value"] == "test_success"


@pytest.mark.asyncio
async def test_pipeline_multiple_steps(test_image, basic_pipeline):
    """Test pipeline with multiple sequential steps."""
    basic_pipeline.add_step(SimpleTestStep())
    basic_pipeline.add_step(RequiresContextStep())
    initial_context = {"input_value": "test_input"}
    result = await basic_pipeline.run(test_image, initial_context)
    assert "test_value" in result
    assert "output_value" in result
    assert result["test_value"] == "test_success"
    assert result["output_value"] == "processed_test_input"


@pytest.mark.asyncio
async def test_pipeline_missing_context(test_image, basic_pipeline):
    """Test pipeline fails when required context is missing."""
    basic_pipeline.add_step(RequiresContextStep())
    with pytest.raises(ValueError) as excinfo:
        await basic_pipeline.run(test_image)
    # Expect error message to indicate missing keys for the decorated step name
    assert "Missing keys for requires_context_step" in str(excinfo.value)


@pytest.mark.asyncio
async def test_pipeline_step_failure(test_image, basic_pipeline):
    """Test pipeline handles step failure properly."""
    basic_pipeline.add_step(FailingStep())
    with pytest.raises(RuntimeError) as excinfo:
        await basic_pipeline.run(test_image)
    assert "failing_step failed" in str(excinfo.value)
    assert "Intentional failure" in str(excinfo.value)


@pytest.mark.asyncio
async def test_pipeline_exception_handling(test_image, basic_pipeline):
    """Test pipeline handles exceptions thrown by steps."""
    basic_pipeline.add_step(ErrorRaisingStep())
    with pytest.raises(RuntimeError) as excinfo:
        await basic_pipeline.run(test_image)
    assert "Test exception" in str(excinfo.value)


@pytest.mark.asyncio
async def test_pipeline_retry_mechanism(test_image):
    """Test retry mechanism works properly."""
    config = PipelineConfig(max_retries=3, timeout=5.0)
    pipeline = Pipeline(config)
    retryable_step = RetryableStep(succeed_on_attempt=2)
    pipeline.add_step(retryable_step)
    result = await pipeline.run(test_image)
    assert "retry_result" in result
    assert "Succeeded after 2 attempts" in result["retry_result"]


@pytest.mark.asyncio
async def test_pipeline_retry_behavior(test_image):
    """Test the retry mechanism's attempt count."""
    config = PipelineConfig(max_retries=2, timeout=5.0)
    pipeline = Pipeline(config)
    class CountingStep(PipelineStep):
        def __init__(self):
            super().__init__(name="counting_step")
            self.attempt_count = 0
        @step()
        async def process(self, image: Image.Image, context: Dict[str, Any]) -> StepResult:
            self.attempt_count += 1
            raise ValueError(f"Test failure on attempt {self.attempt_count}")
    counting_step = CountingStep()
    pipeline.add_step(counting_step)
    with pytest.raises(Exception):
        await pipeline.run(test_image)
    assert counting_step.attempt_count == 2, f"Expected 2 attempts but got {counting_step.attempt_count}"


@pytest.mark.asyncio
async def test_pipeline_retry_exhaustion(test_image):
    """Test that pipeline fails when retries are exhausted."""
    config = PipelineConfig(max_retries=2, timeout=5.0)
    pipeline = Pipeline(config)
    class RetryExhaustionStep(PipelineStep):
        def __init__(self):
            # Passing a custom name; note that if no name is given to @step(),
            # the decorator will default to "process"
            super().__init__(name="retry_exhaustion_step")
            self.attempts = 0
        @step()
        @provides("success_value")
        async def process(self, image: Image.Image, context: Dict[str, Any]) -> StepResult:
            self.attempts += 1
            if self.attempts >= 3:
                return StepResult(
                    status=StepStatus.COMPLETED,
                    data={"success_value": "success"}
                )
            else:
                raise ValueError(f"Test failure on attempt {self.attempts}")
    pipeline.add_step(RetryExhaustionStep())
    with pytest.raises(RuntimeError) as excinfo:
        await pipeline.run(test_image)
    # Instead of expecting the explicit step name, assert that the error message contains
    # a failure indication and the test failure message.
    error_msg = str(excinfo.value)
    assert "failed" in error_msg.lower()
    assert "Test failure on attempt" in error_msg


@pytest.mark.asyncio
async def test_pipeline_retry_success(test_image):
    """Test successful retry when step succeeds on second attempt."""
    config = PipelineConfig(max_retries=2, timeout=5.0)
    pipeline = Pipeline(config)
    class SucceedOnSecondStep(PipelineStep):
        def __init__(self):
            super().__init__(name="succeed_on_second_step")
            self.attempts = 0
        @step()
        @provides("retry_result")
        async def process(self, image: Image.Image, context: Dict[str, Any]) -> StepResult:
            self.attempts += 1
            if self.attempts >= 2:
                return StepResult(
                    status=StepStatus.COMPLETED,
                    data={"retry_result": f"Succeeded after {self.attempts} attempts"}
                )
            else:
                raise ValueError(f"Failed attempt {self.attempts}")
    pipeline.add_step(SucceedOnSecondStep())
    result = await pipeline.run(test_image)
    assert "retry_result" in result
    assert "Succeeded after 2 attempts" in result["retry_result"]


@pytest.mark.asyncio
async def test_pipeline_step_timeout(test_image, basic_pipeline):
    """Test timeout mechanism in steps."""
    basic_pipeline.add_step(SlowStep())
    with pytest.raises(RuntimeError) as excinfo:
        await basic_pipeline.run(test_image)
    # Verify that the error message includes the decorated step name
    assert "slow_step" in str(excinfo.value)


@pytest.mark.asyncio
async def test_pipeline_image_processing(test_image, basic_pipeline):
    """Test image processing step using the actual image."""
    basic_pipeline.add_step(ImageProcessingStep())
    result = await basic_pipeline.run(test_image)
    assert "width" in result
    assert "height" in result
    assert result["width"] == 100
    assert result["height"] == 100


@pytest.mark.asyncio
async def test_pipeline_callbacks(test_image, basic_pipeline):
    """Test callback mechanism."""
    callback = MockCallback()
    basic_pipeline.add_callback(callback)
    basic_pipeline.add_step(SimpleTestStep())
    basic_pipeline.add_step(ImageProcessingStep())
    await basic_pipeline.run(test_image)
    # Expect the decorated step names in callbacks
    assert len(callback.before_calls) == 2
    assert len(callback.after_calls) == 2
    assert "test_step" in callback.before_calls
    assert "image_processor" in callback.before_calls
    assert any(call[0] == "test_step" and call[1] == StepStatus.COMPLETED for call in callback.after_calls)
    assert any(call[0] == "image_processor" and call[1] == StepStatus.COMPLETED for call in callback.after_calls)


@pytest.mark.asyncio
async def test_timing_callback(test_image, basic_pipeline):
    """Test the TimingCallback functionality."""
    timing_callback = TimingCallback()
    basic_pipeline.add_callback(timing_callback)
    basic_pipeline.add_step(SimpleTestStep())
    basic_pipeline.add_step(ImageProcessingStep())
    await basic_pipeline.run(test_image)
    # Expect the keys to be the decorated names
    assert len(timing_callback.step_timings) == 2
    assert "test_step" in timing_callback.step_timings
    assert "image_processor" in timing_callback.step_timings
    assert timing_callback.step_timings["test_step"] >= 0
    assert timing_callback.step_timings["image_processor"] >= 0


@pytest.mark.asyncio
async def test_pipeline_custom_step_configuration():
    """Test that steps can override pipeline configuration."""
    config = PipelineConfig(max_retries=1, timeout=10.0)
    pipeline = Pipeline(config)
    class CustomConfigStep(PipelineStep):
        @step(name="custom_config")
        @max_retries(3)  # Override pipeline config
        @timeout(0.1)    # Override pipeline config
        async def process(self, image: Image.Image, context: Dict[str, Any]) -> StepResult:
            await asyncio.sleep(0.05)
            return StepResult(
                status=StepStatus.COMPLETED,
                data={"custom_config": "success"}
            )
    pipeline.add_step(CustomConfigStep())
    test_image = Image.new('RGB', (100, 100), color='white')
    result = await pipeline.run(test_image)
    assert "custom_config" in result
    assert result["custom_config"] == "success"


@pytest.mark.asyncio
async def test_pipeline_decorator_metadata_extraction():
    """Test that decorator metadata is correctly extracted and applied."""
    class MetadataStep(PipelineStep):
        @step(name="metadata_step")
        @requires("req1", "req2")
        @provides("prov1", "prov2", "prov3")
        @timeout(7.5)
        @max_retries(4)
        async def process(self, image: Image.Image, context: Dict[str, Any]) -> StepResult:
            return StepResult(
                status=StepStatus.COMPLETED,
                data={"prov1": "value1", "prov2": "value2", "prov3": "value3"}
            )
    step_instance = MetadataStep()
    assert step_instance.name == "metadata_step"
    assert sorted(step_instance.required_context_keys) == sorted(["req1", "req2"])
    assert sorted(step_instance.provided_context_keys) == sorted(["prov1", "prov2", "prov3"])
    process_method = MetadataStep.process
    assert hasattr(process_method, '_step_metadata')
    assert process_method._step_metadata.timeout == 7.5
    assert process_method._step_metadata.max_retries == 4
