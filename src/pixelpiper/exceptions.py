from typing import Optional


class PixelPiperError(Exception):
    """Base exception class for PixelPiper errors."""


class StepExecutionError(PixelPiperError):
    """Raised when a step fails after exhausting retries."""

    def __init__(self, step_name: str, retries: int, cause: Exception):
        message = f"Step '{step_name}' failed after {retries} retries: {cause}"
        super().__init__(message)


class MissingContextError(PixelPiperError):
    """Raised when required context keys are missing."""

    def __init__(self, step_name: str, missing_keys: Optional[list[str]] = None) -> None:
        msg = f"Missing required keys for step '{step_name}'"
        if missing_keys:
            msg += f": {', '.join(missing_keys)}"
        super().__init__(msg)


class StepFailedError(PixelPiperError):
    """Raised when a step explicitly returns a failure."""

    def __init__(self, step_name: str, error: Optional[str] = None) -> None:
        msg = f"Step '{step_name}' failed"
        if error:
            msg += f": {error}"
        super().__init__(msg)
