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

    if config.modbus_tcp_host is not None:
        reader = ModbusReader.tcp(
            host=config.modbus_tcp_host,
            port=config.modbus_tcp_port,
            device_id=config.modbus_device_id,
        )
    else:
        reader = ModbusReader.serial(
            port=config.modbus_usb_port,
            device_id=config.modbus_device_id,
        )

    mqtt_client = connect_mqtt_client(
        host=config.mqtt_host,
        port=config.mqtt_port,
        username=config.mqtt_username,
        password=config.mqtt_password,
    )
    publisher = MeasurementPublisher(
        client=mqtt_client,
        topic_prefix=config.mqtt_topic_prefix,
        retain=config.mqtt_retain,
    )
    try:
        with reader:
            run_service(
                reader=reader,
                profile=profile,
                keys=config.keys,
                interval=config.interval,
                log_level=config.log_level,
                publisher=publisher,
            )
    finally:
        mqtt_client.close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
