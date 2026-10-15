from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

from .models import SensorSample


class CSVRecorder:
    def __init__(self, output_dir: str | Path, experiment_id: str):
        self.output_dir = Path(output_dir)
        self.experiment_id = experiment_id
        self.file = None
        self.writer = None
        self.path: Optional[Path] = None

    async def open(self) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.output_dir / f"prueba_humedad_{self.experiment_id}.csv"
        self.file = self.path.open("w", newline="", encoding="utf-8")
        self.writer = csv.writer(self.file)
        self.writer.writerow([
            "timestamp",
            "elapsed_seconds",
            "humidity_inside",
            "humidity_outside",
            "temperature_inside",
            "temperature_outside",
            "extractor",
            "humidifier",
            "mister",
        ])
        self.file.flush()
        return self.path

    async def record(self, sample: SensorSample) -> None:
        if not self.writer or not self.file:
            raise RuntimeError("El recorder no está abierto")
        self.writer.writerow([
            sample.timestamp.isoformat(),
            f"{sample.elapsed_seconds:.3f}",
            f"{sample.humidity_inside:.3f}",
            f"{sample.humidity_outside:.3f}",
            f"{sample.temperature_inside:.3f}",
            f"{sample.temperature_outside:.3f}",
            int(sample.extractor),
            int(sample.humidifier),
            int(sample.mister),
        ])
        self.file.flush()

    async def close(self) -> None:
        if self.file:
            self.file.close()
            self.file = None
            self.writer = None
