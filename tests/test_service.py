"""Test the long-running service loop and CLI entry point."""

import logging
from pathlib import Path

from rainbow_energy_modbus_client.profiles import DeviceProfile, ProfileError, RegisterDefinition
from rainbow_energy_modbus_client.reader import RegisterData, RegisterReadError

from rainbow_energy_publisher.cli import main
from rainbow_energy_publisher.publisher import MeasurementPublisher
from rainbow_energy_publisher.service import configure_logging, run_service


class FakeReader:
    """Return canned register values without Modbus hardware."""

    def __init__(self, values: tuple[int, ...] = (85,)) -> None:
        """Store values returned by reads."""
        self.values = values
        self.reads = 0

    def read_holding_registers(self, start_address: int, count: int) -> RegisterData:
        """Return canned holding-register values."""
        self.reads += 1
        return RegisterData(device_id=1, start_address=start_address, values=self.values)

    def read_input_registers(self, start_address: int, count: int) -> RegisterData:
        """Return canned input-register values."""
        self.reads += 1
        return RegisterData(device_id=1, start_address=start_address, values=self.values)


def _profile() -> DeviceProfile:
    return DeviceProfile(
        manufacturer="Example",
        model="8K",
        registers=(
            RegisterDefinition(
                key="battery_soc",
                name="Battery SOC",
                address=184,
                function="holding",
                data_type="uint16",
                scale=1.0,
                unit="%",
                access="read",
                count=1,
            ),
        ),
    )


def test_run_service_fetches_measurements_each_tick(caplog):
    """Poll the client on each service tick and log the readings."""
    reader = FakeReader(values=(85,))

    with caplog.at_level(logging.INFO):
        run_service(
            reader=reader,
            profile=_profile(),
            keys=("battery_soc",),
            interval=0.5,
            sleep=lambda _seconds: None,
            iterations=2,
        )

    assert reader.reads == 2
    assert "battery_soc=85.0 %" in caplog.text


def test_run_service_expands_all_keys_to_readable_registers(caplog):
    """When all_keys is set, poll every access=read register from the profile."""
    profile = DeviceProfile(
        manufacturer="Example",
        model="8K",
        registers=(
            RegisterDefinition(
                key="battery_soc",
                name="Battery SOC",
                address=184,
                function="holding",
                data_type="uint16",
                scale=1.0,
                unit="%",
                access="read",
                count=1,
            ),
            RegisterDefinition(
                key="grid_power",
                name="Grid Power",
                address=185,
                function="holding",
                data_type="int16",
                scale=1.0,
                unit="W",
                access="read",
                count=1,
            ),
            RegisterDefinition(
                key="export_limit",
                name="Export Limit",
                address=200,
                function="holding",
                data_type="uint16",
                scale=1.0,
                unit="W",
                access="write",
                count=1,
            ),
        ),
    )
    reader = FakeReader(values=(85, 85))

    with caplog.at_level(logging.INFO):
        run_service(
            reader=reader,
            profile=profile,
            keys=(),
            all_keys=True,
            interval=0.5,
            sleep=lambda _seconds: None,
            iterations=1,
        )

    assert "battery_soc=85.0 %" in caplog.text
    assert "grid_power=" in caplog.text
    assert "export_limit" not in caplog.text


def test_run_service_publishes_measurements_each_tick():
    """Hand each successful poll to the measurement publisher."""
    published: list[tuple[str, str]] = []

    class FakeMqtt:
        def publish(self, topic: str, payload: str, *, retain: bool = False) -> None:
            published.append((topic, payload))

        def close(self) -> None:
            return None

    run_service(
        reader=FakeReader(values=(85,)),
        profile=_profile(),
        keys=("battery_soc",),
        interval=0.5,
        sleep=lambda _seconds: None,
        iterations=2,
        publisher=MeasurementPublisher(client=FakeMqtt(), topic_prefix="rainbow/energy"),
    )

    assert published == [
        ("rainbow/energy/battery_soc", "85.0"),
        ("rainbow/energy/battery_soc", "85.0"),
    ]


def test_run_service_publishes_discovery_once_at_start():
    """Publish Home Assistant discovery once before the poll loop when enabled."""
    published: list[tuple[str, str, bool]] = []

    class FakeMqtt:
        def publish(self, topic: str, payload: str, *, retain: bool = False) -> None:
            published.append((topic, payload, retain))

    run_service(
        reader=FakeReader(values=(85,)),
        profile=_profile(),
        keys=("battery_soc",),
        interval=0.5,
        sleep=lambda _seconds: None,
        iterations=2,
        publisher=MeasurementPublisher(
            client=FakeMqtt(),
            topic_prefix="rainbow/energy",
            device_id="inverter-1",
            ha_discovery=True,
        ),
    )

    discovery = [item for item in published if item[0].endswith("/config")]
    assert len(discovery) == 1
    assert discovery[0][0] == "homeassistant/sensor/inverter-1/battery_soc/config"
    assert discovery[0][2] is True
    assert published[0] == discovery[0]
    assert [item[:2] for item in published[1:]] == [
        ("rainbow/energy/battery_soc", "85.0"),
        ("rainbow/energy/battery_soc", "85.0"),
    ]


def test_run_service_continues_when_publish_fails(caplog):
    """Log publish failures and keep polling on later ticks."""
    reader = FakeReader(values=(85,))

    class BoomMqtt:
        def publish(self, topic: str, payload: str, *, retain: bool = False) -> None:
            raise OSError("broker unavailable")

    with caplog.at_level(logging.ERROR):
        run_service(
            reader=reader,
            profile=_profile(),
            keys=("battery_soc",),
            interval=0.5,
            sleep=lambda _seconds: None,
            iterations=2,
            publisher=MeasurementPublisher(
                client=BoomMqtt(),
                topic_prefix="rainbow/energy",
            ),
        )

    assert reader.reads == 2
    assert "publish failed" in caplog.text


def test_run_service_continues_when_discovery_publish_fails(caplog):
    """Log discovery publish failures and still run the poll loop."""
    reader = FakeReader(values=(85,))

    class BoomMqtt:
        def publish(self, topic: str, payload: str, *, retain: bool = False) -> None:
            if topic.endswith("/config"):
                raise OSError("broker unavailable")

    with caplog.at_level(logging.ERROR):
        run_service(
            reader=reader,
            profile=_profile(),
            keys=("battery_soc",),
            interval=0.5,
            sleep=lambda _seconds: None,
            iterations=1,
            publisher=MeasurementPublisher(
                client=BoomMqtt(),
                topic_prefix="rainbow/energy",
                device_id="inverter-1",
                ha_discovery=True,
            ),
        )

    assert reader.reads == 1
    assert "discovery publish failed" in caplog.text


def test_run_service_warns_when_discovery_enabled_without_device_id(caplog):
    """Warn when ha_discovery is enabled but device_id is missing."""
    published: list[tuple[str, str, bool]] = []

    class FakeMqtt:
        def publish(self, topic: str, payload: str, *, retain: bool = False) -> None:
            published.append((topic, payload, retain))

    with caplog.at_level(logging.WARNING):
        run_service(
            reader=FakeReader(values=(85,)),
            profile=_profile(),
            keys=("battery_soc",),
            interval=0.5,
            sleep=lambda _seconds: None,
            iterations=1,
            publisher=MeasurementPublisher(
                client=FakeMqtt(),
                topic_prefix="rainbow/energy",
                ha_discovery=True,
            ),
        )

    assert "device_id" in caplog.text
    assert not any(topic.endswith("/config") for topic, _payload, _retain in published)


def test_run_service_warns_once_for_unknown_keys(caplog):
    """Warn for keys missing from the profile and still poll known keys."""
    reader = FakeReader(values=(85,))

    with caplog.at_level(logging.WARNING):
        run_service(
            reader=reader,
            profile=_profile(),
            keys=("battery_soc", "not_a_real_key"),
            interval=0.5,
            sleep=lambda _seconds: None,
            iterations=1,
        )

    assert "not_a_real_key" in caplog.text
    assert "unknown key" in caplog.text
    assert reader.reads == 1


def test_run_service_stops_when_all_keys_are_unknown(caplog):
    """Stop without polling when every configured key is missing from the profile."""
    reader = FakeReader(values=(85,))

    with caplog.at_level(logging.ERROR):
        run_service(
            reader=reader,
            profile=_profile(),
            keys=("not_a_real_key",),
            interval=0.5,
            sleep=lambda _seconds: None,
            iterations=1,
        )

    assert "no known keys" in caplog.text
    assert reader.reads == 0


def test_run_service_stops_on_interrupt():
    """Stop cleanly when a tick sleep raises KeyboardInterrupt."""
    ticks: list[float] = []

    def sleep(seconds: float) -> None:
        ticks.append(seconds)
        raise KeyboardInterrupt

    run_service(
        reader=FakeReader(),
        profile=_profile(),
        keys=("battery_soc",),
        interval=0.5,
        sleep=sleep,
    )

    assert ticks == [0.5]


def test_run_service_logs_poll_errors_and_continues(caplog):
    """Log ClientError from a failed poll and keep the service running."""

    class FailingReader(FakeReader):
        def read_holding_registers(self, start_address: int, count: int) -> RegisterData:
            self.reads += 1
            raise RegisterReadError("modbus unavailable")

    reader = FailingReader()

    with caplog.at_level(logging.ERROR):
        run_service(
            reader=reader,
            profile=_profile(),
            keys=("battery_soc",),
            interval=0.5,
            sleep=lambda _seconds: None,
            iterations=2,
        )

    assert reader.reads == 2
    assert "poll failed" in caplog.text
    assert "modbus unavailable" in caplog.text


def test_configure_logging_uses_basic_config_without_handlers():
    """Install a root handler when logging has not been configured yet."""
    root = logging.getLogger()
    saved = list(root.handlers)
    for handler in saved:
        root.removeHandler(handler)
    try:
        configure_logging("WARNING")
        assert root.handlers
        assert root.level == logging.WARNING
    finally:
        for handler in list(root.handlers):
            root.removeHandler(handler)
        for handler in saved:
            root.addHandler(handler)


def test_main_runs_service_from_config(monkeypatch):
    """Open Modbus from --config and hand settings to run_service."""
    opened: dict = {}
    ran: dict = {}
    mqtt: dict = {}

    class FakeTransport:
        def __enter__(self):
            return FakeReader()

        def __exit__(self, *_args):
            return None

    class FakeMqtt:
        def publish(self, topic, payload, *, retain=False):
            return None

        def close(self):
            mqtt["closed"] = True

    def fake_tcp(*, host, port=502, device_id=1, client=None):
        opened.update(host=host, port=port, device_id=device_id)
        return FakeTransport()

    def fake_connect_mqtt_client(**kwargs):
        mqtt["connect"] = kwargs
        return FakeMqtt()

    def fake_run_service(**kwargs):
        ran.update(kwargs)

    monkeypatch.setattr("rainbow_energy_publisher.cli.ModbusReader.tcp", fake_tcp)
    monkeypatch.setattr(
        "rainbow_energy_publisher.cli.connect_mqtt_client",
        fake_connect_mqtt_client,
    )
    monkeypatch.setattr("rainbow_energy_publisher.cli.run_service", fake_run_service)

    example = Path(__file__).resolve().parents[1] / "config.yaml.example"
    assert main(["--config", str(example)]) == 0
    assert opened == {
        "host": "modbus-gateway.example",
        "port": 502,
        "device_id": 1,
    }
    assert mqtt["connect"] == {
        "host": "mqtt.example",
        "port": 1883,
        "username": None,
        "password": None,
    }
    assert mqtt["closed"] is True
    assert ran["keys"] == (
        "battery_soc",
        "battery_voltage",
        "battery_power",
        "pv_power",
        "load_power",
        "grid_power",
    )
    assert ran["interval"] == 5.0
    assert ran["log_level"] == "INFO"
    assert ran["all_keys"] is False
    assert ran["profile"].model == "SYNK-8K-SG05LP1"
    assert ran["publisher"] is not None
    assert ran["publisher"]._retain is True
    assert ran["publisher"].ha_discovery is False
    assert ran["publisher"]._device_id is None


def test_main_reports_config_errors(tmp_path, capsys):
    """Exit non-zero when the config file cannot be loaded."""
    path = tmp_path / "missing.yaml"
    assert main(["--config", str(path)]) == 2
    assert "config error" in capsys.readouterr().err


def test_main_reports_mqtt_connect_errors(monkeypatch, tmp_path, capsys):
    """Exit non-zero when the MQTT broker cannot be reached."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
interval: 1.0
profile: sunsynk_8k_sg05lp1
keys: [battery_soc]
modbus:
  tcp:
    host: modbus-gateway.example
mqtt:
  host: mqtt.example
  topic_prefix: rainbow/energy
""",
        encoding="utf-8",
    )

    class FakeTransport:
        def __enter__(self):
            return FakeReader()

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr(
        "rainbow_energy_publisher.cli.ModbusReader.tcp",
        lambda **_kwargs: FakeTransport(),
    )

    def raise_connection_refused(**_kwargs):
        raise ConnectionRefusedError("connection refused")

    monkeypatch.setattr(
        "rainbow_energy_publisher.cli.connect_mqtt_client",
        raise_connection_refused,
    )

    assert main(["--config", str(config_path)]) == 2
    assert "mqtt error" in capsys.readouterr().err


def test_main_reports_modbus_open_errors(monkeypatch, tmp_path, capsys):
    """Exit non-zero when the Modbus transport cannot be opened."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
interval: 1.0
profile: sunsynk_8k_sg05lp1
keys: [battery_soc]
modbus:
  tcp:
    host: modbus-gateway.example
mqtt:
  host: mqtt.example
  topic_prefix: rainbow/energy
""",
        encoding="utf-8",
    )
    mqtt: dict = {}

    class BoomTransport:
        def __enter__(self):
            raise OSError("modbus unreachable")

        def __exit__(self, *_args):
            return None

    class FakeMqtt:
        def publish(self, *args, **kwargs):
            return None

        def close(self):
            mqtt["closed"] = True

    monkeypatch.setattr(
        "rainbow_energy_publisher.cli.ModbusReader.tcp",
        lambda **_kwargs: BoomTransport(),
    )
    monkeypatch.setattr(
        "rainbow_energy_publisher.cli.connect_mqtt_client",
        lambda **_kwargs: FakeMqtt(),
    )

    assert main(["--config", str(config_path)]) == 2
    assert "modbus error" in capsys.readouterr().err
    assert mqtt["closed"] is True


def test_main_loads_profile_from_path(monkeypatch, tmp_path):
    """Load a filesystem profile when profile_path is set."""
    profile_file = tmp_path / "device.yaml"
    profile_file.write_text("unused", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
interval: 1.0
profile_path: {profile_file}
keys: [battery_soc]
modbus:
  tcp:
    host: modbus-gateway.example
mqtt:
  host: mqtt.example
  topic_prefix: rainbow/energy
""",
        encoding="utf-8",
    )
    loaded: dict = {}

    class FakeTransport:
        def __enter__(self):
            return FakeReader()

        def __exit__(self, *_args):
            return None

    def fake_load_profile(path):
        loaded["path"] = path
        return _profile()

    monkeypatch.setattr("rainbow_energy_publisher.cli.load_profile", fake_load_profile)
    monkeypatch.setattr(
        "rainbow_energy_publisher.cli.ModbusReader.tcp",
        lambda **_kwargs: FakeTransport(),
    )
    monkeypatch.setattr(
        "rainbow_energy_publisher.cli.connect_mqtt_client",
        lambda **_kwargs: type(
            "Mqtt",
            (),
            {"publish": lambda self, *args, **kwargs: None, "close": lambda self: None},
        )(),
    )
    monkeypatch.setattr("rainbow_energy_publisher.cli.run_service", lambda **_kwargs: None)

    assert main(["--config", str(config_path)]) == 0
    assert loaded["path"] == profile_file


def test_main_reports_profile_errors(monkeypatch, tmp_path, capsys):
    """Exit non-zero when the named profile cannot be loaded."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
interval: 1.0
profile: missing_device
keys: [battery_soc]
modbus:
  tcp:
    host: modbus-gateway.example
mqtt:
  host: mqtt.example
  topic_prefix: rainbow/energy
""",
        encoding="utf-8",
    )

    def raise_profile_error(_path):
        raise ProfileError("unknown profile")

    monkeypatch.setattr("rainbow_energy_publisher.cli.load_profile", raise_profile_error)

    assert main(["--config", str(config_path)]) == 2
    assert "profile error" in capsys.readouterr().err


def test_main_opens_usb_serial_reader(monkeypatch, tmp_path):
    """Open a serial reader when modbus.usb is configured."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
interval: 1.0
profile: sunsynk_8k_sg05lp1
keys: [battery_soc]
modbus:
  device_id: 2
  usb:
    port: /dev/ttyUSB0
mqtt:
  host: mqtt.example
  topic_prefix: rainbow/energy
""",
        encoding="utf-8",
    )
    opened: dict = {}

    class FakeTransport:
        def __enter__(self):
            return FakeReader()

        def __exit__(self, *_args):
            return None

    def fake_serial(*, port, device_id=1, client=None):
        opened.update(port=port, device_id=device_id)
        return FakeTransport()

    monkeypatch.setattr("rainbow_energy_publisher.cli.ModbusReader.serial", fake_serial)
    monkeypatch.setattr(
        "rainbow_energy_publisher.cli.connect_mqtt_client",
        lambda **_kwargs: type(
            "Mqtt",
            (),
            {"publish": lambda self, *args, **kwargs: None, "close": lambda self: None},
        )(),
    )
    monkeypatch.setattr("rainbow_energy_publisher.cli.run_service", lambda **_kwargs: None)

    assert main(["--config", str(config_path)]) == 0
    assert opened == {"port": "/dev/ttyUSB0", "device_id": 2}
