from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .humidity.experiment import HumidityExperiment

router = APIRouter(prefix="/experiments/humidity", tags=["humidity-experiment"])

# This module is configured by monitor.py at startup.
_experiment: HumidityExperiment | None = None


def configure_humidity_experiment(plc) -> None:
    global _experiment
    _experiment = HumidityExperiment(plc, "experiments/data")


def get_experiment() -> HumidityExperiment:
    if _experiment is None:
        raise RuntimeError("Experimento de humedad no configurado")
    return _experiment


@router.post("/start")
async def start_humidity_experiment():
    experiment = get_experiment()
    if experiment.active:
        raise HTTPException(status_code=409, detail="Ya existe una ejecución activa")

    # Both experiments use the same PLC actuators; never run them concurrently.
    from experiments.humidity.target_attainment.routes import get_target_attainment_experiment

    if get_target_attainment_experiment().active:
        raise HTTPException(
            status_code=409,
            detail="El experimento de alcance de umbrales está activo",
        )
    return await experiment.start()


@router.get("/status")
async def humidity_experiment_status():
    return get_experiment().status_snapshot()


@router.post("/stop")
async def stop_humidity_experiment():
    experiment = get_experiment()
    if experiment.active:
        await experiment.stop()
    return experiment.status_snapshot()


async def shutdown_humidity_experiment() -> None:
    """Stop the active experiment before the PLC connection is closed."""
    if _experiment is not None and _experiment.active:
        await _experiment.stop()
