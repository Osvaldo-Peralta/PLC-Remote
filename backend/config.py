PLC_ENDPOINT = "opc.tcp://192.168.1.99:4840"

NODE_DEFINITIONS = {
    "modoAutomatico": "ns=4;i=43",
    "humedad_ext": "ns=4;i=48",
    "humedadSHT41": "ns=4;i=46",
    "temperaturaExt": "ns=4;i=49",
    "temperaturaSHT41": "ns=4;i=47",

    "extractor": "ns=4;i=29",       # Read only
    "humificador": "ns=4;i=30",     # Read only
    "mister": "ns=4;i=31",          # Read only

    # --- Estas son las variables sobre las que escribire, para activar o desactivar los actuadores en modo manual --- #
    "extractor_rw": "ns=4;i=60",             # Read and Write
    "humificador_rw": "ns=4;i=61",           # Read and Write
    "mister_rw": "ns=4;i=62",                # Read and Write
}

TS = 5.0             # sampling time del loop de monitoreo en segundo plano [s]
RECONNECT_DELAY = 3.0  # segundos de espera entre reintentos de conexión al PLC