from typing import Any, Callable, Optional, Protocol


class StepMetadata:
    """Metadata storage for step decorators."""

    def __init__(self) -> None:
        self.requires: set[str] = set()
        self.provides: set[str] = set()
        self.timeout: Optional[float] = None
        self.max_retries: Optional[int] = None
        self.name: Optional[str] = None


class StepMethod(Protocol):
    _step_metadata: StepMetadata
    __name__: str

    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...


def _ensure_metadata(method: StepMethod) -> StepMetadata:
    """Ensure that a method has a _step_metadata attribute."""
    if not hasattr(method, "_step_metadata"):
        method._step_metadata = StepMetadata()
    return method._step_metadata


def step(name: Optional[str] = None) -> Callable[[StepMethod], StepMethod]:
    """Decorator to mark a method as a pipeline step."""

    def decorator(method: StepMethod) -> StepMethod:
        metadata = _ensure_metadata(method)
        metadata.name = name if name is not None else method.__name__
        return method

    return decorator


def requires(*keys: str) -> Callable[[StepMethod], StepMethod]:
    """Decorator to specify required context keys for a step."""

    def decorator(method: StepMethod) -> StepMethod:
        metadata = _ensure_metadata(method)
        metadata.requires.update(keys)
        return method

    return decorator


def provides(*keys: str) -> Callable[[StepMethod], StepMethod]:
    """Decorator to specify provided context keys for a step."""

    def decorator(method: StepMethod) -> StepMethod:
        metadata = _ensure_metadata(method)
        metadata.provides.update(keys)
        return method

    return decorator


def timeout(seconds: float) -> Callable[[StepMethod], StepMethod]:
    """Decorator to specify a custom timeout for a step."""

    def decorator(method: StepMethod) -> StepMethod:
        metadata = _ensure_metadata(method)
        metadata.timeout = seconds
        return method

    return decorator


def max_retries(count: int) -> Callable[[StepMethod], StepMethod]:
    """Decorator to specify a custom retry count for a step."""

    def decorator(method: StepMethod) -> StepMethod:
        metadata = _ensure_metadata(method)
        metadata.max_retries = count
        return method

    return decorator
