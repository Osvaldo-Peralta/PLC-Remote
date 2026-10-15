from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .experiment import (
    DEFAULT_MAX_DURATION_SECONDS,
    HumidityTargetAttainmentExperiment,
)

router = APIRouter(
    prefix="/experiments/humidity/target-attainment",
    tags=["humidity-target-attainment"],
)

_experiment: Optional[HumidityTargetAttainmentExperiment] = None


class TargetAttainmentStartRequest(BaseModel):
    max_duration_seconds: int = Field(
        default=DEFAULT_MAX_DURATION_SECONDS,
        ge=60,
        le=7200,
        description="Tiempo máximo de ejecución, entre 60 y 7200 segundos.",
    )
    stability_seconds: int = Field(
        default=30,
        ge=0,
        le=300,
        description="Tiempo continuo sobre cada umbral necesario para confirmarlo.",
    )


def configure_target_attainment_experiment(plc) -> None:
    global _experiment
    _experiment = HumidityTargetAttainmentExperiment(plc, "experiments/data")


def get_target_attainment_experiment() -> HumidityTargetAttainmentExperiment:
    if _experiment is None:
        raise RuntimeError("Experimento de alcance de umbrales no configurado")
    return _experiment


@router.post("/start")
async def start_target_attainment_experiment(request: TargetAttainmentStartRequest):
    experiment = get_target_attainment_experiment()
    if experiment.active:
        raise HTTPException(status_code=409, detail="Ya existe una ejecución de alcance de umbrales activa")

    # The same physical actuators cannot be controlled by two experiments at once.
    from experiments.experiment_routes import get_experiment

    if get_experiment().active:
        raise HTTPException(status_code=409, detail="El experimento de humedad de 30 minutos está activo")

    try:
        return await experiment.start(
            max_duration_seconds=request.max_duration_seconds,
            stability_seconds=request.stability_seconds,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/status")
async def target_attainment_status():
    return get_target_attainment_experiment().status_snapshot()


@router.post("/stop")
async def stop_target_attainment_experiment():
    experiment = get_target_attainment_experiment()
    if experiment.active:
        await experiment.stop()
    return experiment.status_snapshot()


async def shutdown_target_attainment_experiment() -> None:
    if _experiment is not None and _experiment.active:
        await _experiment.stop()
