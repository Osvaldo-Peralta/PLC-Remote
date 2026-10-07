from asyncua import Client, ua
from typing import Dict, Optional, Any, Callable
import asyncio
import time
import inspect


class PLCManager:
    def __init__(self, endpoint: str, reconnect_delay: float = 3.0):
        self.endpoint = endpoint
        self.reconnect_delay = reconnect_delay
        self.client: Optional[Client] = None
        self.nodes: Dict[str, Any] = {}
        self.node_definitions: Dict[str, str] = {}
        self.latest_values: Dict[str, Any] = {}
        self.connected = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._snapshot_callbacks: list[Callable[[Dict[str, Any]], Any]] = []

    def add_snapshot_callback(self, callback: Callable[[Dict[str, Any]], Any]) -> None:
        """
        Registra un callback opcional ejecutado después de cada lectura completa.
        """

        if callback not in self._snapshot_callbacks:
            self._snapshot_callbacks.append(callback)

    def remote_snapshot_callback(self, callback: Callable[[Dict[str, Any]], Any]) -> None:
        if callback in self._snapshot_callbacks:
            self._snapshot_callbacks.remove(callback)

    async def connect(self):
        """
        Conecta al PLC. A diferencia de la versión anterior, no lanza
        excepción: reintenta indefinidamente hasta lograr conexión.
        """
        while True:
            try:
                self.client = Client(url=self.endpoint)
                await self.client.connect()
                self.connected = True
                print(f"✅ Conectado al PLC ({self.endpoint})")
                return
            except Exception as e:
                self.connected = False
                print(f"❌ Error al conectar: {e}. Reintentando en {self.reconnect_delay}s...")
                await asyncio.sleep(self.reconnect_delay)

    async def disconnect(self):
        if self.client:
            try:
                await self.client.disconnect()
                print("🔌 Desconectado del PLC")
            except Exception:
                pass
        self.connected = False

    async def add_node(self, name: str, node_id: str):
        if not self.client:
            raise RuntimeError("Cliente no conectado")
        node = self.client.get_node(node_id)
        self.nodes[name] = node
        print(f"✅ Nodo '{name}' encontrado: {node}")

    async def initialize_nodes(self, node_definitions: Dict[str, str]):
        self.node_definitions = node_definitions
        for name, node_id in node_definitions.items():
            try:
                await self.add_node(name, node_id)
            except Exception as e:
                print(f"⚠️ No se pudo inicializar el nodo '{name}' ({node_id}): {e}")

    async def read_value(self, name: str) -> Any:
        node = self.nodes.get(name)
        if not node:
            raise KeyError(f"Nodo '{name}' no encontrado")
        return await node.read_value()

    async def write_value(self, name: str, value: Any, variant_type: ua.VariantType = ua.VariantType.Boolean):
        node = self.nodes.get(name)
        if not node:
            raise KeyError(f"Nodo '{name}' no encontrado")
        await node.write_value(ua.DataValue(ua.Variant(value, variant_type)))

    async def read_all(self) -> Dict[str, Any]:
        """Lee todos los nodos registrados en una sola pasada."""
        values = {}
        for name in self.nodes:
            try:
                values[name] = await self.read_value(name)
            except Exception as e:
                values[name] = None
                print(f"❌ Error al leer '{name}': {e}")
        return values

    def _print_status(self, values: Dict[str, Any]):
        line = " | ".join(f"{k}={round(v, 2)}" for k, v in values.items())
        print(f"[{time.strftime('%H:%M:%S')}] {line}")

    async def _nofify_snapshot_callbacks(self, values: Dict[str, Any]) -> None:
        # Se usa una copia para que un callback no pueda modificar el cache del PLC.
        snapshot = dict (values)
        for callback in list(self._snapshot_callbacks):
            try:
                result = callback(snapshot)
                if inspect.isawaitable(result):
                    await result
            except Exception as e:
                print(f"⚠️ Error en callback de snapshot: {e}")

    async def monitor_loop(self, ts: float = 1.0):
        """
        Loop de fondo:
        - lee todos los nodos cada `ts` segundos
        - actualiza self.latest_values (lo que consumen los endpoints)
        - imprime el snapshot en terminal
        - si se pierde la conexión, reconecta y re-registra los nodos solo
        """
        while True:
            start = time.time()

            if not self.connected:
                await self.connect()
                await self.initialize_nodes(self.node_definitions)

            try:
                self.latest_values = await self.read_all()
                self._print_status(self.latest_values)
                await self._nofify_snapshot_callbacks(self.latest_values)
            except Exception as e:
                print(f"❌ Error en el loop de monitoreo: {e}")
                self.connected = False

            elapsed = time.time() - start
            sleep_for = ts - elapsed
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
            else:
                print(f"⚠️ El ciclo tardó {elapsed:.3f}s > TS={ts}s")

    def start_monitoring(self, node_definitions: Dict[str, str], ts: float = 1.0):
        self.node_definitions = node_definitions
        self._monitor_task = asyncio.create_task(self.monitor_loop(ts))

    async def stop_monitoring(self):
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass