"""Test MQTT client connection helpers."""

from rainbow_energy_mqtt.mqtt import connect_mqtt_client


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

    monkeypatch.setattr("rainbow_energy_mqtt.mqtt.mqtt.Client", FakePaho)

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

    monkeypatch.setattr("rainbow_energy_mqtt.mqtt.mqtt.Client", FakePaho)

    connect_mqtt_client(host="mqtt.example", port=1883)

    assert "auth" not in created
    assert created["connect"] == ("mqtt.example", 1883)
