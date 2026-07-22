"""Test MQTT measurement publishing."""

import json

from rainbow_energy_client.decode import Measurement

from rainbow_energy_mqtt.publisher import MeasurementPublisher


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
