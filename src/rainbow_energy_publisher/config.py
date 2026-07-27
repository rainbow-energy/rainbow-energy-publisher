"""Load and validate rainbow-energy-publisher YAML configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_LOG_LEVEL = "INFO"


class ConfigError(ValueError):
    """Raised when service configuration is missing or invalid."""


@dataclass(frozen=True, slots=True)
class ModbusTcpConfig:
    """Modbus TCP gateway settings."""

    host: str
    port: int


@dataclass(frozen=True, slots=True)
class ModbusUsbConfig:
    """Modbus RTU serial port settings."""

    port: str


@dataclass(frozen=True, slots=True)
class ModbusConfig:
    """Modbus transport settings (exactly one of tcp or usb)."""

    device_id: int
    tcp: ModbusTcpConfig | None
    usb: ModbusUsbConfig | None


@dataclass(frozen=True, slots=True)
class MqttConfig:
    """MQTT broker and publish settings."""

    host: str
    port: int
    topic_prefix: str
    username: str | None
    password: str | None
    retain: bool
    device_id: str | None
    ha_discovery: bool
    discovery_prefix: str


@dataclass(frozen=True, slots=True)
class ServiceConfig:
    """Settings for the long-running Modbus poll service."""

    interval: float
    keys: tuple[str, ...]
    all_keys: bool
    profile: str | None
    profile_path: Path | None
    modbus: ModbusConfig
    mqtt: MqttConfig
    log_level: str


def load_config(path: Path) -> ServiceConfig:
    """Load service settings from a YAML config file."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ConfigError(f"cannot read config {path}: {error}") from error

    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ConfigError(f"invalid YAML: {error}") from error

    root = _require_mapping(raw, "config")

    profile = root.get("profile")
    profile_path = root.get("profile_path")
    if (profile is None) == (profile_path is None):
        raise ConfigError("set exactly one of profile or profile_path")

    keys, all_keys = _parse_keys(root.get("keys"))

    return ServiceConfig(
        interval=_as_float(_require(root, "interval", "interval"), "interval"),
        keys=keys,
        all_keys=all_keys,
        profile=profile,
        profile_path=Path(profile_path) if profile_path is not None else None,
        modbus=_load_modbus(root.get("modbus")),
        mqtt=_load_mqtt(root.get("mqtt")),
        log_level=str(root.get("log_level", DEFAULT_LOG_LEVEL)).upper(),
    )


def _load_modbus(raw: object) -> ModbusConfig:
    """Parse the modbus section into ModbusConfig."""
    modbus = _require_mapping(raw, "modbus")
    tcp_raw = modbus.get("tcp")
    usb_raw = modbus.get("usb")
    if (tcp_raw is None) == (usb_raw is None):
        raise ConfigError("set exactly one of modbus.tcp or modbus.usb")

    tcp: ModbusTcpConfig | None = None
    usb: ModbusUsbConfig | None = None
    if tcp_raw is not None:
        tcp_mapping = _require_mapping(tcp_raw, "modbus.tcp")
        tcp = ModbusTcpConfig(
            host=str(_require(tcp_mapping, "host", "modbus.tcp.host")),
            port=_as_int(tcp_mapping.get("port", 502), "modbus.tcp.port"),
        )
    if usb_raw is not None:
        usb_mapping = _require_mapping(usb_raw, "modbus.usb")
        usb = ModbusUsbConfig(
            port=str(_require(usb_mapping, "port", "modbus.usb.port")),
        )

    return ModbusConfig(
        device_id=_as_int(modbus.get("device_id", 1), "modbus.device_id"),
        tcp=tcp,
        usb=usb,
    )


def _load_mqtt(raw: object) -> MqttConfig:
    """Parse the mqtt section into MqttConfig."""
    mqtt = _require_mapping(raw, "mqtt")
    return MqttConfig(
        host=str(_require(mqtt, "host", "mqtt.host")),
        port=_as_int(mqtt.get("port", 1883), "mqtt.port"),
        topic_prefix=str(_require(mqtt, "topic_prefix", "mqtt.topic_prefix")),
        username=_optional_secret("MQTT_USERNAME", mqtt.get("username")),
        password=_optional_secret("MQTT_PASSWORD", mqtt.get("password")),
        retain=bool(mqtt.get("retain", True)),
        device_id=(
            None if mqtt.get("device_id") is None else str(mqtt.get("device_id"))
        ),
        ha_discovery=bool(mqtt.get("ha_discovery", False)),
        discovery_prefix=str(mqtt.get("discovery_prefix", "homeassistant")),
    )


def _require_mapping(value: object, path: str) -> dict[str, Any]:
    """Return *value* as a mapping or raise ConfigError."""
    if value is None:
        raise ConfigError(f"missing {path}")
    if not isinstance(value, dict):
        raise ConfigError(f"{path} must be a mapping")
    return value


def _require(mapping: dict[str, Any], key: str, path: str) -> object:
    """Return mapping[key] or raise ConfigError when missing/null."""
    if key not in mapping or mapping[key] is None:
        raise ConfigError(f"missing {path}")
    return mapping[key]


def _as_float(value: object, path: str) -> float:
    """Parse *value* as float or raise ConfigError."""
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise ConfigError(f"invalid {path}: {value!r}") from error


def _as_int(value: object, path: str) -> int:
    """Parse *value* as int or raise ConfigError."""
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise ConfigError(f"invalid {path}: {value!r}") from error


def _parse_keys(raw_keys: object) -> tuple[tuple[str, ...], bool]:
    """Return keys and whether to expand to all readable profile registers."""
    if raw_keys == "*":
        return (), True
    if isinstance(raw_keys, list):
        return tuple(raw_keys), False
    raise ConfigError('keys must be a list of names or "*"')


def _optional_secret(env_name: str, yaml_value: object) -> str | None:
    """Return an env override, else the YAML value, else None."""
    if env_name in os.environ:
        value = os.environ[env_name]
    else:
        value = yaml_value
    if value is None:
        return None
    text = str(value)
    return text or None
