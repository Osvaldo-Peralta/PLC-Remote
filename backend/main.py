# main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from asyncua import ua
from plc_client import PLCManager
from typing import Any
from config import PLC_ENDPOINT, NODE_DEFINITIONS

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instancia global del PLCManager
plc = PLCManager(PLC_ENDPOINT)

@app.on_event("startup")
async def startup_event():
    await plc.connect()
    # Inicializa todos los nodos definidos en config.py
    await plc.initialize_nodes(NODE_DEFINITIONS)

@app.on_event("shutdown")
async def shutdown_event():
    await plc.disconnect()

# Función auxiliar para escribir en nodos con manejo de errores
async def safe_write(name: str, value: Any, variant_type: ua.VariantType = ua.VariantType.Boolean):
    try:
        await plc.write_value(name, value, variant_type)
        return {"status": "ok", "value": value}
    except Exception as e:
        print(f"❌ Error al escribir en '{name}': {e}")
        return {"status": "error", "message": f"No se pudo escribir en {name}"}

# Función auxiliar para leer nodos con manejo de errores
async def safe_read(name: str):
    try:
        value = await plc.read_value(name)
        return {"status": "ok", "value": value}
    except Exception as e:
        print(f"❌ Error al leer '{name}': {e}")
        return {"status": "error", "message": f"No se pudo leer de {name}"}

# --- Endpoints actuales --- #
# Botón de inicio
@app.post("/start")
async def start():
    # Escribir True en 'start', False en 'stop'
    res1 = await safe_write("start", True)
    res2 = await safe_write("stop", False)
    if res1["status"] == "error" or res2["status"] == "error":
        return {"status": "error", "message": "No se pudo escribir en el PLC"}
    return {"status": "ok", "action": "start", "value": True}

# Botón de paro
@app.post("/stop")
async def stop():
    # Escribir False en 'start', True en 'stop'
    res1 = await safe_write("start", False)
    res2 = await safe_write("stop", True)
    if res1["status"] == "error" or res2["status"] == "error":
        return {"status": "error", "message": "No se pudo escribir en el PLC"}
    return {"status": "ok", "action": "stop", "value": False}

# Led de prueba
@app.get("/status")
async def status():
    return await safe_read("f_prueba")

# --- Aquí puedes añadir mas elementos --- #
@app.get("/foco_rojo")
async def foco_rojo():
    return await safe_read("f_rojo")

@app.get("/foco_amarillo")
async def foco_amarillo():
    return await safe_read("f_amarillo")

@app.get("/foco_verde")
async def foco_verde():
    return await safe_read("f_verde")

@app.get("/current_time")
async def get_current_time():
    return await safe_read("current_time")