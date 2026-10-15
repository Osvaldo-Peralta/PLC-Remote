from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

from ..models import SensorSample
from .evaluator import ThresholdEvaluator


class TargetAttainmentRecorder:
    """Writes one measurement row per sample plus milestone-event columns."""

    HEADER = [
        "timestamp",
        "elapsed_seconds",
        "humidity_inside",
        "humidity_outside",
        "temperature_inside",
        "temperature_outside",
        "extractor",
        "humidifier",
        "mister",
        "first_crossing_92_seconds",
        "time_to_92_seconds",
        "first_crossing_94_seconds",
        "time_to_94_seconds",
        "events",
    ]

    def __init__(self, output_dir: str | Path, experiment_id: str):
        self.output_dir = Path(output_dir)
        self.experiment_id = experiment_id
        self.path: Optional[Path] = None
        self.file = None
        self.writer = None

    async def open(self) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.output_dir / f"prueba_umbral_humedad_{self.experiment_id}.csv"
        self.file = self.path.open("w", newline="", encoding="utf-8")
        self.writer = csv.DictWriter(self.file, fieldnames=self.HEADER)
        self.writer.writeheader()
        self.file.flush()
        return self.path

    async def record(
        self,
        sample: SensorSample,
        evaluator: ThresholdEvaluator,
        events: list[str],
    ) -> None:
        if not self.writer or not self.file:
            raise RuntimeError("El recorder de alcance de umbral no está abierto")

        milestones = evaluator.milestones
        self.writer.writerow({
            "timestamp": sample.timestamp.isoformat(),
            "elapsed_seconds": f"{sample.elapsed_seconds:.3f}",
            "humidity_inside": f"{sample.humidity_inside:.3f}",
            "humidity_outside": f"{sample.humidity_outside:.3f}",
            "temperature_inside": f"{sample.temperature_inside:.3f}",
            "temperature_outside": f"{sample.temperature_outside:.3f}",
            "extractor": int(sample.extractor),
            "humidifier": int(sample.humidifier),
            "mister": int(sample.mister),
            "first_crossing_92_seconds": milestones[92.0].first_crossing_seconds,
            "time_to_92_seconds": milestones[92.0].time_to_target_seconds,
            "first_crossing_94_seconds": milestones[94.0].first_crossing_seconds,
            "time_to_94_seconds": milestones[94.0].time_to_target_seconds,
            "events": ";".join(events),
        })
        self.file.flush()

    async def close(self) -> None:
        if self.file:
            self.file.close()
            self.file = None
            self.writer = None
