from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Milestone:
    target_humidity: float
    first_crossing_seconds: Optional[float] = None
    stable_since_seconds: Optional[float] = None
    time_to_target_seconds: Optional[float] = None

    @property
    def first_crossed(self) -> bool:
        return self.first_crossing_seconds is not None

    @property
    def confirmed(self) -> bool:
        return self.time_to_target_seconds is not None

    def snapshot(self) -> dict:
        return {
            "target_humidity": self.target_humidity,
            "first_crossing_seconds": self.first_crossing_seconds,
            "time_to_target_seconds": self.time_to_target_seconds,
            "reached": self.confirmed,
        }


class ThresholdEvaluator:
    """Measures first threshold crossing and sustained attainment independently.

    A milestone is confirmed after humidity remains at or above its target for
    the configured stability interval. Once confirmed, it stays confirmed.
    The first crossing is retained even if humidity later falls below target.
    """

    def __init__(self, stability_seconds: float = 30.0):
        if stability_seconds < 0:
            raise ValueError("stability_seconds no puede ser negativo")
        self.stability_seconds = float(stability_seconds)
        self.milestones = {
            92.0: Milestone(92.0),
            94.0: Milestone(94.0),
        }

    def update(self, humidity: float, elapsed_seconds: float) -> list[str]:
        events: list[str] = []
        for target, milestone in self.milestones.items():
            if milestone.confirmed:
                continue

            if humidity >= target:
                if milestone.first_crossing_seconds is None:
                    milestone.first_crossing_seconds = round(elapsed_seconds, 3)
                    events.append(f"FIRST_CROSSING_{int(target)}")

                if milestone.stable_since_seconds is None:
                    milestone.stable_since_seconds = elapsed_seconds
                if elapsed_seconds - milestone.stable_since_seconds >= self.stability_seconds:
                    milestone.time_to_target_seconds = round(elapsed_seconds, 3)
                    events.append(f"TARGET_{int(target)}_STABLE")
            else:
                # A brief crossing does not satisfy the sustained-attainment rule.
                milestone.stable_since_seconds = None

        return events

    def snapshot(self) -> dict:
        return {
            "stability_seconds": self.stability_seconds,
            "milestones": {
                str(int(target)): milestone.snapshot()
                for target, milestone in self.milestones.items()
            },
        }
