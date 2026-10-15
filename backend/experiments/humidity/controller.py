from __future__ import annotations

from typing import Any

from asyncua import ua


class HumidityController:
    """Owns actuator writes for the humidity experiment only."""

    def __init__(self, plc: Any):
        self.plc = plc

    async def _write_output(self, name: str, enabled: bool) -> None:
        try:
            await self.plc.write_value(name, enabled, ua.VariantType.Boolean)
        except Exception as exc:
            # A failed request does not tell us the physical output's final state.
            raise RuntimeError(f"ERROR_WRITE: no se pudo escribir {name}={enabled}: {exc}") from exc

    async def set_humidification(self, enabled: bool) -> None:
        await self._write_output("humificador_rw", enabled)
        try:
            await self._write_output("mister_rw", enabled)
        except Exception:
            # Best-effort rollback: do not intentionally leave the humidifier enabled alone.
            if enabled:
                try:
                    await self._write_output("humificador_rw", False)
                except Exception:
                    pass
            raise

    async def set_extractor(self, enabled: bool) -> None:
        await self._write_output("extractor_rw", enabled)

    async def stop_all(self) -> None:
        """Best-effort shutdown used on normal completion, stop, timeout and errors."""
        errors = []
        for name in ("extractor_rw", "humificador_rw", "mister_rw"):
            try:
                await self.plc.write_value(name, False, ua.VariantType.Boolean)
            except Exception as exc:
                errors.append(f"{name}: {exc}")
        if errors:
            raise RuntimeError("ERROR_SHUTDOWN: no fue posible confirmar escrituras OFF para todos los actuadores: " + "; ".join(errors))
