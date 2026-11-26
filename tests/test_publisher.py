"""Test MQTT measurement publishing."""

import json

from rainbow_energy_modbus_client.decode import Measurement
from rainbow_energy_modbus_client.profiles import RegisterDefinition

from rainbow_energy_publisher.publisher import (
    MeasurementPublisher,
    control_discovery_config,
)


class FakeMqttClient:
    """Record publish calls without a broker."""

    def __init__(self) -> None:
        """Create an empty publish log."""
        self.published: list[tuple[str, str, bool]] = []

    def publish(self, topic: str, payload: str, *, retain: bool = False) -> None:
        """Record one published message."""
        self.published.append((topic, payload, retain))


def test_publish_measurements_writes_state_topics():
    """Publish each measurement value under the configured topic prefix."""
    client = FakeMqttClient()
    publisher = MeasurementPublisher(client=client, topic_prefix="rainbow/energy")

    publisher.publish(
        (
            Measurement(key="battery_soc", name="Battery SOC", value=85.0, unit="%"),
            Measurement(key="grid_power", name="Grid Power", value=-120, unit="W"),
        )
    )

    assert client.published == [
        ("rainbow/energy/battery_soc", "85.0", True),
        ("rainbow/energy/grid_power", "-120", True),
    ]


def test_publish_measurements_honours_retain_false():
    """Pass retain=False through to each MQTT publish when configured."""
    client = FakeMqttClient()
    publisher = MeasurementPublisher(
        client=client,
        topic_prefix="rainbow/energy",
        retain=False,
    )

    publisher.publish(
        (Measurement(key="battery_soc", name="Battery SOC", value=85.0, unit="%"),)
    )

    assert client.published == [
        ("rainbow/energy/battery_soc", "85.0", False),
    ]


def test_publish_measurements_formats_bool_as_lowercase_true_false():
    """Publish boolean values as true/false to match switch command payloads."""
    client = FakeMqttClient()
    publisher = MeasurementPublisher(client=client, topic_prefix="rainbow/energy")

    publisher.publish(
        (
            Measurement(
                key="grid_charge_enabled",
                name="Grid Charge Enabled",
                value=True,
                unit="",
            ),
            Measurement(
                key="solar_export",
                name="Solar Export",
                value=False,
                unit="",
            ),
        )
    )

    assert client.published == [
        ("rainbow/energy/grid_charge_enabled", "true", True),
        ("rainbow/energy/solar_export", "false", True),
    ]


def test_publish_discovery_writes_ha_sensor_config():
    """Publish a retained Home Assistant MQTT discovery config for a sensor."""
    client = FakeMqttClient()
    publisher = MeasurementPublisher(
        client=client,
        topic_prefix="rainbow/energy",
        device_id="inverter-1",
        discovery_prefix="homeassistant",
    )

    publisher.publish_discovery(
        (
            Measurement(key="battery_soc", name="Battery SOC", value=85.0, unit="%"),
        ),
        manufacturer="Sunsynk",
        model="SYNK-8K-SG05LP1",
    )

    assert len(client.published) == 1
    topic, payload, retain = client.published[0]
    assert topic == "homeassistant/sensor/inverter-1/battery_soc/config"
    assert retain is True
    assert json.loads(payload) == {
        "name": "Battery SOC",
        "state_topic": "rainbow/energy/battery_soc",
        "unique_id": "inverter-1_battery_soc",
        "unit_of_measurement": "%",
        "state_class": "measurement",
        "device": {
            "identifiers": ["inverter-1"],
            "name": "inverter-1",
            "manufacturer": "Sunsynk",
            "model": "SYNK-8K-SG05LP1",
        },
    }


def test_publish_discovery_marks_energy_counters_for_ha_energy():
    """Use total_increasing + energy device_class for Wh/kWh sensors."""
    client = FakeMqttClient()
    publisher = MeasurementPublisher(
        client=client,
        topic_prefix="rainbow/energy",
        device_id="inverter-1",
    )

    publisher.publish_discovery(
        (
            Measurement(
                key="day_pv_energy",
                name="Day PV Energy",
                value=12.5,
                unit="kWh",
            ),
            Measurement(
                key="total_grid_import",
                name="Total Grid Import",
                value=1000,
                unit="Wh",
            ),
        ),
        manufacturer="Sunsynk",
        model="8K",
    )

    payloads = [json.loads(payload) for _topic, payload, _retain in client.published]
    assert payloads[0]["state_class"] == "total_increasing"
    assert payloads[0]["device_class"] == "energy"
    assert payloads[0]["unit_of_measurement"] == "kWh"
    assert payloads[1]["state_class"] == "total_increasing"
    assert payloads[1]["device_class"] == "energy"
    assert payloads[1]["unit_of_measurement"] == "Wh"


def test_publish_discovery_skips_when_device_id_missing():
    """Do not publish discovery configs without a configured device_id."""
    client = FakeMqttClient()
    publisher = MeasurementPublisher(client=client, topic_prefix="rainbow/energy")

    publisher.publish_discovery(
        (Measurement(key="battery_soc", name="Battery SOC", value=85.0, unit="%"),),
        manufacturer="Sunsynk",
        model="SYNK-8K-SG05LP1",
    )

    assert client.published == []


def _write_register(**overrides) -> RegisterDefinition:
    values = {
        "key": "export_limit",
        "name": "Export Limit",
        "address": 200,
        "function": "holding",
        "data_type": "uint16",
        "scale": 1.0,
        "unit": "W",
        "access": "write",
        "count": 1,
    }
    values.update(overrides)
    return RegisterDefinition(**values)


def test_control_discovery_config_maps_binary_to_switch():
    """Map binary writable registers to Home Assistant switch discovery."""
    register = _write_register(
        key="grid_charge_enabled",
        name="Grid Charge Enabled",
        unit="",
        binary=True,
        bitmask=0x1,
    )

    component, payload = control_discovery_config(
        register,
        topic_prefix="rainbow/energy",
        device_id="inverter-1",
        manufacturer="Sunsynk",
        model="8K",
    )

    assert component == "switch"
    assert payload["command_topic"] == "rainbow/energy/grid_charge_enabled/set"
    assert payload["state_topic"] == "rainbow/energy/grid_charge_enabled"
    assert payload["payload_on"] == "true"
    assert payload["payload_off"] == "false"


def test_control_discovery_config_maps_options_to_select():
    """Map options writable registers to Home Assistant select discovery."""
    register = _write_register(
        key="aux_port_usage",
        name="AUX Port Usage",
        unit="",
        options={0: "Disable", 1: "Smartload", 2: "Generator"},
    )

    component, payload = control_discovery_config(
        register,
        topic_prefix="rainbow/energy",
        device_id="inverter-1",
        manufacturer="Sunsynk",
        model="8K",
    )

    assert component == "select"
    assert payload["options"] == ["Disable", "Smartload", "Generator"]
    assert payload["command_topic"] == "rainbow/energy/aux_port_usage/set"


def test_control_discovery_config_maps_numeric_to_number():
    """Map scaled numeric writable registers to Home Assistant number discovery."""
    register = _write_register()

    component, payload = control_discovery_config(
        register,
        topic_prefix="rainbow/energy",
        device_id="inverter-1",
        manufacturer="Sunsynk",
        model="8K",
    )

    assert component == "number"
    assert payload["unit_of_measurement"] == "W"
    assert payload["command_topic"] == "rainbow/energy/export_limit/set"


def test_control_discovery_config_skips_time_and_datetime():
    """Do not discover time or datetime writable registers yet."""
    assert (
        control_discovery_config(
            _write_register(key="prog1_time", name="Prog1 Time", data_type="time", unit=""),
            topic_prefix="rainbow/energy",
            device_id="inverter-1",
            manufacturer="Sunsynk",
            model="8K",
        )
        is None
    )
    assert (
        control_discovery_config(
            _write_register(
                key="date_time",
                name="Date Time",
                data_type="datetime",
                count=3,
                unit="",
            ),
            topic_prefix="rainbow/energy",
            device_id="inverter-1",
            manufacturer="Sunsynk",
            model="8K",
        )
        is None
    )


def test_control_discovery_config_skips_non_writable_registers():
    """Ignore read-only registers when building control discovery."""
    register = RegisterDefinition(
        key="battery_soc",
        name="Battery SOC",
        address=184,
        function="holding",
        data_type="uint16",
        scale=1.0,
        unit="%",
        access="read",
        count=1,
    )
    assert (
        control_discovery_config(
            register,
            topic_prefix="rainbow/energy",
            device_id="inverter-1",
            manufacturer="Sunsynk",
            model="8K",
        )
        is None
    )


def test_publish_control_discovery_writes_ha_configs():
    """Publish retained switch/number/select discovery configs for writable keys."""
    client = FakeMqttClient()
    publisher = MeasurementPublisher(
        client=client,
        topic_prefix="rainbow/energy",
        device_id="inverter-1",
    )

    publisher.publish_control_discovery(
        (
            _write_register(
                key="grid_charge_enabled",
                name="Grid Charge Enabled",
                unit="",
                binary=True,
            ),
            _write_register(),
            _write_register(
                key="aux_port_usage",
                name="AUX Port Usage",
                unit="",
                options={0: "Disable", 1: "Smartload"},
            ),
            _write_register(key="prog1_time", name="Prog1 Time", data_type="time", unit=""),
        ),
        manufacturer="Sunsynk",
        model="8K",
    )

    topics = [topic for topic, _payload, _retain in client.published]
    assert topics == [
        "homeassistant/switch/inverter-1/grid_charge_enabled/config",
        "homeassistant/number/inverter-1/export_limit/config",
        "homeassistant/select/inverter-1/aux_port_usage/config",
    ]
    assert all(retain for _topic, _payload, retain in client.published)


def test_publish_control_discovery_skips_when_device_id_missing():
    """Do not publish control discovery configs without a configured device_id."""
    client = FakeMqttClient()
    publisher = MeasurementPublisher(client=client, topic_prefix="rainbow/energy")

    publisher.publish_control_discovery(
        (_write_register(),),
        manufacturer="Sunsynk",
        model="8K",
    )

    assert client.published == []
