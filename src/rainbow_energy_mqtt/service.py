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

    resolved_keys = _resolve_keys(profile, keys, all_keys=all_keys)
    if resolved_keys is None:
        return

    client = Client(reader, profile, keys=resolved_keys)
    _publish_discovery_if_enabled(publisher, profile, resolved_keys)
    _run_poll_loop(
        client,
        publisher=publisher,
        interval=interval,
        sleep=sleep,
        iterations=iterations,
    )


def _resolve_keys(
    profile: DeviceProfile,
    keys: Sequence[str],
    *,
    all_keys: bool,
) -> tuple[str, ...] | None:
    """Expand and filter keys; return None when nothing remains to poll."""
    if all_keys:
        keys = tuple(
            register.key
            for register in profile.registers
            if register.access == "read"
        )

    known_keys = {register.key for register in profile.registers}
    for key in keys:
        if key not in known_keys:
            logger.warning("unknown key %r; not in profile, skipping", key)

    resolved = tuple(key for key in keys if key in known_keys)
    if not resolved:
        logger.error("no known keys left to poll; check config keys against profile")
        return None
    return resolved


def _publish_discovery_if_enabled(
    publisher: MeasurementPublisher | None,
    profile: DeviceProfile,
    keys: Sequence[str],
) -> None:
    """Publish Home Assistant discovery configs once when configured."""
    if publisher is None or not publisher.ha_discovery:
        return
    if publisher.device_id is None:
        logger.warning(
            "ha_discovery is enabled but mqtt.device_id is unset; "
            "skipping Home Assistant discovery"
        )
        return

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


def _run_poll_loop(
    client: Client,
    *,
    publisher: MeasurementPublisher | None,
    interval: float,
    sleep: Callable[[float], None],
    iterations: int | None,
) -> None:
    """Run the client poll loop until interrupted or iterations complete."""
    try:
        for measurements in client.run(
            interval=interval,
            sleep=sleep,
            iterations=iterations,
            on_error=_on_poll_error,
        ):
            _log_measurements(measurements)
            _publish_measurements(publisher, measurements)
    except KeyboardInterrupt:
        return


def _on_poll_error(error: ClientError) -> None:
    """Log a Client poll failure and continue the loop."""
    logger.error("poll failed: %s", error, exc_info=error)


def _log_measurements(measurements: Sequence[Measurement]) -> None:
    """Log each measurement at INFO."""
    for measurement in measurements:
        logger.info(
            "%s=%s %s",
            measurement.key,
            measurement.value,
            measurement.unit,
        )


def _publish_measurements(
    publisher: MeasurementPublisher | None,
    measurements: Sequence[Measurement],
) -> None:
    """Publish measurements when a publisher is configured."""
    if publisher is None:
        return
    try:
        publisher.publish(measurements)
    except OSError as error:
        logger.error("publish failed: %s", error, exc_info=error)
