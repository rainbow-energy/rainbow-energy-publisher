"""Test MQTT measurement publishing."""

from rainbow_energy_client.decode import Measurement

from rainbow_energy_mqtt.publisher import MeasurementPublisher


class FakeMqttClient:
    """Record publish calls without a broker."""

    def __init__(self) -> None:
        """Create an empty publish log."""
        self.published: list[tuple[str, str]] = []

    def publish(self, topic: str, payload: str) -> None:
        """Record one published message."""
        self.published.append((topic, payload))


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
        ("rainbow/energy/battery_soc", "85.0"),
        ("rainbow/energy/grid_power", "-120"),
    ]
