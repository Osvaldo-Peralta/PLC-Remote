from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from asyncua import ua
from plc_client import PLCManager
from typing import Any
from config import PLC_ENDPOINT, NODE_DEFINITIONS, TS, RECONNECT_DELAY

# Import del modulo de pruebas
from experiments.experiment_routes import (
    configure_humidity_experiment,
    shutdown_humidity_experiment,
    router as experiment_router,
)

from experiments.response_experiment import response_tracker, RW_TO_STATUS
from experiments.humidity.target_attainment.routes import (
    configure_target_attainment_experiment,
    shutdown_target_attainment_experiment,
    router as target_attainment_router,
)

app = FastAPI()

app.include_router(experiment_router)
app.include_router(target_attainment_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instancia global del PLCManager
plc = PLCManager(PLC_ENDPOINT, reconnect_delay=RECONNECT_DELAY)


@app.on_event("startup")
async def startup_event():
    await plc.connect()
    await plc.initialize_nodes(NODE_DEFINITIONS)
    # Lanza el loop de monitoreo en segundo plano: lee todos los nodos cada
    # TS segundos, los cachea en plc.latest_values y los imprime en
    # terminal (mismo patrón que planta_opcua.py), sin bloquear la API.
    configure_humidity_experiment(plc)
    configure_target_attainment_experiment(plc)
    plc.add_snapshot_callback(response_tracker.observe_snapshot)
    plc.start_monitoring(NODE_DEFINITIONS, ts=TS)


@app.on_event("shutdown")
async def shutdown_event():
    # First request a safe experiment shutdown while OPC UA is still connected.
    await shutdown_humidity_experiment()
    await shutdown_target_attainment_experiment()
    response_tracker.stop()
    plc.remote_snapshot_callback(response_tracker.observe_snapshot)
    await plc.stop_monitoring()
    await plc.disconnect()


def safe_response(name: str, value: Any = None):
    if value is None:
        return {"status": "error", "message": f"No se pudo leer de {name}"}
    return {"status": "ok", "value": value}
async def safe_write(
    name: str,
    value: Any,
    variant_type: ua.VariantType = ua.VariantType.Boolean,
):
    # Para la instrumentación, el nombre recibido es el nodo *_rw y la
    # detección posterior se hará sobre su nodo de estado correspondiente.
    command_id = response_tracker.command_started(
        name,
        bool(value),
        plc.latest_values.get(RW_TO_STATUS[name])
        if name in RW_TO_STATUS
        else None,
    )

    try:
        await plc.write_value(name, value, variant_type)
        plc.latest_values[name] = value

        response = {"status": "ok", "value": value}
        if command_id:
            event = response_tracker.pending.get(command_id)
            response["response_experiment"] = {
                "command_id": command_id,
                "command_timestamp": event["command_timestamp"] if event else None,
            }
        return response
    except Exception as e:
        response_tracker.command_failed(command_id)
        print(f"❌ Error al escribir en '{name}': {e}")
        return {"status": "error", "message": f"No se pudo escribir en {name}"}

# -----
# Snapshot completo
# -----
@app.get("/status")
async def status():
    """Devuelve el último valor cacheado de todos los nodos."""
    return {"status": "ok", "values": plc.latest_values}

# -----
# Sensores (lectura desde cache, actualizado por el loop de fondo)
# -----
@app.get("/humedad_ext")
async def get_humedad_ext():
    return safe_response("humedad_ext", plc.latest_values.get("humedad_ext"))


@app.get("/humedad_sht41")
async def get_humedad_sht41():
    return safe_response("humedadSCD41", plc.latest_values.get("humedadSCD41"))


@app.get("/temperatura_ext")
async def get_temperatura_ext():
    return safe_response("temperaturaExt", plc.latest_values.get("temperaturaExt"))


@app.get("/temperatura_sht41")
async def get_temperatura_sht41():
    return safe_response("temperaturaSCD41", plc.latest_values.get("temperaturaSCD41"))

# -----
# Modo automático
# -----
@app.get("/modo_automatico")
async def get_modo_automatico():
    return safe_response("modoAutomatico", plc.latest_values.get("modoAutomatico"))


@app.post("/modo_automatico/{estado}")
async def set_modo_automatico(estado: bool):
    return await safe_write("modoAutomatico", estado)

# -----
# Actuadores
# -----
@app.get("/extractor")
async def get_extractor():
    # El estado visible del actuador se obtiene del nodo de lectura
    return safe_response(
        "extractor",
        plc.latest_values.get("extractor")
        )


@app.post("/extractor/{estado}")
async def set_extractor(estado: bool):
    # La orden de escritura se envia al nodo especifico de lectura/escritura
    return await safe_write("extractor_rw", estado)


@app.get("/humificador")
async def get_humificador():
    return safe_response(
        "humificador",
        plc.latest_values.get("humificador")
        )


@app.post("/humificador/{estado}")
async def set_humificador(estado: bool):
    return await safe_write("humificador_rw", estado)


@app.get("/mister")
async def get_mister():
    return safe_response(
        "mister",
        plc.latest_values.get("mister")
        )


@app.post("/mister/{estado}")
async def set_mister(estado: bool):
    return await safe_write("mister_rw", estado)

# -----
# Prueba 2 - instrumentación de tres etapas
# -----

@app.post("/experiments/response/start")
async def start_response_experiments():
    response_tracker.start()
    return {"status": "ok", "message": "Instrumentación de Prueba 2 iniciada"}

@app.post("/experiments/response/stop")
async def stop_response_experiment():
    response_tracker.stop()
    return {"status": "ok", "message": "Instrumentación de Prueba 2 detenida"}

@app.get("/experiments/response/event/{command_id}")
async def get_response(command_id: str):
    event = response_tracker.get_event(command_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Evento aún no detectado")
    return {"status": "ok", "event": event}