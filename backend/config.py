# config.py

PLC_ENDPOINT = "opc.tcp://192.168.0.1:4840"

# Mapeo de nodos para inicializar en startup
NODE_DEFINITIONS = {
    "start": "ns=3;s=\"Semaforo_RM2\".\"start\"",
    "stop": "ns=3;s=\"Semaforo_RM2\".\"stop\"",
    "f_prueba": "ns=3;s=\"Semaforo_RM2\".\"f_prueba\"",
    # --- Elementos nuevos del PLC ---
    "f_rojo": "ns=3;s=\"Semaforo_RM2\".\"f_rojo\"",
    "f_amarillo": "ns=3;s=\"Semaforo_RM2\".\"f_amarillo\"",
    "f_verde": "ns=3;s=\"Semaforo_RM2\".\"f_verde\"",
    "current_time": "ns=3;s=\"Semaforo_RM2\".\"current_time\"",
    # Puedes agregar más aquí fácilmente
    # "luz_verde": "ns=3;s=\"Semaforo_RM2\".\"LuzVerde\"",
}