"""Long-running service loop for rainbow-energy-mqtt."""

from __future__ import annotations

from collections.abc import Callable
from time import sleep as default_sleep


def run_service(
    *,
    interval: float = 1.0,
    sleep: Callable[[float], None] = default_sleep,
) -> None:
    """Run until interrupted, sleeping interval seconds between ticks."""
    try:
        while True:
            sleep(interval)
    except KeyboardInterrupt:
        return
