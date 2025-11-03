# plc_client.py

from asyncua import Client, ua
from typing import Dict, Optional, Any
import asyncio

class PLCManager:
    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self.client: Optional[Client] = None
        self.nodes: Dict[str, Any] = {}

    async def connect(self):
        self.client = Client(url=self.endpoint)
        try:
            await self.client.connect()
            print("✅ Conectado al PLC")
        except Exception as e:
            print(f"❌ Error al conectar: {e}")
            raise

    async def disconnect(self):
        if self.client:
            await self.client.disconnect()
            print("🔌 Desconectado del PLC")

    async def add_node(self, name: str, node_id: str):
        if not self.client:
            raise RuntimeError("Cliente no conectado")
        node = self.client.get_node(node_id)
        self.nodes[name] = node
        print(f"✅ Nodo '{name}' encontrado: {node}")

    async def read_value(self, name: str) -> Any:
        node = self.nodes.get(name)
        if not node:
            raise KeyError(f"Nodo '{name}' no encontrado")
        try:
            return await node.read_value()
        except Exception as e:
            print(f"❌ Error al leer nodo '{name}': {e}")
            raise

    async def write_value(self, name: str, value: Any, variant_type: ua.VariantType = ua.VariantType.Boolean):
        node = self.nodes.get(name)
        if not node:
            raise KeyError(f"Nodo '{name}' no encontrado")
        try:
            await node.write_value(ua.DataValue(ua.Variant(value, variant_type)))
        except Exception as e:
            print(f"❌ Error al escribir en nodo '{name}': {e}")
            raise

    # Método para inicializar múltiples nodos de una lista
    async def initialize_nodes(self, node_definitions: Dict[str, str]):
        for name, node_id in node_definitions.items():
            await self.add_node(name, node_id)