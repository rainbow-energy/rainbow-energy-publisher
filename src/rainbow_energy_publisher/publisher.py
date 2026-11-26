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


_UNIT_DEVICE_CLASSES = {
    "W": "power",
    "V": "voltage",
    "A": "current",
    "°C": "temperature",
    "Hz": "frequency",
    "%": "battery",
    "Wh": "energy",
    "kWh": "energy",
}


def _sensor_class_fields(unit: str) -> dict[str, str]:
    """Return HA state_class / device_class fields for a sensor unit."""
    device_class = _UNIT_DEVICE_CLASSES.get(unit)
    fields = {
        "state_class": (
            "total_increasing" if device_class == "energy" else "measurement"
        ),
    }
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


def _base_discovery_config(
    register: RegisterDefinition,
    *,
    topic_prefix: str,
    device_id: str,
    manufacturer: str,
    model: str,
    command: bool = False,
) -> dict[str, object]:
    """Build the shared HA discovery fields for a register."""
    prefix = topic_prefix.rstrip("/")
    payload: dict[str, object] = {
        "name": register.name,
        "state_topic": f"{prefix}/{register.key}",
        "unique_id": f"{device_id}_{register.key}",
        "device": _device_block(
            device_id=device_id,
            manufacturer=manufacturer,
            model=model,
        ),
    }
    if command:
        payload["command_topic"] = f"{prefix}/{register.key}/set"
    return payload


def _binary_sensor_discovery(
    base: dict[str, object],
) -> tuple[str, dict[str, object]]:
    """Map a binary read register to an HA binary_sensor."""
    return (
        "binary_sensor",
        {
            **base,
            "payload_on": "true",
            "payload_off": "false",
        },
    )


def _diagnostic_sensor_discovery(
    base: dict[str, object],
) -> tuple[str, dict[str, object]]:
    """Map string/fault/protocol reads to a diagnostic sensor."""
    return (
        "sensor",
        {
            **base,
            "entity_category": "diagnostic",
        },
    )


def _enum_sensor_discovery(
    base: dict[str, object],
    register: RegisterDefinition,
) -> tuple[str, dict[str, object]]:
    """Map an options read register to an HA enum sensor."""
    assert register.options is not None
    return (
        "sensor",
        {
            **base,
            "device_class": "enum",
            "options": list(register.options.values()),
        },
    )


def _numeric_sensor_discovery(
    base: dict[str, object],
    register: RegisterDefinition,
) -> tuple[str, dict[str, object]]:
    """Map a numeric read register to an HA sensor with unit classes."""
    return (
        "sensor",
        {
            **base,
            "unit_of_measurement": register.unit,
            **_sensor_class_fields(register.unit),
        },
    )


def _switch_discovery(
    base: dict[str, object],
) -> tuple[str, dict[str, object]]:
    """Map a binary write register to an HA switch."""
    return (
        "switch",
        {
            **base,
            "payload_on": "true",
            "payload_off": "false",
        },
    )


def _select_discovery(
    base: dict[str, object],
    register: RegisterDefinition,
) -> tuple[str, dict[str, object]]:
    """Map an options write register to an HA select."""
    assert register.options is not None
    return (
        "select",
        {
            **base,
            "options": list(register.options.values()),
        },
    )


_TIME_PATTERN = r"^([01]?\d|2[0-3]):[0-5]\d$"
_DATETIME_PATTERN = (
    r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01]) "
    r"([01]?\d|2[0-3]):[0-5]\d:[0-5]\d$"
)
_TEXT_PATTERNS = {
    "time": _TIME_PATTERN,
    "datetime": _DATETIME_PATTERN,
}


def _text_discovery(
    base: dict[str, object],
    register: RegisterDefinition,
) -> tuple[str, dict[str, object]]:
    """Map a time/datetime write register to an HA text entity."""
    return (
        "text",
        {
            **base,
            "pattern": _TEXT_PATTERNS[register.data_type],
        },
    )


def _number_discovery(
    base: dict[str, object],
    register: RegisterDefinition,
) -> tuple[str, dict[str, object]]:
    """Map a numeric write register to an HA number."""
    payload: dict[str, object] = {
        **base,
        "unit_of_measurement": register.unit,
    }
    if register.min is not None:
        payload["min"] = register.min
    if register.max is not None:
        payload["max"] = register.max
    if register.step is not None:
        payload["step"] = register.step
    return ("number", payload)


def sensor_discovery_config(
    register: RegisterDefinition,
    *,
    topic_prefix: str,
    device_id: str,
    manufacturer: str,
    model: str,
) -> tuple[str, dict[str, object]]:
    """Return HA component name and discovery payload for a readable register."""
    base = _base_discovery_config(
        register,
        topic_prefix=topic_prefix,
        device_id=device_id,
        manufacturer=manufacturer,
        model=model,
    )
    if register.binary:
        return _binary_sensor_discovery(base)
    if register.data_type in {"string", "fault", "protocol"}:
        return _diagnostic_sensor_discovery(base)
    if register.options is not None:
        return _enum_sensor_discovery(base, register)
    return _numeric_sensor_discovery(base, register)


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

    base = _base_discovery_config(
        register,
        topic_prefix=topic_prefix,
        device_id=device_id,
        manufacturer=manufacturer,
        model=model,
        command=True,
    )
    if register.binary:
        return _switch_discovery(base)
    if register.options is not None:
        return _select_discovery(base, register)
    if register.data_type in {"time", "datetime"}:
        return _text_discovery(base, register)
    return _number_discovery(base, register)


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

    def _discovery_topic(self, component: str, key: str) -> str:
        """Build the retained Home Assistant discovery config topic."""
        return (
            f"{self._discovery_prefix}/{component}/"
            f"{self._device_id}/{key}/config"
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
            self._client.publish(
                self._discovery_topic(component, register.key),
                json.dumps(payload),
                retain=True,
            )

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
            self._client.publish(
                self._discovery_topic(component, register.key),
                json.dumps(payload),
                retain=True,
            )
