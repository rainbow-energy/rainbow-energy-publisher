"""Command-line entry point for the MQTT publisher service."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rainbow_energy_client import ModbusReader, load_packaged_profile
from rainbow_energy_client.profiles import ProfileError, load_profile

from rainbow_energy_mqtt.config import ConfigError, load_config
from rainbow_energy_mqtt.mqtt import connect_mqtt_client
from rainbow_energy_mqtt.publisher import MeasurementPublisher
from rainbow_energy_mqtt.service import run_service


def main(argv: list[str] | None = None) -> int:
    """Load --config, open Modbus, and run the poll loop until interrupted."""
    parser = argparse.ArgumentParser(prog="rainbow-energy-mqtt")
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to the service YAML config file",
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    try:
        config = load_config(args.config)
    except (ConfigError, OSError, KeyError, TypeError, ValueError) as error:
        print(f"config error: {error}", file=sys.stderr)
        return 2

    try:
        if config.profile_path is not None:
            profile = load_profile(config.profile_path)
        else:
            profile = load_packaged_profile(config.profile)
    except (OSError, ProfileError) as error:
        print(f"profile error: {error}", file=sys.stderr)
        return 2

    if config.modbus.tcp is not None:
        reader = ModbusReader.tcp(
            host=config.modbus.tcp.host,
            port=config.modbus.tcp.port,
            device_id=config.modbus.device_id,
        )
    else:
        assert config.modbus.usb is not None
        reader = ModbusReader.serial(
            port=config.modbus.usb.port,
            device_id=config.modbus.device_id,
        )

    try:
        mqtt_client = connect_mqtt_client(
            host=config.mqtt.host,
            port=config.mqtt.port,
            username=config.mqtt.username,
            password=config.mqtt.password,
        )
    except OSError as error:
        print(f"mqtt error: {error}", file=sys.stderr)
        return 2
    publisher = MeasurementPublisher(
        client=mqtt_client,
        topic_prefix=config.mqtt.topic_prefix,
        retain=config.mqtt.retain,
        device_id=config.mqtt.device_id,
        discovery_prefix=config.mqtt.discovery_prefix,
        ha_discovery=config.mqtt.ha_discovery,
    )
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
        print(f"modbus error: {error}", file=sys.stderr)
        return 2
    finally:
        mqtt_client.close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
