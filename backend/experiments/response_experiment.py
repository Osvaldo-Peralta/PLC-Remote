from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Dict, Optional
from uuid import uuid4


RW_TO_STATUS = {
    "extractor_rw": "extractor",
    "humificador_rw": "humificador",
    "mister_rw": "mister",
}


class ResponseTracker:
    """Instrumentación aislada para la Prueba 2.

    Registra el intervalo entre el envío de un comando y su detección en el
    snapshot leído directamente desde los nodos de estado del PLC.
    """

    def __init__(self) -> None:
        self.accepting_commands = False
        self.pending: Dict[str, Dict[str, Any]] = {}
        self.completed: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()

    def start(self) -> None:
        self.accepting_commands = True
        self.pending.clear()
        self.completed.clear()

    def stop(self) -> None:
        # No se borran pendientes: un comando ya enviado debe poder completar
        # su medición aunque el usuario detenga la campaña.
        self.accepting_commands = False

    def command_started(self, node_name: str, expected_state: bool, current_state: Any) -> Optional[str]:
        if not self.accepting_commands or node_name not in RW_TO_STATUS:
            return None

        status_name = RW_TO_STATUS[node_name]
        command_id = uuid4().hex[:12]
        started_perf = perf_counter()

        self.pending[command_id] = {
            "command_id": command_id,
            "status_name": status_name,
            "expected_state": expected_state,
            "previous_state": current_state if isinstance(current_state, bool) else None,
            "command_timestamp": self._timestamp(),
            "started_perf": started_perf,
            # Exigimos observar primero un estado distinto al esperado. Esto
            # evita confirmar una medición solo porque el cache ya contenía
            # el valor objetivo antes del comando.
            "observed_non_expected": current_state != expected_state,
        }
        return command_id

    def command_failed(self, command_id: Optional[str]) -> None:
        if command_id:
            self.pending.pop(command_id, None)

    def observe_snapshot(self, values: Dict[str, Any]) -> None:
        now_perf = perf_counter()
        now_timestamp = self._timestamp()

        for command_id, event in list(self.pending.items()):
            current = values.get(event["status_name"])

            if current is None:
                continue

            if current != event["expected_state"]:
                event["observed_non_expected"] = True
                continue

            if not event["observed_non_expected"]:
                continue

            event["detected_timestamp"] = now_timestamp
            event["backend_response_time_ms"] = (
                now_perf - event["started_perf"]
            ) * 1000.0

            result = {
                key: value
                for key, value in event.items()
                if key not in {"started_perf", "observed_non_expected"}
            }
            self.completed[command_id] = result
            del self.pending[command_id]

    def get_event(self, command_id: str) -> Optional[Dict[str, Any]]:
        return self.completed.get(command_id)


response_tracker = ResponseTracker()
