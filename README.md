# Rainbow Energy MQTT

Long-running service that polls an inverter with
[`rainbow-energy-client`](https://github.com/rainbow-solar/rainbow-energy-client)
and publishes measurements to MQTT (for Home Assistant and other subscribers).

## Install

```bash
make sync
```

## Usage

```bash
cp config.yaml.example config.yaml
# edit config.yaml
make run
```

Stop with Ctrl-C.

`config.yaml` is gitignored. Optional `log_level` defaults to `INFO`.
MQTT broker settings live under `mqtt:` (`host`, optional `port` defaulting
to `1883`, `topic_prefix`, and optional `username` / `password`). Prefer
`MQTT_USERNAME` / `MQTT_PASSWORD` env vars over putting secrets in YAML.
Optional publish options: `retain` (default `true`), `device_id`,
`ha_discovery` (default `false`), and `discovery_prefix` (default
`homeassistant`). Each poll publishes `topic_prefix/<key>` with the
measurement value and still logs readings at INFO. When `ha_discovery` is
true, retained Home Assistant MQTT sensor discovery configs are published
once at startup (requires `device_id`).

Docker:

```bash
make build
docker run --rm -v "$PWD/config.yaml:/config/config.yaml:ro" rainbow-energy-mqtt
```

## Development

```bash
make check
```

Run `make help` for all targets.
