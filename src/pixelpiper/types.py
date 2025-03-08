# types.py
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

class StepStatus(Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class StepResult:
    status: StepStatus
    data: Dict[str, Any]
    error: Optional[str] = None
