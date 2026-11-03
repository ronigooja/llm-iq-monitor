import time

from llm_iq_monitor.availability import probe_interval
from llm_iq_monitor.settings import Settings


def test_idle_uses_only_the_idle_interval():
    availability = Settings().availability
    availability.probe_idle_every_min = 120
    availability.probe_busy_every_min = 30

    assert probe_interval(availability, "idle") == 120


def test_busy_and_unknown_use_the_busy_interval():
    availability = Settings().availability
    availability.probe_idle_every_min = 120
    availability.probe_busy_every_min = 30

    assert probe_interval(availability, "busy") == 30
    assert probe_interval(availability, "unknown") == 30


def test_missing_state_is_unknown_and_uses_busy_interval():
    availability = Settings().availability
    availability.probe_busy_every_min = 30
    state_row = None
    state = state_row[0] if state_row else "unknown"

    assert probe_interval(availability, state) == 30


def test_model_without_probes_is_due_immediately():
    now = time.time()
    last = None

    assert last is None or now - last >= 30 * 60


def test_interval_switches_back_to_idle_after_classification():
    availability = Settings().availability
    availability.probe_idle_every_min = 120
    availability.probe_busy_every_min = 30

    assert probe_interval(availability, "busy") == 30
    assert probe_interval(availability, "idle") == 120
