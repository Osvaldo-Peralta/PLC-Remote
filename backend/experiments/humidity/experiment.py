from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from .controller import HumidityController
from .models import ExperimentResult, ExperimentState, SensorSample
from .policy import TARGET_MAX, TARGET_MIN, decide
from .recorder import CSVRecorder
from .sampler import HumiditySampler


MAX_DURATION_SECONDS = 30 * 60
SAMPLE_INTERVAL_SECONDS = 1.0
POST_HUMIDIFICATION_WAIT_SECONDS = 10 * 60


class HumidityExperiment:
    """Orchestrates one complete humidity-control execution."""

    def __init__(self, plc, output_dir: str | Path):
        self.plc = plc
        self.sampler = HumiditySampler(plc)
        self.controller = HumidityController(plc)
        self.output_dir = Path(output_dir)

        self.state = ExperimentState.IDLE
        self.experiment_id: Optional[str] = None
        self.task: Optional[asyncio.Task] = None
        self.stop_event = asyncio.Event()
        # A one-item queue preserves the newest sample without edge-triggered
        # set()/clear() races or an ever-growing backlog during long actuator waits.
        self._sample_queue: asyncio.Queue[SensorSample] = asyncio.Queue(maxsize=1)
        self.target_event = asyncio.Event()

        self.latest_sample: Optional[SensorSample] = None
        self.initial_humidity: Optional[float] = None
        self.target_humidity: Optional[float] = None
        self.time_to_target_seconds: Optional[float] = None
        self.cycles = 0
        self.max_humidity: Optional[float] = None
        self.max_humidity_elapsed_seconds: Optional[float] = None
        self.result: Optional[ExperimentResult] = None
        self.error: Optional[str] = None
        self.error_code: Optional[str] = None
        self.error_stage: Optional[str] = None
        self.cleanup_errors: list[str] = []
        self.outputs_off_write_confirmed: Optional[bool] = None
        self.started_at: Optional[datetime] = None
        self.finished_at: Optional[datetime] = None
        self.recorder: Optional[CSVRecorder] = None
        self._started_monotonic: Optional[float] = None
        self._sampling_task: Optional[asyncio.Task] = None

    @property
    def active(self) -> bool:
        return self.task is not None and not self.task.done()

    def status_snapshot(self) -> dict:
        elapsed = 0.0
        if self._started_monotonic is not None and self.active:
            elapsed = time.monotonic() - self._started_monotonic
        elif self.result and self.started_at and self.finished_at:
            elapsed = (self.finished_at - self.started_at).total_seconds()

        remaining_wait = None
        current_action = self.state.value
        return {
            "experiment_id": self.experiment_id,
            "status": self.state.value,
            "active": self.active,
            "elapsed_seconds": round(min(elapsed, MAX_DURATION_SECONDS), 3),
            "max_duration_seconds": MAX_DURATION_SECONDS,
            "initial_humidity": self.initial_humidity,
            "current_humidity": self.latest_sample.humidity_inside if self.latest_sample else None,
            "target_humidity": self.target_humidity,
            "time_to_target_seconds": self.time_to_target_seconds,
            "cycles": self.cycles,
            "current_action": current_action,
            "remaining_wait_seconds": remaining_wait,
            "target_reached": self.state == ExperimentState.TARGET_REACHED,
            "csv_path": str(self.recorder.path) if self.recorder and self.recorder.path else (
                self.result.csv_path if self.result else None
            ),
            "error": self.error,
            "error_code": self.error_code,
            "error_stage": self.error_stage,
            "cleanup_errors": list(self.cleanup_errors),
            # True means all OFF writes were acknowledged, not physical feedback.
            "outputs_off_write_confirmed": self.outputs_off_write_confirmed,
        }

    async def start(self) -> dict:
        if self.active:
            raise RuntimeError("Ya existe una ejecución de experimento activa")

        self.experiment_id = uuid.uuid4().hex[:12]
        self.stop_event = asyncio.Event()
        self._sample_queue = asyncio.Queue(maxsize=1)
        self.target_event = asyncio.Event()
        self.result = None
        self.error = None
        self.error_code = None
        self.error_stage = None
        self.cleanup_errors = []
        self.outputs_off_write_confirmed = None
        self.initial_humidity = None
        self.target_humidity = None
        self.time_to_target_seconds = None
        self.cycles = 0
        self.max_humidity = None
        self.max_humidity_elapsed_seconds = None
        self.started_at = datetime.now()
        self.finished_at = None
        self._started_monotonic = time.monotonic()
        self._next_sample_deadline = self._started_monotonic
        self.state = ExperimentState.MONITORING

        self.task = asyncio.create_task(self._run())
        return self.status_snapshot()

    async def stop(self) -> None:
        if not self.active:
            return
        self.stop_event.set()
        await self.task

    async def _run(self) -> None:
        recorder = CSVRecorder(self.output_dir, self.experiment_id)
        self.recorder = recorder
        self._sampling_task = asyncio.create_task(self._sampling_loop())

        try:
            await recorder.open()
            # Wait for the first direct PLC sample before making a decision.
            await self._wait_for_sample_or_stop()
            if self.stop_event.is_set():
                if self.error is None:
                    self.state = ExperimentState.STOPPED
                return

            while not self.stop_event.is_set():
                if self._elapsed() >= MAX_DURATION_SECONDS:
                    self.state = ExperimentState.TIMEOUT
                    break

                sample = self.latest_sample
                if sample is None:
                    await self._wait_for_sample_or_stop()
                    continue

                decision = decide(sample.humidity_inside)

                if decision.action.value == "finish":
                    self._mark_target(sample)
                    self.state = ExperimentState.TARGET_REACHED
                    break

                if decision.action.value == "humidify":
                    self.cycles += 1
                    self.state = ExperimentState.HUMIDIFYING
                    await self.controller.set_humidification(True)
                    try:
                        outcome = await self._wait_until(
                            decision.duration_seconds or 0.0,
                            interrupt_on_target=True,
                        )
                    finally:
                        await self.controller.set_humidification(False)

                    if outcome == "target":
                        self.state = ExperimentState.TARGET_REACHED
                        break
                    if outcome in {"stopped", "error"}:
                        self.state = ExperimentState.ERROR if self.error else ExperimentState.STOPPED
                        break
                    if self._elapsed() >= MAX_DURATION_SECONDS:
                        self.state = ExperimentState.TIMEOUT
                        break

                    # Ten-minute recovery/observation period after humidification.
                    self.state = ExperimentState.WAITING
                    outcome = await self._wait_until(
                        POST_HUMIDIFICATION_WAIT_SECONDS,
                        interrupt_on_target=True,
                    )
                    if outcome == "target":
                        self.state = ExperimentState.TARGET_REACHED
                        break
                    if outcome in {"stopped", "error"}:
                        self.state = ExperimentState.ERROR if self.error else ExperimentState.STOPPED
                        break
                    if self._elapsed() >= MAX_DURATION_SECONDS:
                        self.state = ExperimentState.TIMEOUT
                        break
                    self.state = ExperimentState.MONITORING
                    continue

                if decision.action.value == "extract":
                    self.state = ExperimentState.EXTRACTING
                    await self.controller.set_extractor(True)
                    try:
                        outcome = await self._wait_until(
                            decision.duration_seconds or 0.0,
                            interrupt_on_target=True,
                        )
                    finally:
                        await self.controller.set_extractor(False)

                    if outcome == "target":
                        self.state = ExperimentState.TARGET_REACHED
                        break
                    if outcome in {"stopped", "error"}:
                        self.state = ExperimentState.ERROR if self.error else ExperimentState.STOPPED
                        break
                    if self._elapsed() >= MAX_DURATION_SECONDS:
                        self.state = ExperimentState.TIMEOUT
                        break
                    self.state = ExperimentState.MONITORING
                    continue

                # MONITOR: 94 < H <= 110. Keep sampling until policy changes.
                self.state = ExperimentState.MONITORING
                await self._wait_for_sample_or_stop()

            if self.stop_event.is_set() and self.state not in {
                ExperimentState.TARGET_REACHED,
                ExperimentState.TIMEOUT,
                ExperimentState.ERROR,
            }:
                self.state = ExperimentState.STOPPED

        except Exception as exc:
            self._record_error(exc, stage="execution")
        finally:
            try:
                await self.controller.stop_all()
                self.outputs_off_write_confirmed = True
            except Exception as exc:
                self.cleanup_errors.append(str(exc))
                self.outputs_off_write_confirmed = False
                # Preserve the first error; append shutdown failure separately.
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
            self.result = ExperimentResult(
                experiment_id=self.experiment_id,
                status=self.state,
                started_at=self.started_at,
                finished_at=self.finished_at,
                initial_humidity=self.initial_humidity,
                final_humidity=self.latest_sample.humidity_inside if self.latest_sample else None,
                target_humidity=self.target_humidity,
                time_to_target_seconds=self.time_to_target_seconds,
                cycles=self.cycles,
                max_humidity=self.max_humidity,
                max_humidity_elapsed_seconds=self.max_humidity_elapsed_seconds,
                csv_path=str(recorder.path) if recorder.path else None,
                error=self.error,
            )

    async def _sampling_loop(self) -> None:
        while not self.stop_event.is_set():
            elapsed = self._elapsed()
            try:
                sample = await self.sampler.sample(elapsed)
                self.latest_sample = sample
                if self.initial_humidity is None:
                    self.initial_humidity = sample.humidity_inside

                if self.max_humidity is None or sample.humidity_inside > self.max_humidity:
                    self.max_humidity = sample.humidity_inside
                    self.max_humidity_elapsed_seconds = sample.elapsed_seconds

                if TARGET_MIN <= sample.humidity_inside <= TARGET_MAX:
                    self._mark_target(sample)

                if self.recorder:
                    await self.recorder.record(sample)
            except Exception as exc:
                self._record_error(exc, stage="sampling")
                self.stop_event.set()
                self.state = ExperimentState.ERROR
                return

            # Keep only the freshest sample for the decision loop. Sampling
            # continues during actuator activation and the ten-minute wait.
            if self._sample_queue.full():
                try:
                    self._sample_queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                self._sample_queue.put_nowait(sample)
            except asyncio.QueueFull:
                # Defensive fallback; the queue is drained immediately above.
                pass

            if self._elapsed() >= MAX_DURATION_SECONDS:
                return

            # Start-to-start cadence: PLC read duration is included in the
            # requested one-second interval rather than added to it.
            if not hasattr(self, "_next_sample_deadline") or self._next_sample_deadline is None:
                self._next_sample_deadline = time.monotonic() + SAMPLE_INTERVAL_SECONDS
            else:
                self._next_sample_deadline += SAMPLE_INTERVAL_SECONDS
            sleep_for = self._next_sample_deadline - time.monotonic()
            if sleep_for > 0:
                try:
                    await asyncio.wait_for(self.stop_event.wait(), timeout=sleep_for)
                except asyncio.TimeoutError:
                    pass
            else:
                # Do not accumulate drift if PLC reads take longer than a second.
                self._next_sample_deadline = time.monotonic()

    def _record_error(self, exc: Exception, stage: str) -> None:
        """Keep the first failure as the primary cause and classify it."""
        message = str(exc)
        if self.error is None:
            self.error = message
            upper = message.upper()
            if (
                "FAILED TO SEND REQUEST" in upper
                or "CONNECTION" in upper
                or "SERVER" in upper
            ):
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
            # Secondary failures must not overwrite the original cause.
            self.cleanup_errors.append(f"Secondary failure during {stage}: {message}")

    def _mark_target(self, sample: SensorSample) -> None:
        if self.time_to_target_seconds is None:
            self.target_humidity = sample.humidity_inside
            self.time_to_target_seconds = sample.elapsed_seconds
            self.target_event.set()

    async def _wait_for_sample_or_stop(self) -> None:
        """Wait for the newest sample, manual stop, or the global deadline."""
        remaining = MAX_DURATION_SECONDS - self._elapsed()
        if self.stop_event.is_set() or remaining <= 0:
            return

        sample_wait = asyncio.create_task(self._sample_queue.get())
        stop_wait = asyncio.create_task(self.stop_event.wait())
        done, pending = await asyncio.wait(
            {sample_wait, stop_wait},
            timeout=remaining,
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        # If both finished at once, retrieving the sample is harmless: the
        # latest sample is also stored in self.latest_sample for status/reporting.
        for task in done:
            try:
                task.result()
            except asyncio.CancelledError:
                pass

    async def _wait_until(self, seconds: float, interrupt_on_target: bool) -> str:
        """Wait for an actuator duration, manual stop, target, or 30-min limit."""
        deadline = time.monotonic() + seconds
        while True:
            remaining = min(deadline - time.monotonic(), MAX_DURATION_SECONDS - self._elapsed())
            if remaining <= 0:
                return "duration"

            stop_wait = asyncio.create_task(self.stop_event.wait())
            waits = {stop_wait}
            target_wait = None
            if interrupt_on_target:
                target_wait = asyncio.create_task(self.target_event.wait())
                waits.add(target_wait)

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
            if self.error is not None or self.state == ExperimentState.ERROR:
                return "error"
            if self.stop_event.is_set():
                return "stopped"
            if interrupt_on_target and self.target_event.is_set():
                return "target"

    def _elapsed(self) -> float:
        return 0.0 if self._started_monotonic is None else time.monotonic() - self._started_monotonic
