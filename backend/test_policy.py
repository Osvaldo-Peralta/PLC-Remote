from experiments.humidity.policy import decide
from experiments.humidity.models import ActionType


def test_policy_boundaries():
    assert (decide(74.99).action, decide(74.99).duration_seconds) == (ActionType.HUMIDIFY, 40.0)
    assert (decide(75.0).action, decide(75.0).duration_seconds) == (ActionType.HUMIDIFY, 20.0)
    assert (decide(85.0).action, decide(85.0).duration_seconds) == (ActionType.HUMIDIFY, 10.0)
    assert decide(92.0).action == ActionType.FINISH
    assert decide(94.0).action == ActionType.FINISH
    assert decide(94.01).action == ActionType.MONITOR
    assert decide(110.0).action == ActionType.MONITOR
    assert (decide(110.01).action, decide(110.01).duration_seconds) == (ActionType.EXTRACT, 30.0)
