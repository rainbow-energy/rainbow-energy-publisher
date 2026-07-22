"""Test the long-running service loop and CLI entry point."""

import logging
from pathlib import Path

from rainbow_energy_client.profiles import DeviceProfile, RegisterDefinition
from rainbow_energy_client.reader import RegisterData, RegisterReadError

from rainbow_energy_mqtt.cli import main
from rainbow_energy_mqtt.service import run_service


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

    seen: list[tuple] = []

    with caplog.at_level(logging.ERROR):
        run_service(
            reader=FailingReader(),
            profile=_profile(),
            keys=("battery_soc",),
            interval=0.5,
            sleep=lambda _seconds: None,
            iterations=2,
            on_measurements=seen.append,
        )

    assert seen == []
    assert "poll failed" in caplog.text
    assert "modbus unavailable" in caplog.text


def test_main_runs_service_from_config(monkeypatch):
    """Open Modbus from --config and hand settings to run_service."""
    opened: dict = {}
    ran: dict = {}

    class FakeTransport:
        def __enter__(self):
            return FakeReader()

        def __exit__(self, *_args):
            return None

    def fake_tcp(*, host, port=502, device_id=1, client=None):
        opened.update(host=host, port=port, device_id=device_id)
        return FakeTransport()

    def fake_run_service(**kwargs):
        ran.update(kwargs)

    monkeypatch.setattr("rainbow_energy_mqtt.cli.ModbusReader.tcp", fake_tcp)
    monkeypatch.setattr("rainbow_energy_mqtt.cli.run_service", fake_run_service)

    example = Path(__file__).resolve().parents[1] / "config.yaml.example"
    assert main(["--config", str(example)]) == 0
    assert opened == {
        "host": "modbus-gateway.example",
        "port": 502,
        "device_id": 1,
    }
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
    assert ran["profile"].model == "SYNK-8K-SG05LP1"
