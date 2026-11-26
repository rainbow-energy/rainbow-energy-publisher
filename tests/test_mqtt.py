"""Test MQTT client connection helpers."""

from rainbow_energy_publisher.mqtt import connect_mqtt_client


def test_connect_mqtt_client_configures_broker(monkeypatch):
    """Build a connected paho client from host, port, and optional auth."""
    created: dict = {}

    class FakePaho:
        def __init__(self, *args, **kwargs):
            created["init"] = True

        def username_pw_set(self, username, password=None):
            created["auth"] = (username, password)

        def connect(self, host, port=1883, keepalive=60):
            created["connect"] = (host, port)

        def loop_start(self):
            created["loop"] = True

        def loop_stop(self):
            created["loop_stop"] = True

        def disconnect(self):
            created["disconnect"] = True

        def publish(self, topic, payload, retain=False):
            created.setdefault("published", []).append((topic, payload, retain))

        def reconnect_delay_set(self, min_delay=1, max_delay=120):
            created["reconnect_delay"] = (min_delay, max_delay)

    monkeypatch.setattr("rainbow_energy_publisher.mqtt.mqtt.Client", FakePaho)

    client = connect_mqtt_client(
        host="mqtt.example",
        port=1883,
        username="user",
        password="secret",
    )
    client.publish("rainbow/energy/battery_soc", "85.0")
    client.close()

    assert created["auth"] == ("user", "secret")
    assert created["connect"] == ("mqtt.example", 1883)
    assert created["loop"] is True
    assert created["published"] == [("rainbow/energy/battery_soc", "85.0", False)]
    assert created["loop_stop"] is True
    assert created["disconnect"] is True


def test_connect_mqtt_client_skips_auth_when_username_missing(monkeypatch):
    """Connect anonymously when no username is configured."""
    created: dict = {}

    class FakePaho:
        def __init__(self, *args, **kwargs):
            pass

        def username_pw_set(self, username, password=None):
            created["auth"] = True

        def connect(self, host, port=1883, keepalive=60):
            created["connect"] = (host, port)

        def loop_start(self):
            pass

        def reconnect_delay_set(self, min_delay=1, max_delay=120):
            pass

    monkeypatch.setattr("rainbow_energy_publisher.mqtt.mqtt.Client", FakePaho)

    connect_mqtt_client(host="mqtt.example", port=1883)

    assert "auth" not in created
    assert created["connect"] == ("mqtt.example", 1883)


def test_connect_mqtt_client_enables_automatic_reconnect(monkeypatch):
    """Enable paho reconnect-on-failure and configure backoff delays."""
    created: dict = {}

    class FakePaho:
        def __init__(self, *args, **kwargs):
            created["init_kwargs"] = kwargs

        def reconnect_delay_set(self, min_delay=1, max_delay=120):
            created["reconnect_delay"] = (min_delay, max_delay)

        def connect(self, host, port=1883, keepalive=60):
            pass

        def loop_start(self):
            pass

    monkeypatch.setattr("rainbow_energy_publisher.mqtt.mqtt.Client", FakePaho)

    connect_mqtt_client(host="mqtt.example", port=1883)

    assert created["init_kwargs"]["reconnect_on_failure"] is True
    assert created["reconnect_delay"] == (1, 120)


def test_mqtt_client_subscribe_registers_topic_callback(monkeypatch):
    """Subscribe to a topic and deliver matching payloads to the callback."""
    created: dict = {}
    seen: list[tuple[str, str]] = []

    class FakePaho:
        def __init__(self, *args, **kwargs):
            self._handlers: dict[str, object] = {}

        def reconnect_delay_set(self, min_delay=1, max_delay=120):
            pass

        def connect(self, host, port=1883, keepalive=60):
            pass

        def loop_start(self):
            pass

        def loop_stop(self):
            pass

        def disconnect(self):
            pass

        def subscribe(self, topic, qos=0):
            created["subscribe"] = (topic, qos)

        def message_callback_add(self, topic, callback):
            self._handlers[topic] = callback
            created["handler_topic"] = topic

        def publish(self, topic, payload, retain=False):
            pass

    monkeypatch.setattr("rainbow_energy_publisher.mqtt.mqtt.Client", FakePaho)

    client = connect_mqtt_client(host="mqtt.example", port=1883)

    def on_message(topic: str, payload: str) -> None:
        seen.append((topic, payload))

    client.subscribe("rainbow/energy/+/set", on_message)

    handler = client._client._handlers["rainbow/energy/+/set"]
    message = type(
        "Msg",
        (),
        {"topic": "rainbow/energy/grid_charge_enabled/set", "payload": b"true"},
    )()
    handler(None, None, message)
    text_message = type(
        "Msg",
        (),
        {"topic": "rainbow/energy/grid_charge_enabled/set", "payload": "false"},
    )()
    handler(None, None, text_message)

    assert created["subscribe"] == ("rainbow/energy/+/set", 0)
    assert created["handler_topic"] == "rainbow/energy/+/set"
    assert seen == [
        ("rainbow/energy/grid_charge_enabled/set", "true"),
        ("rainbow/energy/grid_charge_enabled/set", "false"),
    ]
