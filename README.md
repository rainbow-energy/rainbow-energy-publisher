# Rainbow Energy MQTT

Long-running service that polls an inverter with
[`rainbow-energy-client`](https://github.com/rainbow-solar/rainbow-energy-client)
and publishes measurements to MQTT (for Home Assistant and other subscribers).

## Install

From this directory (sibling checkout of `rainbow-energy-client` at
`../rainbow-energy-client`):

```bash
uv sync
```

## Usage

```bash
cp config.yaml.example config.yaml
# edit config.yaml
uv run rainbow-energy-mqtt --config config.yaml
```

Stop with Ctrl-C.

`config.yaml` is gitignored. Optional `log_level` defaults to `INFO`.
Measurements are logged until MQTT lands.

## Development

```bash
uv run pytest
```
