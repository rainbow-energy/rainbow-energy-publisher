"""MQTT command topic handling for writable profile registers."""

from __future__ import annotations

import logging
import threading
from collections.abc import Set

from rainbow_energy_modbus_client.device import WriteValue
from rainbow_energy_modbus_client.profiles import DeviceProfile

from rainbow_energy_publisher.mqtt import MqttClient

logger = logging.getLogger(__name__)


class CommandQueue:
    """Thread-safe queue of pending key/value writes, latest value wins."""

    def __init__(self) -> None:
        """Create an empty command queue."""
        self._lock = threading.Lock()
        self._pending: dict[str, WriteValue] = {}

    def put(self, key: str, value: WriteValue) -> None:
        """Record a pending write for *key*, replacing any earlier value."""
        with self._lock:
            self._pending[key] = value

    def drain(self) -> dict[str, WriteValue]:
        """Return and clear all pending writes."""
        with self._lock:
            pending = self._pending
            self._pending = {}
            return pending


def parse_command_payload(raw: str) -> WriteValue:
    """Parse an MQTT command payload into bool, int, float, or string."""
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


def writable_keys(profile: DeviceProfile) -> set[str]:
    """Return profile register keys marked access: write."""
    return {
        register.key
        for register in profile.registers
        if register.access == "write"
    }


def handle_command_message(
    *,
    topic: str,
    payload: str,
    topic_prefix: str,
    allowed_keys: Set[str],
    queue: CommandQueue,
) -> None:
    """Parse a command topic and enqueue a write when the key is allowed."""
    prefix = topic_prefix.rstrip("/")
    suffix = "/set"
    if not topic.startswith(f"{prefix}/") or not topic.endswith(suffix):
        return
    key = topic[len(prefix) + 1 : -len(suffix)]
    if not key or "/" in key:
        return
    if key not in allowed_keys:
        logger.warning("ignoring command for non-writable key %r", key)
        return
    queue.put(key, parse_command_payload(payload))


def subscribe_commands(
    *,
    client: MqttClient,
    topic_prefix: str,
    allowed_keys: Set[str],
    queue: CommandQueue,
) -> None:
    """Subscribe to topic_prefix/+/set and enqueue allowed command writes."""
    prefix = topic_prefix.rstrip("/")
    topic = f"{prefix}/+/set"

    def _on_message(message_topic: str, payload: str) -> None:
        handle_command_message(
            topic=message_topic,
            payload=payload,
            topic_prefix=prefix,
            allowed_keys=allowed_keys,
            queue=queue,
        )

    client.subscribe(topic, _on_message)
