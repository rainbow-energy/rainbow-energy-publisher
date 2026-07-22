"""Load and validate rainbow-energy-mqtt YAML configuration."""

from __future__ import annotations

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
    profile: str | None
    profile_path: Path | None
    modbus_device_id: int
    modbus_tcp_host: str | None
    modbus_tcp_port: int
    modbus_usb_port: str | None
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

    return ServiceConfig(
        interval=float(raw["interval"]),
        keys=tuple(raw["keys"]),
        profile=profile,
        profile_path=Path(profile_path) if profile_path is not None else None,
        modbus_device_id=int(modbus.get("device_id", 1)),
        modbus_tcp_host=tcp.get("host") if tcp is not None else None,
        modbus_tcp_port=int(tcp.get("port", 502)) if tcp is not None else 502,
        modbus_usb_port=usb.get("port") if usb is not None else None,
        log_level=str(raw.get("log_level", DEFAULT_LOG_LEVEL)).upper(),
    )
