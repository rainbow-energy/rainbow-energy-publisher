"""Publish decoded measurements to MQTT state topics."""

from __future__ import annotations

import json
from collections.abc import Sequence

from rainbow_energy_modbus_client.decode import Measurement
from rainbow_energy_modbus_client.profiles import RegisterDefinition

from rainbow_energy_publisher.mqtt import MqttClient


def _state_payload(value: object) -> str:
    """Format a measurement value for MQTT state topics."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


_ENERGY_UNITS = frozenset({"Wh", "kWh"})
_UNIT_DEVICE_CLASSES = {
    "W": "power",
    "V": "voltage",
    "A": "current",
    "°C": "temperature",
    "Hz": "frequency",
    "%": "battery",
}


def _sensor_class_fields(unit: str) -> dict[str, str]:
    """Return HA state_class / device_class fields for a sensor unit."""
    if unit in _ENERGY_UNITS:
        return {
            "state_class": "total_increasing",
            "device_class": "energy",
        }
    fields = {"state_class": "measurement"}
    device_class = _UNIT_DEVICE_CLASSES.get(unit)
    if device_class is not None:
        fields["device_class"] = device_class
    return fields


def _device_block(
    *,
    device_id: str,
    manufacturer: str,
    model: str,
) -> dict[str, object]:
    """Build the shared Home Assistant device discovery block."""
    return {
        "identifiers": [device_id],
        "name": device_id,
        "manufacturer": manufacturer,
        "model": model,
    }


def sensor_discovery_config(
    register: RegisterDefinition,
    *,
    topic_prefix: str,
    device_id: str,
    manufacturer: str,
    model: str,
) -> tuple[str, dict[str, object]]:
    """Return HA component name and discovery payload for a readable register."""
    prefix = topic_prefix.rstrip("/")
    state_topic = f"{prefix}/{register.key}"
    device = _device_block(
        device_id=device_id,
        manufacturer=manufacturer,
        model=model,
    )
    base = {
        "name": register.name,
        "state_topic": state_topic,
        "unique_id": f"{device_id}_{register.key}",
        "device": device,
    }
    if register.binary:
        return (
            "binary_sensor",
            {
                **base,
                "payload_on": "true",
                "payload_off": "false",
            },
        )
    if register.data_type in {"string", "fault", "protocol"}:
        return (
            "sensor",
            {
                **base,
                "entity_category": "diagnostic",
            },
        )
    if register.options is not None:
        return (
            "sensor",
            {
                **base,
                "device_class": "enum",
                "options": list(register.options.values()),
            },
        )
    return (
        "sensor",
        {
            **base,
            "unit_of_measurement": register.unit,
            **_sensor_class_fields(register.unit),
        },
    )


def control_discovery_config(
    register: RegisterDefinition,
    *,
    topic_prefix: str,
    device_id: str,
    manufacturer: str,
    model: str,
) -> tuple[str, dict[str, object]] | None:
    """Return HA component name and discovery payload for a writable register.

    Maps binary registers to switch, options to select, time/datetime to text,
    and other numerics to number. Skips non-writable registers.
    """
    if register.access != "write":
        return None

    prefix = topic_prefix.rstrip("/")
    state_topic = f"{prefix}/{register.key}"
    command_topic = f"{prefix}/{register.key}/set"
    device = _device_block(
        device_id=device_id,
        manufacturer=manufacturer,
        model=model,
    )
    base = {
        "name": register.name,
        "state_topic": state_topic,
        "command_topic": command_topic,
        "unique_id": f"{device_id}_{register.key}",
        "device": device,
    }

    if register.binary:
        return (
            "switch",
            {
                **base,
                "payload_on": "true",
                "payload_off": "false",
            },
        )
    if register.options is not None:
        return (
            "select",
            {
                **base,
                "options": list(register.options.values()),
            },
        )
    if register.data_type in {"time", "datetime"}:
        return ("text", dict(base))
    return (
        "number",
        {
            **base,
            "unit_of_measurement": register.unit,
        },
    )


class MeasurementPublisher:
    """Publish measurement values under a topic prefix."""

    def __init__(
        self,
        *,
        client: MqttClient,
        topic_prefix: str,
        retain: bool = True,
        device_id: str | None = None,
        discovery_prefix: str = "homeassistant",
        ha_discovery: bool = False,
    ) -> None:
        """Bind an MQTT client, topic prefix, retain flag, and discovery settings."""
        self._client = client
        self._topic_prefix = topic_prefix.rstrip("/")
        self._retain = retain
        self._device_id = device_id
        self._discovery_prefix = discovery_prefix.rstrip("/")
        self._ha_discovery = ha_discovery

    @property
    def ha_discovery(self) -> bool:
        """Return whether Home Assistant discovery should be published at startup."""
        return self._ha_discovery

    @property
    def device_id(self) -> str | None:
        """Return the stable MQTT / Home Assistant device identifier, if set."""
        return self._device_id

    def publish(self, measurements: Sequence[Measurement]) -> None:
        """Publish each measurement value as a string payload on its state topic."""
        for measurement in measurements:
            topic = f"{self._topic_prefix}/{measurement.key}"
            self._client.publish(
                topic,
                _state_payload(measurement.value),
                retain=self._retain,
            )

    def publish_discovery(
        self,
        registers: Sequence[RegisterDefinition],
        *,
        manufacturer: str,
        model: str,
    ) -> None:
        """Publish retained Home Assistant MQTT discovery configs for sensors."""
        if self._device_id is None:
            return
        for register in registers:
            component, payload = sensor_discovery_config(
                register,
                topic_prefix=self._topic_prefix,
                device_id=self._device_id,
                manufacturer=manufacturer,
                model=model,
            )
            topic = (
                f"{self._discovery_prefix}/{component}/"
                f"{self._device_id}/{register.key}/config"
            )
            self._client.publish(topic, json.dumps(payload), retain=True)

    def publish_control_discovery(
        self,
        registers: Sequence[RegisterDefinition],
        *,
        manufacturer: str,
        model: str,
    ) -> None:
        """Publish retained HA switch/number/select configs for writable registers."""
        if self._device_id is None:
            return
        for register in registers:
            mapped = control_discovery_config(
                register,
                topic_prefix=self._topic_prefix,
                device_id=self._device_id,
                manufacturer=manufacturer,
                model=model,
            )
            if mapped is None:
                continue
            component, payload = mapped
            topic = (
                f"{self._discovery_prefix}/{component}/"
                f"{self._device_id}/{register.key}/config"
            )
            self._client.publish(topic, json.dumps(payload), retain=True)
