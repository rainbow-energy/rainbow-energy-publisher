"""Long-running service loop for rainbow-energy-mqtt."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from time import sleep as default_sleep

from rainbow_energy_client import Client, ClientError
from rainbow_energy_client.device import RegisterReader
from rainbow_energy_client.profiles import DeviceProfile

from rainbow_energy_mqtt.config import DEFAULT_LOG_LEVEL

logger = logging.getLogger(__name__)


def configure_logging(level: str = DEFAULT_LOG_LEVEL) -> None:
    """Configure root logging; *level* is a standard logging name (e.g. INFO)."""
    resolved = getattr(logging, level.upper(), logging.INFO)
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=resolved,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
    else:
        root.setLevel(resolved)


def run_service(
    *,
    reader: RegisterReader,
    profile: DeviceProfile,
    keys: Sequence[str],
    interval: float = 1.0,
    sleep: Callable[[float], None] = default_sleep,
    iterations: int | None = None,
    log_level: str = DEFAULT_LOG_LEVEL,
) -> None:
    """Poll measurements until interrupted or iterations complete."""
    configure_logging(log_level)
    client = Client(reader, profile, keys=keys)

    def on_error(error: ClientError) -> None:
        logger.error("poll failed: %s", error, exc_info=error)

    try:
        for measurements in client.run(
            interval=interval,
            sleep=sleep,
            iterations=iterations,
            on_error=on_error,
        ):
            for measurement in measurements:
                logger.info(
                    "%s=%s %s",
                    measurement.key,
                    measurement.value,
                    measurement.unit,
                )
    except KeyboardInterrupt:
        return
