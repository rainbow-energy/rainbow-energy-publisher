"""MQTT broker connection helpers."""

from __future__ import annotations

import paho.mqtt.client as mqtt


class MqttClient:
    """Library-backed MQTT client used by the measurement publisher."""

    def __init__(self, client: mqtt.Client) -> None:
        """Wrap a connected client from the configured MQTT library."""
        self._client = client

    def publish(self, topic: str, payload: str) -> None:
        """Publish one message to a topic."""
        self._client.publish(topic, payload)

    def close(self) -> None:
        """Stop the network loop and disconnect."""
        self._client.loop_stop()
        self._client.disconnect()


def connect_mqtt_client(
    *,
    host: str,
    port: int = 1883,
    username: str | None = None,
    password: str | None = None,
) -> MqttClient:
    """Connect to an MQTT broker and return a publisher-ready client."""
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    if username is not None:
        client.username_pw_set(username, password)
    client.connect(host, port)
    client.loop_start()
    return MqttClient(client)
