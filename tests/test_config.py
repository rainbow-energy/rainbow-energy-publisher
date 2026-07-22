"""Test loading service configuration from YAML."""

from pathlib import Path

import pytest

from rainbow_energy_mqtt.config import ConfigError, load_config

_EXAMPLE_CONFIG = Path(__file__).resolve().parents[1] / "config.yaml.example"


def _write_config(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def test_load_config_defaults_log_level_when_omitted():
    """Use INFO when log_level is left out of the example config."""
    assert load_config(_EXAMPLE_CONFIG).log_level == "INFO"


def test_load_config_rejects_missing_profile_choice(tmp_path: Path):
    """Require exactly one of profile or profile_path."""
    path = _write_config(
        tmp_path,
        """
interval: 5.0
keys: [battery_soc]
modbus:
  tcp:
    host: modbus-gateway.example
""",
    )

    with pytest.raises(ConfigError, match="profile or profile_path"):
        load_config(path)


def test_load_config_rejects_missing_modbus_transport(tmp_path: Path):
    """Require exactly one of modbus.tcp or modbus.usb."""
    path = _write_config(
        tmp_path,
        """
interval: 5.0
profile: sunsynk_8k_sg05lp1
keys: [battery_soc]
modbus:
  device_id: 1
""",
    )

    with pytest.raises(ConfigError, match="modbus.tcp or modbus.usb"):
        load_config(path)
