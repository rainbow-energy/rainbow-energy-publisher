"""Long-running service loop for rainbow-energy-publisher."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from time import sleep as default_sleep

from rainbow_energy_modbus_client import Client, ClientError
from rainbow_energy_modbus_client.decode import Measurement
from rainbow_energy_modbus_client.device import RegisterTransport
from rainbow_energy_modbus_client.profiles import DeviceProfile

from rainbow_energy_publisher.commands import (
    CommandQueue,
    subscribe_commands,
    writable_keys,
)
from rainbow_energy_publisher.config import DEFAULT_LOG_LEVEL
from rainbow_energy_publisher.mqtt import MqttClient
from rainbow_energy_publisher.publisher import MeasurementPublisher

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
    reader: RegisterTransport,
    profile: DeviceProfile,
    keys: Sequence[str],
    interval: float = 1.0,
    sleep: Callable[[float], None] = default_sleep,
    iterations: int | None = None,
    log_level: str = DEFAULT_LOG_LEVEL,
    publisher: MeasurementPublisher | None = None,
    all_keys: bool = False,
    accept_writes: bool = False,
    mqtt_client: MqttClient | None = None,
    topic_prefix: str | None = None,
) -> None:
    """Poll measurements until interrupted or iterations complete."""
    configure_logging(log_level)

    resolved_keys = _resolve_keys(
        profile,
        keys,
        all_keys=all_keys,
        accept_writes=accept_writes,
    )
    if resolved_keys is None:
        return

    client = Client(reader, profile, keys=resolved_keys)
    command_queue = _start_command_subscription(
        profile=profile,
        accept_writes=accept_writes,
        mqtt_client=mqtt_client,
        topic_prefix=topic_prefix,
    )
    _publish_discovery_if_enabled(
        publisher,
        profile,
        resolved_keys,
        accept_writes=accept_writes,
    )
    _run_poll_loop(
        client,
        publisher=publisher,
        interval=interval,
        sleep=sleep,
        iterations=iterations,
        command_queue=command_queue,
    )


def _start_command_subscription(
    *,
    profile: DeviceProfile,
    accept_writes: bool,
    mqtt_client: MqttClient | None,
    topic_prefix: str | None,
) -> CommandQueue | None:
    """Subscribe to MQTT /set topics when accept_writes is enabled."""
    if not accept_writes:
        return None
    if mqtt_client is None or not topic_prefix:
        logger.warning(
            "mqtt.accept_writes is enabled but MQTT client or topic_prefix is missing; "
            "skipping command subscription"
        )
        return None

    queue = CommandQueue()
    subscribe_commands(
        client=mqtt_client,
        topic_prefix=topic_prefix,
        allowed_keys=writable_keys(profile),
        queue=queue,
    )
    return queue


def _resolve_keys(
    profile: DeviceProfile,
    keys: Sequence[str],
    *,
    all_keys: bool,
    accept_writes: bool = False,
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
    if accept_writes:
        already = set(resolved)
        write_keys = tuple(
            register.key
            for register in profile.registers
            if register.access == "write" and register.key not in already
        )
        resolved = resolved + write_keys
    if not resolved:
        logger.error("no known keys left to poll; check config keys against profile")
        return None
    return resolved


def _publish_discovery_if_enabled(
    publisher: MeasurementPublisher | None,
    profile: DeviceProfile,
    keys: Sequence[str],
    *,
    accept_writes: bool = False,
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
    discovery_registers = tuple(
        registers[key]
        for key in keys
        if key in registers and registers[key].access == "read"
    )
    try:
        publisher.publish_discovery(
            discovery_registers,
            manufacturer=profile.manufacturer,
            model=profile.model,
        )
        if accept_writes:
            publisher.publish_control_discovery(
                tuple(
                    register
                    for register in profile.registers
                    if register.access == "write"
                ),
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
    command_queue: CommandQueue | None,
) -> None:
    """Run the client poll loop until interrupted or iterations complete."""

    def sleep_between_polls(seconds: float) -> None:
        sleep(seconds)
        _apply_pending_writes(client, command_queue)

    try:
        _apply_pending_writes(client, command_queue)
        for measurements in client.run(
            interval=interval,
            sleep=sleep_between_polls if command_queue is not None else sleep,
            iterations=iterations,
            on_error=_on_poll_error,
        ):
            _log_measurements(measurements)
            _publish_measurements(publisher, measurements)
    except KeyboardInterrupt:
        return


def _apply_pending_writes(
    client: Client,
    command_queue: CommandQueue | None,
) -> None:
    """Drain queued MQTT commands and write them through the Modbus client."""
    if command_queue is None:
        return
    pending = command_queue.drain()
    if not pending:
        return
    try:
        client.write(pending)
    except ClientError as error:
        logger.error("write failed: %s", error, exc_info=error)


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
