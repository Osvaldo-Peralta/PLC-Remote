from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from asyncua import Client, ua
import asyncio

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración de la URL del servidor de OPC UA
PLC_ENDPOINT = "opc.tcp://192.168.0.1:4840"

client = None
node_start = None
node_stop = None
node_status = None

@app.on_event("startup")
async def startup_event():
    global client, node_start, node_stop, node_status
    client = Client(url=PLC_ENDPOINT)
    try:
        await client.connect()
        print("✅ Conectado al PLC")
        # ✅ Obtenemos los nodos para cada variable
        node_start = client.get_node("ns=3;s=\"Semaforo_RM2\".\"start\"")
        node_stop = client.get_node("ns=3;s=\"Semaforo_RM2\".\"stop\"")
        node_status = client.get_node("ns=3;s=\"Semaforo_RM2\".\"f_prueba\"")
        print(f"✅ Nodo start encontrado: {node_start}")
        print(f"✅ Nodo stop encontrado: {node_stop}")
        print(f"✅ Nodo status encontrado: {node_status}")
    except Exception as e:
        print(f"❌ Error al conectar: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    if client:
        await client.disconnect()
        print("🔌 Desconectado del PLC")


@app.post("/start")
async def start():
    global node_start, node_stop
    if not node_start or not node_stop:
        return {"status": "error", "message": "No node"}

    try:
        # ✅ Escribir True en 'start', False en 'stop'
        await node_start.write_value(ua.DataValue(ua.Variant(True, ua.VariantType.Boolean)))
        await node_stop.write_value(ua.DataValue(ua.Variant(False, ua.VariantType.Boolean)))
        return {"status": "ok", "action": "start", "value": True}
    except Exception as e:
        print(f"❌ Error al escribir en start: {e}")
        return {"status": "error", "message": "No se pudo escribir en el PLC"}

@app.post("/stop")
async def stop():
    global node_start, node_stop
    if not node_start or not node_stop:
        return {"status": "error", "message": "No node"}

    try:
        # ✅ Escribir False en 'start', True en 'stop'
        await node_start.write_value(ua.DataValue(ua.Variant(False, ua.VariantType.Boolean)))
        await node_stop.write_value(ua.DataValue(ua.Variant(True, ua.VariantType.Boolean)))
        return {"status": "ok", "action": "stop", "value": False}
    except Exception as e:
        print(f"❌ Error al escribir en stop: {e}")
        return {"status": "error", "message": "No se pudo escribir en el PLC"}

@app.get("/status")
async def status():
    global node_status
    if not node_status:
        return {"status": "error", "message": "No node"}

    try:
        value = await node_status.read_value()
        return {"status": "ok", "value": value}
    except Exception as e:
        print(f"❌ Error al leer en status: {e}")
        return {"status": "error", "message": "No se pudo leer del PLC"}