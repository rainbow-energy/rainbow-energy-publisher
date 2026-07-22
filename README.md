# Rainbow Energy MQTT

Long-running service that polls an inverter with
[`rainbow-energy-client`](https://github.com/rainbow-solar/rainbow-energy-client)
and publishes measurements to MQTT. Topics work for any subscriber; Home
Assistant MQTT discovery is enabled by default.

## Install (development)

From this directory, with the sibling client checkout at
`../rainbow-energy-client`:

```bash
uv sync
cp config.example.yaml config.yaml
# edit config.yaml
uv run rainbow-energy-mqtt --config config.yaml
```

On other hosts, point `rainbow-energy-client` at git in `pyproject.toml`
`[tool.uv.sources]` (or install both packages from git).

## Configuration

Pass a YAML file with `--config` or `RAINBOW_ENERGY_MQTT_CONFIG`.

Device map: set exactly one of:

- `profile` — packaged stem from rainbow-energy-client (e.g. `sunsynk_8k_sg05lp1`)
- `profile_path` — path to a custom profile YAML

See [config.example.yaml](config.example.yaml). Override MQTT password with
`RAINBOW_ENERGY_MQTT_PASSWORD` if needed.

## MQTT topics

State (any consumer):

```text
{topic_prefix}/{device_id}/{key}/state
```

Availability:

```text
{topic_prefix}/{device_id}/status
```

Home Assistant discovery (when `ha_discovery: true`):

```text
{discovery_prefix}/sensor/{device_id}_{key}/config
```

## Run as a service

Native / systemd:

```bash
rainbow-energy-mqtt --config /etc/rainbow-energy-mqtt/config.yaml
```

Container-friendly (Dockerfile later):

```bash
CMD ["rainbow-energy-mqtt", "--config", "/config/config.yaml"]
```

Stop with Ctrl-C / SIGTERM.
