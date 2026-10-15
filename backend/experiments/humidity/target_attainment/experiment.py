from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..controller import HumidityController
from ..models import ExperimentState, SensorSample
from ..policy import decide
from ..sampler import HumiditySampler
from .evaluator import ThresholdEvaluator
from .recorder import TargetAttainmentRecorder

DEFAULT_MAX_DURATION_SECONDS = 60 * 60
DEFAULT_SAMPLE_INTERVAL_SECONDS = 1.0
POST_HUMIDIFICATION_WAIT_SECONDS = 10 * 60


class HumidityTargetAttainmentExperiment:
    """Measures time to 92% and then 94% without changing the control policy.

    Unlike the fixed-duration experiment, crossing 92% does not end this run.
    The normal policy's 92-94% decision is treated as passive monitoring so
    the second milestone can be observed without forcing additional humidity.
    """

    def __init__(
        self,
        plc,
        output_dir: str | Path,
        *,
        max_duration_seconds: float = DEFAULT_MAX_DURATION_SECONDS,
        stability_seconds: float = 30.0,
        sample_interval_seconds: float = DEFAULT_SAMPLE_INTERVAL_SECONDS,
    ):
        if max_duration_seconds <= 0:
            raise ValueError("max_duration_seconds debe ser positivo")
        if sample_interval_seconds <= 0:
            raise ValueError("sample_interval_seconds debe ser positivo")
        self.plc = plc
        self.sampler = HumiditySampler(plc)
        self.controller = HumidityController(plc)
        self.output_dir = Path(output_dir)
        self.default_max_duration_seconds = float(max_duration_seconds)
        self.max_duration_seconds = self.default_max_duration_seconds
        self.sample_interval_seconds = float(sample_interval_seconds)
        self.evaluator = ThresholdEvaluator(stability_seconds)

        self.state = ExperimentState.IDLE
        self.experiment_id: Optional[str] = None
        self.started_at: Optional[datetime] = None
        self.finished_at: Optional[datetime] = None
        self._started_monotonic: Optional[float] = None
        self.task: Optional[asyncio.Task] = None
        self._sampling_task: Optional[asyncio.Task] = None
        self.stop_event = asyncio.Event()
        self.first_crossing_92_event = asyncio.Event()
        self.target_94_stable_event = asyncio.Event()
        self._sample_queue: asyncio.Queue[SensorSample] = asyncio.Queue(maxsize=1)
        self.latest_sample: Optional[SensorSample] = None
        self.initial_humidity: Optional[float] = None
        self.initial_actuator_state: Optional[dict[str, bool]] = None
        self.sensor_values_unchanged_samples = 0
        self._previous_sensor_values: Optional[tuple[float, float, float, float]] = None
        self._sensor_stall_warning_emitted = False
        self.maximum_humidity: Optional[float] = None
        self.maximum_humidity_elapsed_seconds: Optional[float] = None
        self.error: Optional[str] = None
        self.error_code: Optional[str] = None
        self.error_stage: Optional[str] = None
        self.cleanup_errors: list[str] = []
        self.outputs_off_write_confirmed: Optional[bool] = None
        self.csv_path: Optional[str] = None
        self.recorder: Optional[TargetAttainmentRecorder] = None

    @property
    def active(self) -> bool:
        return self.task is not None and not self.task.done()

    async def start(
        self,
        *,
        max_duration_seconds: Optional[float] = None,
        stability_seconds: Optional[float] = None,
    ) -> dict:
        if self.active:
            raise RuntimeError("Ya existe un experimento de alcance de umbral activo")
        effective_max_duration = (
            max_duration_seconds
            if max_duration_seconds is not None
            else self.default_max_duration_seconds
        )
        if effective_max_duration <= 0:
            raise ValueError("max_duration_seconds debe ser positivo")
        self.max_duration_seconds = float(effective_max_duration)
        # Reset milestone state for every run, retaining configured defaults
        # when the caller does not override the stability interval.
        effective_stability = (
            stability_seconds
            if stability_seconds is not None
            else self.evaluator.stability_seconds
        )
        self.evaluator = ThresholdEvaluator(effective_stability)

        self.experiment_id = uuid.uuid4().hex[:12]
        self.started_at = datetime.now()
        self.finished_at = None
        self._started_monotonic = time.monotonic()
        self._next_sample_deadline = self._started_monotonic
        self.stop_event = asyncio.Event()
        self.first_crossing_92_event = asyncio.Event()
        self.target_94_stable_event = asyncio.Event()
        self._sample_queue = asyncio.Queue(maxsize=1)
        self.latest_sample = None
        self.initial_humidity = None
        self.initial_actuator_state = None
        self.sensor_values_unchanged_samples = 0
        self._previous_sensor_values = None
        self._sensor_stall_warning_emitted = False
        self.maximum_humidity = None
        self.maximum_humidity_elapsed_seconds = None
        self.error = None
        self.error_code = None
        self.error_stage = None
        self.cleanup_errors = []
        self.outputs_off_write_confirmed = None
        self.csv_path = None
        self.recorder = None
        self.state = ExperimentState.MONITORING
        print(
            f"[target-attainment] starting id={self.experiment_id} "
            f"max_duration={self.max_duration_seconds:.0f}s "
            f"stability={self.evaluator.stability_seconds:.0f}s targets=92%,94%"
        )
        self.task = asyncio.create_task(self._run())
        return self.status_snapshot()

    async def stop(self) -> None:
        if not self.active:
            return
        self.stop_event.set()
        await self.task

    def _elapsed(self) -> float:
        if self._started_monotonic is None:
            return 0.0
        return time.monotonic() - self._started_monotonic

    def status_snapshot(self) -> dict:
        milestones = self.evaluator.snapshot()
        elapsed = self._elapsed() if self.active else (
            (self.finished_at - self.started_at).total_seconds()
            if self.started_at and self.finished_at else 0.0
        )
        return {
            "experiment_id": self.experiment_id,
            "status": self.state.value,
            "active": self.active,
            "elapsed_seconds": round(min(elapsed, self.max_duration_seconds), 3),
            "max_duration_seconds": self.max_duration_seconds,
            "stability_seconds": self.evaluator.stability_seconds,
            "initial_humidity": self.initial_humidity,
            "initial_actuator_state": self.initial_actuator_state,
            "sensor_values_unchanged_samples": self.sensor_values_unchanged_samples,
            "current_humidity": self.latest_sample.humidity_inside if self.latest_sample else None,
            "maximum_humidity": self.maximum_humidity,
            "maximum_humidity_elapsed_seconds": self.maximum_humidity_elapsed_seconds,
            "milestones": milestones["milestones"],
            "csv_path": self.csv_path,
            "error": self.error,
            "error_code": self.error_code,
            "error_stage": self.error_stage,
            "cleanup_errors": list(self.cleanup_errors),
            # True means OFF writes were acknowledged, not physical actuator feedback.
            "outputs_off_write_confirmed": self.outputs_off_write_confirmed,
        }

    async def _run(self) -> None:
        assert self.experiment_id is not None
        recorder = TargetAttainmentRecorder(self.output_dir, self.experiment_id)
        self.recorder = recorder
        try:
            self.csv_path = str(await recorder.open())
            self._sampling_task = asyncio.create_task(self._sampling_loop())
            await self._wait_for_sample_or_stop()

            while not self.stop_event.is_set() and self.error is None:
                if self.evaluator.milestones[94.0].confirmed:
                    self.state = ExperimentState.TARGET_REACHED
                    break
                if self._elapsed() >= self.max_duration_seconds:
                    self.state = ExperimentState.TIMEOUT
                    break

                sample = self.latest_sample
                if sample is None:
                    await self._wait_for_sample_or_stop()
                    continue

                decision = decide(sample.humidity_inside)
                action = decision.action.value

                if action == "humidify":
                    self.state = ExperimentState.HUMIDIFYING
                    print(
                        f"[target-attainment] id={self.experiment_id} "
                        f"control=HUMIDIFY humidity={sample.humidity_inside:.3f}% "
                        f"duration={decision.duration_seconds or 0.0:.1f}s "
                        f"reason={decision.reason}"
                    )
                    await self.controller.set_humidification(True)
                    try:
                        outcome = await self._wait_until(
                            decision.duration_seconds or 0.0,
                            interrupt_on_92=True,
                        )
                    finally:
                        await self.controller.set_humidification(False)
                        print(
                            f"[target-attainment] id={self.experiment_id} "
                            "control=HUMIDIFY_OFF"
                        )

                    if outcome == "timeout":
                        self.state = ExperimentState.TIMEOUT
                        break
                    if outcome in {"stopped", "error"}:
                        break
                    # Keep the existing ten-minute post-actuation observation
                    # interval, even if 92% is crossed during activation.
                    self.state = ExperimentState.WAITING
                    outcome = await self._wait_until(
                        POST_HUMIDIFICATION_WAIT_SECONDS,
                        interrupt_on_92=False,
                    )
                    if outcome == "timeout":
                        self.state = ExperimentState.TIMEOUT
                        break
                    if outcome in {"stopped", "error"}:
                        break
                    self.state = ExperimentState.MONITORING
                    continue

                if action == "extract":
                    self.state = ExperimentState.EXTRACTING
                    print(
                        f"[target-attainment] id={self.experiment_id} "
                        f"control=EXTRACT humidity={sample.humidity_inside:.3f}% "
                        f"duration={decision.duration_seconds or 0.0:.1f}s "
                        f"reason={decision.reason}"
                    )
                    await self.controller.set_extractor(True)
                    try:
                        outcome = await self._wait_until(
                            decision.duration_seconds or 0.0,
                            interrupt_on_92=False,
                        )
                    finally:
                        await self.controller.set_extractor(False)
                        print(
                            f"[target-attainment] id={self.experiment_id} "
                            "control=EXTRACT_OFF"
                        )
                    if outcome in {"stopped", "error", "timeout"}:
                        break
                    self.state = ExperimentState.MONITORING
                    continue

                # In the 92-94% band, the existing policy says FINISH. For this
                # measurement phase, FINISH means no actuation and continued
                # observation, so the 94% milestone can still be measured.
                self.state = ExperimentState.MONITORING
                await self._wait_for_sample_or_stop()

            if self.error:
                self.state = ExperimentState.ERROR
            elif self.stop_event.is_set() and self.state not in {
                ExperimentState.TARGET_REACHED, ExperimentState.TIMEOUT, ExperimentState.ERROR
            }:
                self.state = ExperimentState.STOPPED
        except Exception as exc:
            self._record_error(exc, stage="execution")
            self.state = ExperimentState.ERROR
        finally:
            try:
                await self.controller.stop_all()
                self.outputs_off_write_confirmed = True
            except Exception as exc:
                self.outputs_off_write_confirmed = False
                self.cleanup_errors.append(str(exc))
                if self.error is None:
                    self._record_error(exc, stage="shutdown")
                self.state = ExperimentState.ERROR

            if self._sampling_task:
                self._sampling_task.cancel()
                try:
                    await self._sampling_task
                except asyncio.CancelledError:
                    pass
                self._sampling_task = None
            self.finished_at = datetime.now()
            await recorder.close()
            print(
                f"[target-attainment] id={self.experiment_id} status={self.state.value} "
                f"time_to_92={self.evaluator.milestones[92.0].time_to_target_seconds} "
                f"time_to_94={self.evaluator.milestones[94.0].time_to_target_seconds} "
                f"error={self.error or '-'} csv={self.csv_path}"
            )

    async def _sampling_loop(self) -> None:
        # Match the proven fixed-duration experiment's start-to-start cadence:
        # PLC read time is included in the one-second interval, not added to it.
        while not self.stop_event.is_set() and self._elapsed() < self.max_duration_seconds:
            elapsed = self._elapsed()
            try:
                sample = await self.sampler.sample(elapsed)
                self.latest_sample = sample
                if self.initial_humidity is None:
                    self.initial_humidity = sample.humidity_inside
                    self.initial_actuator_state = {
                        "extractor": sample.extractor,
                        "humidifier": sample.humidifier,
                        "mister": sample.mister,
                    }
                    print(
                        f"[target-attainment] id={self.experiment_id} "
                        f"initial_sample humidity={sample.humidity_inside:.3f}% "
                        f"outputs={self.initial_actuator_state}"
                    )
                    if any(self.initial_actuator_state.values()):
                        print(
                            f"[target-attainment] WARNING id={self.experiment_id} "
                            "one or more actuators were already ON in the first sample; "
                            "check the initial plant state before interpreting this run"
                        )

                sensor_values = (
                    sample.humidity_inside,
                    sample.humidity_outside,
                    sample.temperature_inside,
                    sample.temperature_outside,
                )
                if sensor_values == self._previous_sensor_values:
                    self.sensor_values_unchanged_samples += 1
                else:
                    self.sensor_values_unchanged_samples = 1
                    self._sensor_stall_warning_emitted = False
                self._previous_sensor_values = sensor_values

                events = self.evaluator.update(sample.humidity_inside, sample.elapsed_seconds)
                if (
                    self.sensor_values_unchanged_samples >= 5
                    and not self._sensor_stall_warning_emitted
                ):
                    warning_event = "SENSOR_VALUES_UNCHANGED_5_SAMPLES"
                    events.append(warning_event)
                    self._sensor_stall_warning_emitted = True
                    print(
                        f"[target-attainment] WARNING id={self.experiment_id} "
                        f"the four sensor values have been identical for "
                        f"{self.sensor_values_unchanged_samples} consecutive samples; "
                        "verify PLC values and OPC UA reads"
                    )
                if self.maximum_humidity is None or sample.humidity_inside > self.maximum_humidity:
                    self.maximum_humidity = sample.humidity_inside
                    self.maximum_humidity_elapsed_seconds = sample.elapsed_seconds

                for event in events:
                    if event == "FIRST_CROSSING_92":
                        self.first_crossing_92_event.set()
                        print(
                            f"[target-attainment] id={self.experiment_id} "
                            f"first_crossing_92={sample.elapsed_seconds:.3f}s "
                            f"humidity={sample.humidity_inside:.2f}%"
                        )
                    elif event == "TARGET_92_STABLE":
                        print(
                            f"[target-attainment] id={self.experiment_id} "
                            f"target_92_stable={self.evaluator.milestones[92.0].time_to_target_seconds:.3f}s"
                        )
                    elif event == "FIRST_CROSSING_94":
                        print(
                            f"[target-attainment] id={self.experiment_id} "
                            f"first_crossing_94={sample.elapsed_seconds:.3f}s "
                            f"humidity={sample.humidity_inside:.2f}%"
                        )
                    elif event == "TARGET_94_STABLE":
                        self.target_94_stable_event.set()
                        print(
                            f"[target-attainment] id={self.experiment_id} "
                            f"target_94_stable={self.evaluator.milestones[94.0].time_to_target_seconds:.3f}s"
                        )
                if self.recorder:
                    await self.recorder.record(sample, self.evaluator, events)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._record_error(exc, stage="sampling")
                self.state = ExperimentState.ERROR
                self.stop_event.set()
                return

            if self._sample_queue.full():
                try:
                    self._sample_queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                self._sample_queue.put_nowait(sample)
            except asyncio.QueueFull:
                pass

            if not hasattr(self, "_next_sample_deadline") or self._next_sample_deadline is None:
                self._next_sample_deadline = time.monotonic() + self.sample_interval_seconds
            else:
                self._next_sample_deadline += self.sample_interval_seconds

            sleep_for = self._next_sample_deadline - time.monotonic()
            if sleep_for > 0:
                try:
                    await asyncio.wait_for(self.stop_event.wait(), timeout=sleep_for)
                except asyncio.TimeoutError:
                    pass
            else:
                # Do not accumulate drift if a PLC read takes longer than the interval.
                self._next_sample_deadline = time.monotonic()

    async def _wait_for_sample_or_stop(self) -> None:
        if self.stop_event.is_set() or self._elapsed() >= self.max_duration_seconds:
            return
        sample_wait = asyncio.create_task(self._sample_queue.get())
        stop_wait = asyncio.create_task(self.stop_event.wait())
        target_wait = asyncio.create_task(self.target_94_stable_event.wait())
        remaining = max(0.0, self.max_duration_seconds - self._elapsed())
        done, pending = await asyncio.wait(
            {sample_wait, stop_wait, target_wait},
            timeout=remaining,
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            try:
                task.result()
            except asyncio.CancelledError:
                pass

    async def _wait_until(self, seconds: float, *, interrupt_on_92: bool) -> str:
        deadline = time.monotonic() + seconds
        while True:
            if self.error:
                return "error"
            if self.stop_event.is_set():
                return "stopped"
            remaining = min(deadline - time.monotonic(), self.max_duration_seconds - self._elapsed())
            if remaining <= 0:
                return "timeout" if self._elapsed() >= self.max_duration_seconds else "duration"

            waits = {asyncio.create_task(self.stop_event.wait()), asyncio.create_task(self.target_94_stable_event.wait())}
            if interrupt_on_92:
                waits.add(asyncio.create_task(self.first_crossing_92_event.wait()))
            done, pending = await asyncio.wait(
                waits,
                timeout=remaining,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            if not done:
                return "duration"
            if self.error:
                return "error"
            if self.stop_event.is_set():
                return "stopped"
            if self.target_94_stable_event.is_set():
                return "target"
            if interrupt_on_92 and self.first_crossing_92_event.is_set():
                return "target_92"

    def _record_error(self, exc: Exception, *, stage: str) -> None:
        message = str(exc)
        if self.error is None:
            self.error = message
            upper = message.upper()
            if "FAILED TO SEND REQUEST" in upper or "CONNECTION" in upper or "SERVER" in upper:
                self.error_code = "ERROR_CONNECTION"
            elif "ERROR_WRITE" in upper:
                self.error_code = "ERROR_WRITE"
            elif "ERROR_READ" in upper or stage == "sampling":
                self.error_code = "ERROR_READ"
            elif "ERROR_SHUTDOWN" in upper or stage == "shutdown":
                self.error_code = "ERROR_SHUTDOWN"
            else:
                self.error_code = "ERROR_EXPERIMENT"
            self.error_stage = stage
        else:
            self.cleanup_errors.append(f"Secondary failure during {stage}: {message}")
