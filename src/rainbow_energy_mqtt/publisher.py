"""Publish decoded measurements to MQTT state topics."""

from __future__ import annotations

from collections.abc import Sequence

from rainbow_energy_client.decode import Measurement

from rainbow_energy_mqtt.mqtt import MqttClient


class MeasurementPublisher:
    """Publish measurement values under a topic prefix."""

    def __init__(self, *, client: MqttClient, topic_prefix: str) -> None:
        """Bind an MQTT client and topic prefix (for example rainbow/energy)."""
        self._client = client
        self._topic_prefix = topic_prefix.rstrip("/")

    def publish(self, measurements: Sequence[Measurement]) -> None:
        """Publish each measurement value as a string payload on its state topic."""
        for measurement in measurements:
            topic = f"{self._topic_prefix}/{measurement.key}"
            self._client.publish(topic, str(measurement.value))
