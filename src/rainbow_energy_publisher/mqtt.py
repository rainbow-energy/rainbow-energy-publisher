"""MQTT broker connection helpers."""

from __future__ import annotations

from collections.abc import Callable

import paho.mqtt.client as mqtt

MessageCallback = Callable[[str, str], None]


class MqttClient:
    """Library-backed MQTT client used by the measurement publisher."""

    def __init__(self, client: mqtt.Client) -> None:
        """Wrap a connected client from the configured MQTT library."""
        self._client = client

    def publish(self, topic: str, payload: str, *, retain: bool = False) -> None:
        """Publish one message to a topic."""
        self._client.publish(topic, payload, retain=retain)

    def subscribe(self, topic: str, callback: MessageCallback) -> None:
        """Subscribe to *topic* and invoke *callback(topic, payload)* on messages."""

        def _on_message(_client: object, _userdata: object, message: object) -> None:
            topic_text = str(getattr(message, "topic"))
            raw = getattr(message, "payload")
            if isinstance(raw, bytes):
                payload = raw.decode("utf-8", errors="replace")
            else:
                payload = str(raw)
            callback(topic_text, payload)

        self._client.message_callback_add(topic, _on_message)
        self._client.subscribe(topic)

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
    """Connect to an MQTT broker and return a publisher-ready client.

    The underlying paho client reconnects automatically if the broker
    connection drops while the network loop is running.
    """
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        reconnect_on_failure=True,
    )
    client.reconnect_delay_set(min_delay=1, max_delay=120)
    if username is not None:
        client.username_pw_set(username, password)
    client.connect(host, port)
    client.loop_start()
    return MqttClient(client)
