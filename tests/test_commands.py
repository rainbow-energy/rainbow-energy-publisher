"""Test MQTT command topic parsing and write queueing."""

from __future__ import annotations

import logging

from rainbow_energy_modbus_client.profiles import DeviceProfile, RegisterDefinition

from rainbow_energy_publisher.commands import (
    CommandQueue,
    handle_command_message,
    parse_command_payload,
    writable_keys,
)


def _write_register(key: str, *, address: int = 217) -> RegisterDefinition:
    return RegisterDefinition(
        key=key,
        name=key,
        address=address,
        function="holding",
        data_type="uint16",
        scale=1.0,
        unit="",
        access="write",
        count=1,
    )


def _read_register(key: str, *, address: int = 184) -> RegisterDefinition:
    return RegisterDefinition(
        key=key,
        name=key,
        address=address,
        function="holding",
        data_type="uint16",
        scale=1.0,
        unit="",
        access="read",
        count=1,
    )


def test_parse_command_payload_coerces_bool_int_float_and_string():
    """Coerce MQTT payloads the same way as the client CLI --set values."""
    assert parse_command_payload("true") is True
    assert parse_command_payload("FALSE") is False
    assert parse_command_payload("20") == 20
    assert parse_command_payload("1.5") == 1.5
    assert parse_command_payload("1:30") == "1:30"
    assert parse_command_payload("Smartload") == "Smartload"


def test_writable_keys_returns_access_write_register_keys():
    """Collect only access: write leaf keys from the profile."""
    profile = DeviceProfile(
        manufacturer="Example",
        model="8K",
        registers=(
            _read_register("battery_soc"),
            _write_register("battery_shutdown_capacity"),
            _write_register("grid_charge_enabled", address=232),
        ),
    )

    assert writable_keys(profile) == {
        "battery_shutdown_capacity",
        "grid_charge_enabled",
    }


def test_handle_command_message_enqueues_writable_key():
    """Enqueue a coerced value for a matching topic_prefix/key/set message."""
    queue = CommandQueue()
    allowed = {"battery_shutdown_capacity"}

    handle_command_message(
        topic="rainbow/energy/battery_shutdown_capacity/set",
        payload="20",
        topic_prefix="rainbow/energy",
        allowed_keys=allowed,
        queue=queue,
    )

    assert queue.drain() == {"battery_shutdown_capacity": 20}


def test_handle_command_message_ignores_non_writable_key(caplog):
    """Skip unknown or read-only keys with a warning."""
    queue = CommandQueue()

    with caplog.at_level(logging.WARNING):
        handle_command_message(
            topic="rainbow/energy/battery_soc/set",
            payload="50",
            topic_prefix="rainbow/energy",
            allowed_keys={"battery_shutdown_capacity"},
            queue=queue,
        )

    assert queue.drain() == {}
    assert "battery_soc" in caplog.text


def test_handle_command_message_ignores_non_set_topic():
    """Ignore topics that are not under topic_prefix/<key>/set."""
    queue = CommandQueue()

    handle_command_message(
        topic="rainbow/energy/battery_shutdown_capacity",
        payload="20",
        topic_prefix="rainbow/energy",
        allowed_keys={"battery_shutdown_capacity"},
        queue=queue,
    )

    assert queue.drain() == {}


def test_handle_command_message_ignores_nested_key_path():
    """Ignore /set topics whose key segment contains further slashes."""
    queue = CommandQueue()

    handle_command_message(
        topic="rainbow/energy/nested/key/set",
        payload="20",
        topic_prefix="rainbow/energy",
        allowed_keys={"nested/key", "key"},
        queue=queue,
    )

    assert queue.drain() == {}


def test_command_queue_merges_latest_value_per_key():
    """Keep the latest queued value when the same key is commanded twice."""
    queue = CommandQueue()
    allowed = {"battery_shutdown_capacity"}

    handle_command_message(
        topic="rainbow/energy/battery_shutdown_capacity/set",
        payload="10",
        topic_prefix="rainbow/energy",
        allowed_keys=allowed,
        queue=queue,
    )
    handle_command_message(
        topic="rainbow/energy/battery_shutdown_capacity/set",
        payload="20",
        topic_prefix="rainbow/energy",
        allowed_keys=allowed,
        queue=queue,
    )

    assert queue.drain() == {"battery_shutdown_capacity": 20}
    assert queue.drain() == {}


def test_subscribe_commands_wires_wildcard_set_topic():
    """Subscribe to topic_prefix/+/set and enqueue matching writable keys."""
    from rainbow_energy_publisher.commands import subscribe_commands

    subscribed: list[tuple[str, object]] = []

    class FakeMqtt:
        def subscribe(self, topic: str, callback) -> None:
            subscribed.append((topic, callback))

    queue = CommandQueue()
    mqtt = FakeMqtt()
    subscribe_commands(
        client=mqtt,  # type: ignore[arg-type]
        topic_prefix="rainbow/energy",
        allowed_keys={"battery_shutdown_capacity"},
        queue=queue,
    )

    assert len(subscribed) == 1
    topic, callback = subscribed[0]
    assert topic == "rainbow/energy/+/set"
    callback("rainbow/energy/battery_shutdown_capacity/set", "20")
    assert queue.drain() == {"battery_shutdown_capacity": 20}
