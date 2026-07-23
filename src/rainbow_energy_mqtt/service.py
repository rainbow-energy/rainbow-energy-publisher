"""Long-running service loop for rainbow-energy-mqtt."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from time import sleep as default_sleep

from rainbow_energy_client import Client, ClientError
from rainbow_energy_client.decode import Measurement
from rainbow_energy_client.device import RegisterReader
from rainbow_energy_client.profiles import DeviceProfile

from rainbow_energy_mqtt.config import DEFAULT_LOG_LEVEL
from rainbow_energy_mqtt.publisher import MeasurementPublisher

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
    publisher: MeasurementPublisher | None = None,
    all_keys: bool = False,
) -> None:
    """Poll measurements until interrupted or iterations complete."""
    configure_logging(log_level)

    if all_keys:
        keys = tuple(
            register.key
            for register in profile.registers
            if register.access == "read"
        )

    known_keys = {register.key for register in profile.registers}
    unknown_keys = [key for key in keys if key not in known_keys]
    for key in unknown_keys:
        logger.warning("unknown key %r; not in profile, skipping", key)
    keys = tuple(key for key in keys if key in known_keys)
    if not keys:
        logger.error("no known keys left to poll; check config keys against profile")
        return

    client = Client(reader, profile, keys=keys)

    if publisher is not None and publisher.ha_discovery:
        if publisher.device_id is None:
            logger.warning(
                "ha_discovery is enabled but mqtt.device_id is unset; "
                "skipping Home Assistant discovery"
            )
        else:
            registers = {register.key: register for register in profile.registers}
            discovery_measurements = tuple(
                Measurement(
                    key=key,
                    name=registers[key].name,
                    value=0,
                    unit=registers[key].unit,
                )
                for key in keys
                if key in registers
            )
            try:
                publisher.publish_discovery(
                    discovery_measurements,
                    manufacturer=profile.manufacturer,
                    model=profile.model,
                )
            except OSError as error:
                logger.error("discovery publish failed: %s", error, exc_info=error)

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
            if publisher is not None:
                try:
                    publisher.publish(measurements)
                except OSError as error:
                    logger.error("publish failed: %s", error, exc_info=error)
    except KeyboardInterrupt:
        return
