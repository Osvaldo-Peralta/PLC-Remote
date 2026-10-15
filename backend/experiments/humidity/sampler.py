from __future__ import annotations

from datetime import datetime
from typing import Any

from .models import SensorSample


class HumiditySampler:
    """Reads the process variables directly from PLCManager for the experiment."""

    def __init__(self, plc: Any, clock=datetime.now):
        self.plc = plc
        self.clock = clock

    async def sample(self, elapsed_seconds: float) -> SensorSample:
        values = {}
        for name in (
            "humedadSCD41",
            "humedad_ext",
            "temperaturaSCD41",
            "temperaturaExt",
            "extractor",
            "humificador",
            "mister",
        ):
            try:
                values[name] = await self.plc.read_value(name)
            except Exception as exc:
                # Include the failing variable in the error shown by the API/CSV status.
                raise RuntimeError(f"ERROR_READ: fallo al leer '{name}': {exc}") from exc

            if values[name] is None:
                raise RuntimeError(f"ERROR_READ: el nodo '{name}' devolvió un valor vacío")

        return SensorSample(
            timestamp=self.clock(),
            elapsed_seconds=elapsed_seconds,
            humidity_inside=float(values["humedadSCD41"]),
            humidity_outside=float(values["humedad_ext"]),
            temperature_inside=float(values["temperaturaSCD41"]),
            temperature_outside=float(values["temperaturaExt"]),
            extractor=bool(values["extractor"]),
            humidifier=bool(values["humificador"]),
            mister=bool(values["mister"]),
        )
