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

## Kubernetes (Helm)

A minimal chart lives in [`chart/`](chart/). It deploys one `Deployment`,
mounts `config.yaml` from a `ConfigMap`, and optionally creates a `Secret`
for `MQTT_USERNAME` / `MQTT_PASSWORD`.

Uncomment **exactly one** of `config.modbus.tcp` or `config.modbus.usb`
in your values (omit the other). TCP is usual for remote `mbusd`. USB mounts
the host device via `hostPath` (`CharDevice`) and defaults to a privileged
container; pin that pod with `nodeSelector`.

```bash
# my-values.yaml — set Modbus + MQTT for your site
helm upgrade --install publisher ./chart \
  --namespace energy --create-namespace \
  -f my-values.yaml
```

Example `my-values.yaml` (TCP):

```yaml
config:
  modbus:
    device_id: 1
    tcp:
      host: solarassistant.example
      port: 502
  mqtt:
    host: mqtt.example
    topic_prefix: rainbow/energy
mqtt:
  existingSecret: publisher-mqtt
```

USB instead of TCP:

```yaml
config:
  modbus:
    device_id: 1
    usb:
      port: /dev/ttyUSB0
nodeSelector:
  kubernetes.io/hostname: pi-with-rs485
```

Create MQTT credentials if not using chart-managed username/password:

```bash
kubectl create secret generic publisher-mqtt \
  --from-literal=MQTT_USERNAME=... \
  --from-literal=MQTT_PASSWORD=...
```

Lint the chart (requires [Helm](https://helm.sh)):

```bash
helm lint chart
helm template publisher chart -f my-values.yaml --debug
```
