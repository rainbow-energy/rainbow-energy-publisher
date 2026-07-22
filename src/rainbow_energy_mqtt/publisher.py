"""Publish decoded measurements to MQTT state topics."""

from __future__ import annotations

import json
from collections.abc import Sequence

from rainbow_energy_client.decode import Measurement

from rainbow_energy_mqtt.mqtt import MqttClient


class MeasurementPublisher:
    """Publish measurement values under a topic prefix."""

    def __init__(
        self,
        *,
        client: MqttClient,
        topic_prefix: str,
        retain: bool = True,
        device_id: str | None = None,
        discovery_prefix: str = "homeassistant",
        ha_discovery: bool = False,
    ) -> None:
        """Bind an MQTT client, topic prefix, retain flag, and discovery settings."""
        self._client = client
        self._topic_prefix = topic_prefix.rstrip("/")
        self._retain = retain
        self._device_id = device_id
        self._discovery_prefix = discovery_prefix.rstrip("/")
        self._ha_discovery = ha_discovery

    @property
    def ha_discovery(self) -> bool:
        """Return whether Home Assistant discovery should be published at startup."""
        return self._ha_discovery

    def publish(self, measurements: Sequence[Measurement]) -> None:
        """Publish each measurement value as a string payload on its state topic."""
        for measurement in measurements:
            topic = f"{self._topic_prefix}/{measurement.key}"
            self._client.publish(topic, str(measurement.value), retain=self._retain)

    def publish_discovery(
        self,
        measurements: Sequence[Measurement],
        *,
        manufacturer: str,
        model: str,
    ) -> None:
        """Publish retained Home Assistant MQTT discovery configs for sensors."""
        if self._device_id is None:
            return
        for measurement in measurements:
            topic = (
                f"{self._discovery_prefix}/sensor/"
                f"{self._device_id}/{measurement.key}/config"
            )
            payload = {
                "name": measurement.name,
                "state_topic": f"{self._topic_prefix}/{measurement.key}",
                "unique_id": f"{self._device_id}_{measurement.key}",
                "unit_of_measurement": measurement.unit,
                "state_class": "measurement",
                "device": {
                    "identifiers": [self._device_id],
                    "name": self._device_id,
                    "manufacturer": manufacturer,
                    "model": model,
                },
            }
            self._client.publish(topic, json.dumps(payload), retain=True)
