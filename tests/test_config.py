"""Test loading service configuration from YAML."""

from pathlib import Path

import pytest

from rainbow_energy_mqtt.config import ConfigError, load_config

_EXAMPLE_CONFIG = Path(__file__).resolve().parents[1] / "config.yaml.example"


def _write_config(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def test_load_config_reads_mqtt_broker_settings():
    """Load MQTT host and topic prefix; default the broker port to 1883."""
    config = load_config(_EXAMPLE_CONFIG)

    assert config.mqtt_host == "mqtt.example"
    assert config.mqtt_port == 1883
    assert config.mqtt_topic_prefix == "rainbow/energy"
    assert config.mqtt_username is None
    assert config.mqtt_password is None


def test_load_config_defaults_mqtt_publish_options_when_omitted():
    """Default retain, discovery, and related MQTT options when left out."""
    config = load_config(_EXAMPLE_CONFIG)

    assert config.mqtt_retain is True
    assert config.mqtt_device_id is None
    assert config.mqtt_ha_discovery is False
    assert config.mqtt_discovery_prefix == "homeassistant"


def test_load_config_reads_mqtt_publish_options_from_yaml(tmp_path: Path):
    """Load retain, device_id, and Home Assistant discovery options from YAML."""
    path = _write_config(
        tmp_path,
        """
interval: 5.0
profile: sunsynk_8k_sg05lp1
keys: [battery_soc]
modbus:
  tcp:
    host: modbus-gateway.example
mqtt:
  host: mqtt.example
  topic_prefix: rainbow/energy
  retain: false
  device_id: inverter-1
  ha_discovery: true
  discovery_prefix: ha
""",
    )

    config = load_config(path)

    assert config.mqtt_retain is False
    assert config.mqtt_device_id == "inverter-1"
    assert config.mqtt_ha_discovery is True
    assert config.mqtt_discovery_prefix == "ha"


def test_load_config_defaults_log_level_when_omitted():
    """Use INFO when log_level is left out of the example config."""
    assert load_config(_EXAMPLE_CONFIG).log_level == "INFO"


def test_load_config_accepts_keys_star_for_all_readable_registers(tmp_path: Path):
    """Treat keys: "*" as poll-all; leave keys empty until profile expansion."""
    path = _write_config(
        tmp_path,
        """
interval: 5.0
profile: sunsynk_8k_sg05lp1
keys: "*"
modbus:
  tcp:
    host: modbus-gateway.example
mqtt:
  host: mqtt.example
  topic_prefix: rainbow/energy
""",
    )

    config = load_config(path)

    assert config.all_keys is True
    assert config.keys == ()


def test_load_config_rejects_invalid_keys_shape(tmp_path: Path):
    """Reject keys that are neither a list nor the "*" sentinel."""
    path = _write_config(
        tmp_path,
        """
interval: 5.0
profile: sunsynk_8k_sg05lp1
keys: all
modbus:
  tcp:
    host: modbus-gateway.example
mqtt:
  host: mqtt.example
  topic_prefix: rainbow/energy
""",
    )

    with pytest.raises(ConfigError, match=r'keys must be a list of names or "\*"'):
        load_config(path)


def test_load_config_prefers_mqtt_auth_env_overrides(tmp_path: Path, monkeypatch):
    """Prefer MQTT_USERNAME and MQTT_PASSWORD over YAML auth fields."""
    path = _write_config(
        tmp_path,
        """
interval: 5.0
profile: sunsynk_8k_sg05lp1
keys: [battery_soc]
modbus:
  tcp:
    host: modbus-gateway.example
mqtt:
  host: mqtt.example
  topic_prefix: rainbow/energy
  username: from-yaml
  password: yaml-secret
""",
    )
    monkeypatch.setenv("MQTT_USERNAME", "from-env")
    monkeypatch.setenv("MQTT_PASSWORD", "env-secret")

    config = load_config(path)

    assert config.mqtt_username == "from-env"
    assert config.mqtt_password == "env-secret"


def test_load_config_reads_mqtt_auth_from_yaml(tmp_path: Path, monkeypatch):
    """Use YAML username and password when env overrides are unset."""
    monkeypatch.delenv("MQTT_USERNAME", raising=False)
    monkeypatch.delenv("MQTT_PASSWORD", raising=False)
    path = _write_config(
        tmp_path,
        """
interval: 5.0
profile: sunsynk_8k_sg05lp1
keys: [battery_soc]
modbus:
  tcp:
    host: modbus-gateway.example
mqtt:
  host: mqtt.example
  topic_prefix: rainbow/energy
  username: from-yaml
  password: yaml-secret
""",
    )

    config = load_config(path)

    assert config.mqtt_username == "from-yaml"
    assert config.mqtt_password == "yaml-secret"


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
mqtt:
  host: mqtt.example
  topic_prefix: rainbow/energy
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
mqtt:
  host: mqtt.example
  topic_prefix: rainbow/energy
""",
    )

    with pytest.raises(ConfigError, match="modbus.tcp or modbus.usb"):
        load_config(path)
