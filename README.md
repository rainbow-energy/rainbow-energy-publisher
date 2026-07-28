# Rainbow Energy Publisher

Long-running service that polls an inverter with
[`rainbow-energy-modbus-client`](https://github.com/rainbow-energy/rainbow-energy-modbus-client)
and publishes measurements to MQTT (for Home Assistant and other subscribers).

Device register maps ship in the image from
[`rainbow-energy-modbus-profiles`](https://github.com/rainbow-energy/rainbow-energy-modbus-profiles)
under `/profiles`. Config `profile: <name>` loads `/profiles/<name>.yaml`.
Use `profile_path` to mount a custom map instead.

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

GitHub Actions (`.github/workflows/ci.yml`) has three jobs:

1. **test** — `make check` and `helm lint chart`
2. **build** — production image (push to GHCR on `main` only)
3. **publish-helm-chart** — package and push the chart to GHCR (`main` only)

Published artifacts (same commit → shared versions):

- image tags: `latest`, short SHA (e.g. `a1b2c3d`), and CalVer SemVer
  (e.g. `2026.7.28-r142.ga1b2c3d`)
- chart: `oci://ghcr.io/<owner>/rainbow-energy-publisher` — `version` is
  CalVer with `r<run>.g<sha>` prerelease (same string as the CalVer image
  tag); `appVersion` is the short SHA (same as the SHA image tag). The
  chart deploys that SHA image by default (`image.tag` empty →
  `Chart.AppVersion`). The run number makes same-day releases sortable
  for dependency bots (e.g. Renovate) while staying Helm SemVer-valid.

Pull requests run **test** and **build** (no push) and skip chart publish.

Install a published chart (pick a version from GHCR / the workflow log):

```bash
helm upgrade --install publisher \
  oci://ghcr.io/rainbow-energy/rainbow-energy-publisher \
  --version 2026.7.28-r142.ga1b2c3d \
  -f my-values.yaml
```

## Kubernetes (Helm)

A minimal chart lives in [`chart/`](chart/). It deploys one `Deployment`,
mounts `config.yaml` from a `ConfigMap`, and optionally creates a `Secret`
for `MQTT_USERNAME` / `MQTT_PASSWORD`. With `reloader.enabled` (default
`true`), the Deployment is annotated for [Stakater Reloader](https://github.com/stakater/Reloader)
so ConfigMap/Secret edits trigger a rolling restart. Image updates still
need a Helm upgrade that changes `image.tag` / chart `appVersion`.

Uncomment **exactly one** of `config.modbus.tcp` or `config.modbus.usb`
in your values (omit the other). TCP is usual for remote `mbusd`. USB mounts
the host device via `hostPath` (`CharDevice`) and defaults to a privileged
container; pin that pod with `nodeSelector`.

```bash
# my-values.yaml — set Modbus + MQTT for your site
helm upgrade --install publisher \
  oci://ghcr.io/rainbow-energy/rainbow-energy-publisher \
  --version 2026.7.28-r142.ga1b2c3d \
  --namespace energy --create-namespace \
  -f my-values.yaml
```

Or install from the local chart tree:

```bash
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
