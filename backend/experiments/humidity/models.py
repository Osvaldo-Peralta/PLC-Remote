from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class ExperimentState(str, Enum):
    IDLE = "IDLE"
    MONITORING = "MONITORING"
    HUMIDIFYING = "HUMIDIFYING"
    EXTRACTING = "EXTRACTING"
    WAITING = "WAITING"
    TARGET_REACHED = "TARGET_REACHED"
    TIMEOUT = "TIMEOUT"
    STOPPED = "STOPPED"
    ERROR = "ERROR"


class ActionType(str, Enum):
    HUMIDIFY = "humidify"
    EXTRACT = "extract"
    MONITOR = "monitor"
    FINISH = "finish"


@dataclass(frozen=True)
class SensorSample:
    timestamp: datetime
    elapsed_seconds: float
    humidity_inside: float
    humidity_outside: float
    temperature_inside: float
    temperature_outside: float
    extractor: bool
    humidifier: bool
    mister: bool


@dataclass(frozen=True)
class ControlDecision:
    action: ActionType
    duration_seconds: Optional[float]
    reason: str


@dataclass(frozen=True)
class ExperimentResult:
    experiment_id: str
    status: ExperimentState
    started_at: datetime
    finished_at: datetime
    initial_humidity: Optional[float]
    final_humidity: Optional[float]
    target_humidity: Optional[float]
    time_to_target_seconds: Optional[float]
    cycles: int
    max_humidity: Optional[float]
    max_humidity_elapsed_seconds: Optional[float]
    csv_path: Optional[str]
    error: Optional[str] = None
