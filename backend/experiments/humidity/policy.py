from .models import ActionType, ControlDecision


TARGET_MIN = 92.0
TARGET_MAX = 94.0
EXTRACTION_THRESHOLD = 110.0


def decide(humidity_inside: float) -> ControlDecision:
    """Maps the current interior humidity to one control decision.

    This module contains only experimental policy; it has no PLC or timing concerns.
    """
    if humidity_inside < 75.0:
        return ControlDecision(ActionType.HUMIDIFY, 40.0, "Humedad inferior a 75 %")

    if humidity_inside < 85.0:
        return ControlDecision(ActionType.HUMIDIFY, 20.0, "Humedad entre 75 % y 85 %")

    if humidity_inside < TARGET_MIN:
        return ControlDecision(ActionType.HUMIDIFY, 10.0, "Humedad entre 85 % y 92 %")

    if humidity_inside <= TARGET_MAX:
        return ControlDecision(ActionType.FINISH, None, "Humedad dentro del intervalo objetivo 92-94 %")

    if humidity_inside <= EXTRACTION_THRESHOLD:
        return ControlDecision(ActionType.MONITOR, None, "Humedad superior a 94 %; se mantiene la monitorización")

    return ControlDecision(ActionType.EXTRACT, 30.0, "Humedad superior a 110 %")
