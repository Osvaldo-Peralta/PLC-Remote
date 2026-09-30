from __future__ import annotations

import asyncio
import csv
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


# -----------------------------------------------------------------------------
# Configuración de la prueba piloto
# -----------------------------------------------------------------------------
TEST_DURATION_SECONDS = 10 * 60
SAMPLE_INTERVAL_SECONDS = 1.0
ACTUATION_DURATION_SECONDS = 35.0

HUMIDITY_LOWER_THRESHOLD = 92.0
HUMIDITY_UPPER_THRESHOLD = 94.0

# Nodos de escritura: SOLO para el entorno experimental.
HUMIDIFIER_WRITE_NODE = "humificador_rw"
MISTER_WRITE_NODE = "mister_rw"

# Nodos de estado observados durante la prueba.
HUMIDIFIER_STATUS_NODE = "humificador"
MISTER_STATUS_NODE = "mister"

CSV_HEADER = [
    "timestamp",
    "elapsed_seconds",
    "temperature_ext",
    "humidity_ext",
    "humidity_int",
    "humidifier",
    "mister",
]


@dataclass
class HumidityExperimentResult:
    test_id: int
    started_at: datetime
    finished_at: Optional[datetime] = None
    initial_humidity: Optional[float] = None
    time_to_92: Optional[float] = None
    time_to_94: Optional[float] = None
    maximum_humidity: Optional[float] = None
    csv_path: Optional[str] = None


@dataclass
class HumidityExperiment:
    """
    Ejecuta una prueba experimental aislada del funcionamiento normal del HMI.

    Durante la operación normal, esta clase NO debe ejecutarse.
    Durante una prueba, controla temporalmente humidificador y mister mediante
    sus nodos *_rw y registra la respuesta del ambiente en un CSV.
    """

    plc: Any
    output_dir: Path = Path("experiments/data")
    test_duration: float = TEST_DURATION_SECONDS
    sample_interval: float = SAMPLE_INTERVAL_SECONDS
    actuation_duration: float = ACTUATION_DURATION_SECONDS

    running: bool = False
    current_result: Optional[HumidityExperimentResult] = None
    _task: Optional[asyncio.Task] = field(default=None, init=False, repr=False)
    _test_counter: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _next_test_id(self) -> int:
        self._test_counter += 1
        return self._test_counter

    def _build_csv_path(self, test_id: int, started_at: datetime) -> Path:
        filename = (
            f"prueba_humedad_{test_id:02d}_"
            f"{started_at.strftime('%Y%m%d_%H%M%S')}.csv"
        )
        return self.output_dir / filename

    async def _set_humidity_actuators(self, state: bool) -> None:
        """Activa/desactiva ambos actuadores exclusivamente para la prueba."""
        await self.plc.write_value(HUMIDIFIER_WRITE_NODE, state)
        try:
            await self.plc.write_value(MISTER_WRITE_NODE, state)
        except Exception:
            # Si el segundo actuador falla al cambiar de estado, intentamos
            # dejar ambos apagados antes de propagar el error.
            try:
                await self.plc.write_value(HUMIDIFIER_WRITE_NODE, False)
            except Exception:
                pass
            raise

    async def _snapshot(self, elapsed_seconds: float) -> dict[str, Any]:
        """
        Lee directamente los nodos necesarios para el experimento.

        No usamos latest_values porque el loop normal de monitorización puede
        tener un intervalo diferente al muestreo experimental.
        """
        values: dict[str, Any] = {}
        node_names = (
            "temperaturaExt",
            "humedad_ext",
            "humedadSHT41",
            HUMIDIFIER_STATUS_NODE,
            MISTER_STATUS_NODE,
        )

        for name in node_names:
            try:
                values[name] = await self.plc.read_value(name)
            except Exception:
                values[name] = None

        return {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "elapsed_seconds": round(elapsed_seconds, 3),
            "temperature_ext": values["temperaturaExt"],
            "humidity_ext": values["humedad_ext"],
            "humidity_int": values["humedadSHT41"],
            "humidifier": values[HUMIDIFIER_STATUS_NODE],
            "mister": values[MISTER_STATUS_NODE],
        }

    @staticmethod
    def _as_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _update_result_metrics(
        self,
        result: HumidityExperimentResult,
        row: dict[str, Any],
    ) -> None:
        humidity = self._as_float(row["humidity_int"])
        elapsed = float(row["elapsed_seconds"])

        if humidity is None:
            return

        if result.initial_humidity is None:
            result.initial_humidity = humidity

        if result.maximum_humidity is None or humidity > result.maximum_humidity:
            result.maximum_humidity = humidity

        if result.time_to_92 is None and humidity >= HUMIDITY_LOWER_THRESHOLD:
            result.time_to_92 = elapsed

        if result.time_to_94 is None and humidity >= HUMIDITY_UPPER_THRESHOLD:
            result.time_to_94 = elapsed

    async def _run(self) -> None:
        test_id = self._next_test_id()
        started_at = datetime.now()
        result = HumidityExperimentResult(test_id=test_id, started_at=started_at)
        self.current_result = result

        csv_path = self._build_csv_path(test_id, started_at)
        result.csv_path = str(csv_path)
        started_monotonic = asyncio.get_running_loop().time()
        actuation_finished = False

        print(f"🧪 Iniciando prueba experimental #{test_id}")
        print(f"   Duración: {self.test_duration:.0f} s")
        print(f"   Activación: {self.actuation_duration:.0f} s")
        print(f"   CSV: {csv_path}")

        try:
            with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=CSV_HEADER)
                writer.writeheader()

                # Primera medición: establece las condiciones iniciales ANTES
                # de encender los actuadores.
                initial_elapsed = asyncio.get_running_loop().time() - started_monotonic
                row = await self._snapshot(initial_elapsed)
                writer.writerow(row)
                csv_file.flush()
                self._update_result_metrics(result, row)

                # Prueba piloto: una única activación de 35 s.
                await self._set_humidity_actuators(True)
                print("💧 Humidificador + mister: ON")

                while True:
                    elapsed = asyncio.get_running_loop().time() - started_monotonic
                    if elapsed >= self.test_duration:
                        break

                    if not actuation_finished and elapsed >= self.actuation_duration:
                        await self._set_humidity_actuators(False)
                        actuation_finished = True
                        print("⏹️ Humidificador + mister: OFF")

                    row = await self._snapshot(elapsed)
                    writer.writerow(row)
                    csv_file.flush()
                    self._update_result_metrics(result, row)

                    remaining = self.sample_interval
                    await asyncio.sleep(remaining)

                # Seguridad: asegurar OFF al terminar.
                await self._set_humidity_actuators(False)

        except asyncio.CancelledError:
            try:
                await self._set_humidity_actuators(False)
            finally:
                raise
        finally:
            result.finished_at = datetime.now()
            self.running = False
            self._task = None

            print(f"✅ Prueba #{test_id} finalizada")
            print(f"   Humedad inicial: {result.initial_humidity}")
            print(f"   Tiempo a 92 %: {result.time_to_92}")
            print(f"   Tiempo a 94 %: {result.time_to_94}")
            print(f"   Humedad máxima: {result.maximum_humidity}")
            print(f"   Datos: {result.csv_path}")

    def start(self) -> None:
        """Inicia la prueba sin bloquear el servidor FastAPI."""
        if self.running:
            raise RuntimeError("Ya existe una prueba experimental en ejecución")

        self.running = True
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Detiene la prueba y deja los actuadores experimentales apagados."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def status(self) -> dict[str, Any]:
        result = self.current_result

        if result is None:
            return {"running": False, "result": None}

        return {
            "running": self.running,
            "result": {
                "test_id": result.test_id,
                "started_at": result.started_at.isoformat(),
                "finished_at": result.finished_at.isoformat() if result.finished_at else None,
                "initial_humidity": result.initial_humidity,
                "time_to_92": result.time_to_92,
                "time_to_94": result.time_to_94,
                "maximum_humidity": result.maximum_humidity,
                "csv_path": result.csv_path,
            },
        }
