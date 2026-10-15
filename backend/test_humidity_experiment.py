"""Offline integration tests for the humidity experiment using a fake PLC."""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from experiments.humidity import experiment as experiment_module
from experiments.humidity.experiment import HumidityExperiment
from experiments.humidity.models import ExperimentState, SensorSample


class FakePLC:
    def __init__(self) -> None:
        self.outputs = {
            "extractor_rw": False,
            "humificador_rw": False,
            "mister_rw": False,
        }
        self.writes: list[tuple[str, bool]] = []
        self.fail_writes = False

    async def write_value(self, name, value, variant_type=None):
        if self.fail_writes:
            raise RuntimeError("Failed to send request to OPC UA server")
        self.outputs[name] = bool(value)
        self.writes.append((name, bool(value)))


class SequenceSampler:
    def __init__(self, plc: FakePLC, humidity_sequence: list[float], error: bool = False):
        self.plc = plc
        self.humidity_sequence = humidity_sequence
        self.error = error
        self.calls = 0

    async def sample(self, elapsed_seconds: float) -> SensorSample:
        self.calls += 1
        if self.error:
            raise RuntimeError("fallo simulado de lectura")
        index = min(self.calls - 1, len(self.humidity_sequence) - 1)
        humidity = self.humidity_sequence[index]
        return SensorSample(
            timestamp=datetime.now(),
            elapsed_seconds=elapsed_seconds,
            humidity_inside=humidity,
            humidity_outside=60.0,
            temperature_inside=25.0,
            temperature_outside=25.0,
            extractor=self.plc.outputs["extractor_rw"],
            humidifier=self.plc.outputs["humificador_rw"],
            mister=self.plc.outputs["mister_rw"],
        )


class HumidityExperimentTests(unittest.IsolatedAsyncioTestCase):
    async def _run_experiment(self, humidity_sequence, *, max_duration=5.0, error=False, stop_manually=False):
        plc = FakePLC()
        with tempfile.TemporaryDirectory() as directory:
            experiment = HumidityExperiment(plc, Path(directory))
            experiment.sampler = SequenceSampler(plc, humidity_sequence, error=error)
            with (
                patch.object(experiment_module, "SAMPLE_INTERVAL_SECONDS", 0.01),
                patch.object(experiment_module, "MAX_DURATION_SECONDS", max_duration),
                patch.object(experiment_module, "POST_HUMIDIFICATION_WAIT_SECONDS", 0.05),
            ):
                await experiment.start()
                if stop_manually:
                    await asyncio.sleep(0.04)
                    await experiment.stop()
                else:
                    await asyncio.wait_for(experiment.task, timeout=max_duration + 1.0)
                self.assertIsNotNone(experiment.result)
                self.assertTrue(all(plc.outputs[name] is False for name in plc.outputs))
                self.assertTrue(all(value is False for name, value in plc.writes[-3:]))
                return experiment.result.status, experiment.error

    async def test_manual_stop_turns_all_outputs_off(self):
        status, error = await self._run_experiment([72.9], stop_manually=True)
        self.assertEqual(status, ExperimentState.STOPPED)
        self.assertIsNone(error)

    async def test_target_interrupts_activation_and_turns_outputs_off(self):
        status, error = await self._run_experiment([72.9, 92.4])
        self.assertEqual(status, ExperimentState.TARGET_REACHED)
        self.assertIsNone(error)

    async def test_global_timeout_turns_all_outputs_off(self):
        status, error = await self._run_experiment([80.0], max_duration=0.15)
        self.assertEqual(status, ExperimentState.TIMEOUT)
        self.assertIsNone(error)

    async def test_sampling_error_is_not_misreported_as_manual_stop(self):
        status, error = await self._run_experiment([72.9], error=True)
        self.assertEqual(status, ExperimentState.ERROR)
        self.assertIn("fallo simulado", error or "")

    async def test_primary_error_is_preserved_when_shutdown_also_fails(self):
        plc = FakePLC()
        with tempfile.TemporaryDirectory() as directory:
            experiment = HumidityExperiment(plc, Path(directory))
            experiment.sampler = SequenceSampler(plc, [72.9], error=True)
            # The failure begins in sampling; subsequent OFF writes also fail.
            plc.fail_writes = True
            with (
                patch.object(experiment_module, "SAMPLE_INTERVAL_SECONDS", 0.01),
                patch.object(experiment_module, "MAX_DURATION_SECONDS", 0.2),
            ):
                await experiment.start()
                await asyncio.wait_for(experiment.task, timeout=1.0)

            status = experiment.status_snapshot()
            self.assertEqual(status["status"], ExperimentState.ERROR.value)
            self.assertIn("fallo simulado de lectura", status["error"])
            self.assertTrue(status["cleanup_errors"])
            self.assertFalse(status["outputs_off_write_confirmed"])
            self.assertEqual(status["error_code"], "ERROR_READ")


if __name__ == "__main__":
    unittest.main()
