"""Offline tests for the second-phase humidity target-attainment experiment."""
from __future__ import annotations

import asyncio
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from experiments.humidity.target_attainment.evaluator import ThresholdEvaluator
from experiments.humidity.target_attainment.experiment import HumidityTargetAttainmentExperiment
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
    def __init__(self, plc: FakePLC, humidity_sequence: list[float]):
        self.plc = plc
        self.humidity_sequence = humidity_sequence
        self.calls = 0

    async def sample(self, elapsed_seconds: float) -> SensorSample:
        index = min(self.calls, len(self.humidity_sequence) - 1)
        self.calls += 1
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


class ThresholdEvaluatorTests(unittest.TestCase):
    def test_first_crossing_is_not_same_as_stable_attainment(self):
        evaluator = ThresholdEvaluator(stability_seconds=3)
        self.assertEqual(evaluator.update(92.2, 0), ["FIRST_CROSSING_92"])
        self.assertEqual(evaluator.update(91.8, 1), [])
        self.assertEqual(evaluator.update(92.4, 2), [])
        self.assertEqual(evaluator.update(92.5, 4), [])
        self.assertEqual(evaluator.update(92.6, 5), ["TARGET_92_STABLE"])
        self.assertEqual(evaluator.milestones[92.0].first_crossing_seconds, 0)
        self.assertEqual(evaluator.milestones[92.0].time_to_target_seconds, 5)

    def test_93_percent_does_not_mark_94_percent_reached(self):
        evaluator = ThresholdEvaluator(stability_seconds=2)
        evaluator.update(93.0, 0)
        evaluator.update(93.0, 1)
        evaluator.update(93.0, 2)
        self.assertTrue(evaluator.milestones[92.0].confirmed)
        self.assertFalse(evaluator.milestones[94.0].confirmed)


class TargetAttainmentExperimentTests(unittest.IsolatedAsyncioTestCase):
    async def test_reaches_both_milestones_in_one_run_and_shuts_outputs_off(self):
        plc = FakePLC()
        with tempfile.TemporaryDirectory() as directory:
            experiment = HumidityTargetAttainmentExperiment(
                plc, Path(directory), max_duration_seconds=1.0,
                stability_seconds=0.02, sample_interval_seconds=0.01,
            )
            experiment.sampler = SequenceSampler(plc, [91.0, 92.2, 93.0, 94.1, 94.3, 94.5])
            await experiment.start()
            await asyncio.wait_for(experiment.task, timeout=2.0)
            result = experiment.status_snapshot()
            self.assertEqual(result["status"], ExperimentState.TARGET_REACHED.value)
            self.assertIsNotNone(result["milestones"]["92"]["first_crossing_seconds"])
            self.assertIsNotNone(result["milestones"]["92"]["time_to_target_seconds"])
            self.assertIsNotNone(result["milestones"]["94"]["first_crossing_seconds"])
            self.assertIsNotNone(result["milestones"]["94"]["time_to_target_seconds"])
            self.assertTrue(result["outputs_off_write_confirmed"])
            self.assertTrue(all(value is False for value in plc.outputs.values()))
            self.assertTrue(Path(result["csv_path"]).exists())

    async def test_93_percent_is_passive_and_does_not_trigger_more_humidification(self):
        plc = FakePLC()
        with tempfile.TemporaryDirectory() as directory:
            experiment = HumidityTargetAttainmentExperiment(
                plc, Path(directory), max_duration_seconds=0.08,
                stability_seconds=0.01, sample_interval_seconds=0.01,
            )
            experiment.sampler = SequenceSampler(plc, [93.0])
            await experiment.start()
            await asyncio.wait_for(experiment.task, timeout=1.0)
            result = experiment.status_snapshot()
            self.assertEqual(result["status"], ExperimentState.TIMEOUT.value)
            self.assertTrue(result["milestones"]["92"]["reached"])
            self.assertFalse(result["milestones"]["94"]["reached"])
            self.assertFalse(any(name == "humificador_rw" and value for name, value in plc.writes))
            self.assertFalse(any(name == "mister_rw" and value for name, value in plc.writes))
            self.assertTrue(all(value is False for value in plc.outputs.values()))

    async def test_constant_sensor_values_are_flagged_in_csv(self):
        plc = FakePLC()
        with tempfile.TemporaryDirectory() as directory:
            experiment = HumidityTargetAttainmentExperiment(
                plc, Path(directory), max_duration_seconds=0.09,
                stability_seconds=30.0, sample_interval_seconds=0.01,
            )
            experiment.sampler = SequenceSampler(plc, [93.0])
            await experiment.start()
            await asyncio.wait_for(experiment.task, timeout=1.0)
            result = experiment.status_snapshot()
            self.assertGreaterEqual(result["sensor_values_unchanged_samples"], 5)
            csv_text = Path(result["csv_path"]).read_text(encoding="utf-8")
            self.assertIn("SENSOR_VALUES_UNCHANGED_5_SAMPLES", csv_text)

    async def test_sampling_failure_is_reported_and_outputs_off_are_attempted(self):
        plc = FakePLC()
        with tempfile.TemporaryDirectory() as directory:
            experiment = HumidityTargetAttainmentExperiment(
                plc, Path(directory), max_duration_seconds=0.2,
                stability_seconds=0.01, sample_interval_seconds=0.01,
            )

            class BrokenSampler:
                async def sample(self, elapsed_seconds):
                    raise RuntimeError("Failed to send request to OPC UA server")

            experiment.sampler = BrokenSampler()
            await experiment.start()
            await asyncio.wait_for(experiment.task, timeout=1.0)
            result = experiment.status_snapshot()
            self.assertEqual(result["status"], ExperimentState.ERROR.value)
            self.assertEqual(result["error_code"], "ERROR_CONNECTION")
            self.assertTrue(result["outputs_off_write_confirmed"])
            self.assertTrue(all(value is False for value in plc.outputs.values()))


if __name__ == "__main__":
    unittest.main()
