# Rainbow Energy Publisher

Long-running service that polls an inverter with
[`rainbow-energy-modbus-client`](https://github.com/rainbow-energy/rainbow-energy-modbus-client)
and publishes measurements to MQTT (for Home Assistant and other subscribers).

## Usage

```bash
cp config.yaml.example config.yaml
# edit config.yaml
make run
```

Stop with Ctrl-C.

`config.yaml` is gitignored. Optional `log_level` defaults to `INFO`.
`keys` is a list of measurement names, or `keys: "*"` (quoted) to poll
every readable register from the profile. MQTT broker settings live under
`mqtt:` (`host`, optional `port` defaulting to `1883`, `topic_prefix`, and
optional `username` / `password`). Prefer `MQTT_USERNAME` /
`MQTT_PASSWORD` env vars over putting secrets in YAML.
Optional publish options: `retain` (default `true`), `device_id`,
`ha_discovery` (default `false`), and `discovery_prefix` (default
`homeassistant`). Each poll publishes `topic_prefix/<key>` with the
measurement value and still logs readings at INFO. When `ha_discovery` is
true, retained Home Assistant MQTT sensor discovery configs are published
once at startup (requires `device_id`). The MQTT client reconnects
automatically if the broker connection drops while the service is running.

All Make targets run through Docker:

```bash
make build   # production image
make run     # build + run with ./config.yaml mounted
make shell   # production shell with config mounted
make sync    # development image (locked deps)
make lint    # Ruff in the development image
make test    # pytest in the development image
make check   # lint + test
```

## Development

```bash
make check
```

Run `make help` for all targets.

GitHub Actions (`.github/workflows/ci.yml`) runs `make check`, builds the
production image, and on pushes to `main` publishes it to GHCR as
`ghcr.io/<owner>/rainbow-energy-publisher` (`latest` and the short commit SHA).
Pull requests build the image but do not push.
