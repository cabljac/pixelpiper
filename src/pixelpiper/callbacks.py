import time
import logging
from typing import Dict
from .types import StepResult  # Common types extracted to a separate module

logger = logging.getLogger(__name__)

class PipelineCallback:
    """Interface for pipeline callbacks."""
    async def before_step(self, step_name: str) -> None:
        pass

    async def after_step(self, step_name: str, result: StepResult) -> None:
        pass

class TimingCallback(PipelineCallback):
    """Callback that tracks execution time for pipeline steps."""
    def __init__(self) -> None:
        self.step_timings: Dict[str, float] = {}
        self._current_start: float = 0.0

    async def before_step(self, step_name: str) -> None:
        self._current_start = time.time()
        logger.info("Starting step", extra={"step": step_name})

    async def after_step(self, step_name: str, result: StepResult) -> None:
        duration = time.time() - self._current_start
        self.step_timings[step_name] = duration
        logger.info("Finished step", extra={"step": step_name, "duration": duration, "status": result.status.value})
