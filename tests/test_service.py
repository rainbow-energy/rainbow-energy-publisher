"""Test the long-running service loop and CLI entry point."""

from rainbow_energy_mqtt.cli import main
from rainbow_energy_mqtt.service import run_service


def test_run_service_loops_until_interrupted():
    """Keep ticking until KeyboardInterrupt stops the service."""
    ticks: list[float] = []

    def sleep(seconds: float) -> None:
        ticks.append(seconds)
        if len(ticks) >= 3:
            raise KeyboardInterrupt

    run_service(interval=0.5, sleep=sleep)

    assert ticks == [0.5, 0.5, 0.5]


def test_main_returns_zero_when_service_stops(monkeypatch):
    """Exit cleanly when the service loop returns."""
    monkeypatch.setattr("rainbow_energy_mqtt.cli.run_service", lambda: None)

    assert main([]) == 0
