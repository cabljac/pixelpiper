import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from PIL import Image
from .callbacks import PipelineCallback
from .types import StepResult, StepStatus

logger = logging.getLogger(__name__)

class PipelineStep(ABC):
    """Abstract base class for pipeline steps."""
    def __init__(self, name: Optional[str] = None) -> None:
        self._name = name or self.__class__.__name__
        self._required_context_keys: List[str] = []
        self._provided_context_keys: List[str] = []
        self._load_metadata()

    def _load_metadata(self) -> None:
      process_method = getattr(self.__class__, "process", None)
      if process_method and hasattr(process_method, "_step_metadata"):
          metadata = process_method._step_metadata
          if metadata.name:
              self._name = metadata.name
          self._required_context_keys = list(metadata.requires)
          self._provided_context_keys = list(metadata.provides)


    @property
    def name(self) -> str:
        return self._name

    @property
    def required_context_keys(self) -> List[str]:
        return self._required_context_keys

    @property
    def provided_context_keys(self) -> List[str]:
        return self._provided_context_keys

    def validate_context(self, context: Dict[str, Any]) -> bool:
        missing = [key for key in self.required_context_keys if key not in context]
        if missing:
            logger.warning("Missing required keys", extra={"step": self.name, "missing": missing})
        return not missing

    @abstractmethod
    async def process(self, image: Image.Image, context: Dict[str, Any]) -> StepResult:
        """Process the input image and update the context."""
        pass

@dataclass
class PipelineConfig:
    """Configuration for pipeline execution."""
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: float = 30.0
    validate_outputs: bool = True

class Pipeline:
    """Pipeline executor for running a series of steps."""
    def __init__(self, config: Optional[PipelineConfig] = None, callbacks: Optional[List[PipelineCallback]] = None) -> None:
        self.steps: List[PipelineStep] = []
        self.context: Dict[str, Any] = {}
        self.config = config or PipelineConfig()
        self.callbacks: List[PipelineCallback] = callbacks or []
        # UI callback logic removed

    def add_step(self, step: PipelineStep) -> None:
        self.steps.append(step)

    def add_callback(self, callback: PipelineCallback) -> None:
        self.callbacks.append(callback)

    async def _run_step(self, step: PipelineStep, image: Image.Image) -> StepResult:
        timeout_val = self.config.timeout
        retries = self.config.max_retries
        # Adjust timeout and retries from metadata if available.
        process_method = step.__class__.process
        if hasattr(process_method, "_step_metadata"):
            metadata = process_method._step_metadata
            if metadata.timeout is not None:
                timeout_val = metadata.timeout
            if metadata.max_retries is not None:
                retries = metadata.max_retries

        for attempt in range(1, retries + 1):
            try:
                logger.info("Executing step", extra={"step": step.name, "attempt": attempt})
                async with asyncio.timeout(timeout_val):
                    for callback in self.callbacks:
                        await callback.before_step(step.name)
                    result = await step.process(image, self.context)
                    for callback in self.callbacks:
                        await callback.after_step(step.name, result)
                    return result
            except Exception as e:
                logger.error("Error in step", extra={"step": step.name, "attempt": attempt, "error": str(e)})
                if attempt < retries:
                    await asyncio.sleep(self.config.retry_delay)
                else:
                    failed = StepResult(status=StepStatus.FAILED, data={}, error=str(e))
                    for callback in self.callbacks:
                        await callback.after_step(step.name, failed)
                    return failed

    async def run(self, image: Image.Image, initial_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self.context = initial_context or {}
        try:
            for step in self.steps:
                logger.info("Starting step", extra={"step": step.name})
                if not step.validate_context(self.context):
                    raise ValueError(f"Missing keys for {step.name}")
                result = await self._run_step(step, image)
                if result.status == StepStatus.FAILED:
                    raise RuntimeError(f"Step {step.name} failed: {result.error}")
                self.context.update(result.data)
                logger.info("Completed step", extra={"step": step.name})
            return self.context
        finally:
            # Ensure all callbacks are closed if applicable.
            for callback in self.callbacks:
                if hasattr(callback, "close") and callable(callback.close):
                    await callback.close()
