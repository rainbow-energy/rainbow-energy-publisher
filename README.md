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
Measurements are logged until MQTT lands.

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
