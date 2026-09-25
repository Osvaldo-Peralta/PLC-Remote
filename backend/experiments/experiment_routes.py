from fastapi import APIRouter, HTTPException
from .humidity_experiment import HumidityExperiment


router = APIRouter(
    prefix="/experiments/humidity",
    tags=["Experimentos"],
)


# La instancia se asigna desde monitor.py durante startup.
humidity_experiment: HumidityExperiment | None = None


def configure_humidity_experiment(plc) -> HumidityExperiment:
    global humidity_experiment
    humidity_experiment = HumidityExperiment(plc=plc)
    return humidity_experiment


@router.post("/start")
async def start_humidity_experiment():
    if humidity_experiment is None:
        raise HTTPException(status_code=503, detail="Experimento no inicializado")

    if humidity_experiment.running:
        raise HTTPException(status_code=409, detail="Ya existe una prueba en ejecución")

    humidity_experiment.start()
    return {
        "status": "ok",
        "message": "Prueba piloto iniciada",
    }


@router.get("/status")
async def humidity_experiment_status():
    if humidity_experiment is None:
        raise HTTPException(status_code=503, detail="Experimento no inicializado")

    return {
        "status": "ok",
        **humidity_experiment.status(),
    }


@router.post("/stop")
async def stop_humidity_experiment():
    if humidity_experiment is None:
        raise HTTPException(status_code=503, detail="Experimento no inicializado")

    if not humidity_experiment.running:
        return {
            "status": "ok",
            "message": "No hay una prueba en ejecución",
        }

    await humidity_experiment.stop()
    return {
        "status": "ok",
        "message": "Prueba piloto detenida",
    }
