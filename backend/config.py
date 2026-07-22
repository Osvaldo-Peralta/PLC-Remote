PLC_ENDPOINT = "opc.tcp://192.168.1.99:4840"

NODE_DEFINITIONS = {
    "modoAutomatico": "ns=4;i=43",
    "humedad_ext": "ns=4;i=48",
    "humedadSHT41": "ns=4;i=46",
    "temperaturaExt": "ns=4;i=49",
    "temperaturaSHT41": "ns=4;i=47",
    "extractor": "ns=4;i=29",
    "humificador": "ns=4;i=30",
    "mister": "ns=4;i=31",
}

TS = 5.0             # sampling time del loop de monitoreo en segundo plano [s]
RECONNECT_DELAY = 3.0  # segundos de espera entre reintentos de conexión al PLC