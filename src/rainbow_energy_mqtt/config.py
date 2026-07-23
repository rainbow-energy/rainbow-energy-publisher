"""Load and validate rainbow-energy-mqtt YAML configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_LOG_LEVEL = "INFO"


class ConfigError(ValueError):
    """Raised when service configuration is missing or invalid."""


@dataclass(frozen=True, slots=True)
class ServiceConfig:
    """Settings for the long-running Modbus poll service."""

    interval: float
    keys: tuple[str, ...]
    all_keys: bool
    profile: str | None
    profile_path: Path | None
    modbus_device_id: int
    modbus_tcp_host: str | None
    modbus_tcp_port: int
    modbus_usb_port: str | None
    mqtt_host: str
    mqtt_port: int
    mqtt_topic_prefix: str
    mqtt_username: str | None
    mqtt_password: str | None
    mqtt_retain: bool
    mqtt_device_id: str | None
    mqtt_ha_discovery: bool
    mqtt_discovery_prefix: str
    log_level: str


def load_config(path: Path) -> ServiceConfig:
    """Load service settings from a YAML config file."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    profile = raw.get("profile")
    profile_path = raw.get("profile_path")
    if (profile is None) == (profile_path is None):
        raise ConfigError("set exactly one of profile or profile_path")

    modbus = raw["modbus"]
    tcp = modbus.get("tcp")
    usb = modbus.get("usb")
    if (tcp is None) == (usb is None):
        raise ConfigError("set exactly one of modbus.tcp or modbus.usb")

    mqtt = raw["mqtt"]
    keys, all_keys = _parse_keys(raw.get("keys"))

    return ServiceConfig(
        interval=float(raw["interval"]),
        keys=keys,
        all_keys=all_keys,
        profile=profile,
        profile_path=Path(profile_path) if profile_path is not None else None,
        modbus_device_id=int(modbus.get("device_id", 1)),
        modbus_tcp_host=tcp.get("host") if tcp is not None else None,
        modbus_tcp_port=int(tcp.get("port", 502)) if tcp is not None else 502,
        modbus_usb_port=usb.get("port") if usb is not None else None,
        mqtt_host=str(mqtt["host"]),
        mqtt_port=int(mqtt.get("port", 1883)),
        mqtt_topic_prefix=str(mqtt["topic_prefix"]),
        mqtt_username=_optional_secret("MQTT_USERNAME", mqtt.get("username")),
        mqtt_password=_optional_secret("MQTT_PASSWORD", mqtt.get("password")),
        mqtt_retain=bool(mqtt.get("retain", True)),
        mqtt_device_id=(
            None if mqtt.get("device_id") is None else str(mqtt.get("device_id"))
        ),
        mqtt_ha_discovery=bool(mqtt.get("ha_discovery", False)),
        mqtt_discovery_prefix=str(mqtt.get("discovery_prefix", "homeassistant")),
        log_level=str(raw.get("log_level", DEFAULT_LOG_LEVEL)).upper(),
    )


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
