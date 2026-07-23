"""Command-line entry point for the MQTT publisher service."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rainbow_energy_client import ModbusReader, load_packaged_profile
from rainbow_energy_client.device import RegisterReader
from rainbow_energy_client.profiles import DeviceProfile, ProfileError, load_profile

from rainbow_energy_mqtt.config import ConfigError, ServiceConfig, load_config
from rainbow_energy_mqtt.mqtt import MqttClient, connect_mqtt_client
from rainbow_energy_mqtt.publisher import MeasurementPublisher
from rainbow_energy_mqtt.service import run_service


def main(argv: list[str] | None = None) -> int:
    """Load --config, open Modbus, and run the poll loop until interrupted."""
    config_path = _parse_args(argv)

    try:
        config = load_config(config_path)
    except (ConfigError, OSError, KeyError, TypeError, ValueError) as error:
        return _fail("config error", error)

    try:
        profile = _load_profile(config)
    except (OSError, ProfileError) as error:
        return _fail("profile error", error)

    reader = _open_modbus_reader(config)

    try:
        mqtt_client = _connect_mqtt(config)
    except OSError as error:
        return _fail("mqtt error", error)

    publisher = _build_publisher(config, mqtt_client)
    try:
        return _run_with_modbus(config, profile, reader, publisher)
    finally:
        mqtt_client.close()


def _parse_args(argv: list[str] | None) -> Path:
    """Parse CLI arguments and return the config path."""
    parser = argparse.ArgumentParser(prog="rainbow-energy-mqtt")
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to the service YAML config file",
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    return args.config


def _fail(prefix: str, error: BaseException) -> int:
    """Print a prefixed error to stderr and return exit code 2."""
    print(f"{prefix}: {error}", file=sys.stderr)
    return 2


def _load_profile(config: ServiceConfig) -> DeviceProfile:
    """Load the configured packaged or filesystem profile."""
    if config.profile_path is not None:
        return load_profile(config.profile_path)
    return load_packaged_profile(config.profile)


def _open_modbus_reader(config: ServiceConfig) -> RegisterReader:
    """Build a Modbus TCP or serial reader from config."""
    if config.modbus.tcp is not None:
        return ModbusReader.tcp(
            host=config.modbus.tcp.host,
            port=config.modbus.tcp.port,
            device_id=config.modbus.device_id,
        )
    assert config.modbus.usb is not None
    return ModbusReader.serial(
        port=config.modbus.usb.port,
        device_id=config.modbus.device_id,
    )


def _connect_mqtt(config: ServiceConfig) -> MqttClient:
    """Connect to the configured MQTT broker."""
    return connect_mqtt_client(
        host=config.mqtt.host,
        port=config.mqtt.port,
        username=config.mqtt.username,
        password=config.mqtt.password,
    )


def _build_publisher(
    config: ServiceConfig,
    mqtt_client: MqttClient,
) -> MeasurementPublisher:
    """Create a measurement publisher from MQTT settings."""
    return MeasurementPublisher(
        client=mqtt_client,
        topic_prefix=config.mqtt.topic_prefix,
        retain=config.mqtt.retain,
        device_id=config.mqtt.device_id,
        discovery_prefix=config.mqtt.discovery_prefix,
        ha_discovery=config.mqtt.ha_discovery,
    )


def _run_with_modbus(
    config: ServiceConfig,
    profile: DeviceProfile,
    reader: RegisterReader,
    publisher: MeasurementPublisher,
) -> int:
    """Open Modbus and run the service loop; return a process exit code."""
    try:
        with reader:
            run_service(
                reader=reader,
                profile=profile,
                keys=config.keys,
                all_keys=config.all_keys,
                interval=config.interval,
                log_level=config.log_level,
                publisher=publisher,
            )
    except OSError as error:
        return _fail("modbus error", error)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
