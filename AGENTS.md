# Rainbow Energy MQTT agent guidance

## Project context

- Rainbow Energy MQTT is a long-running service that polls an inverter with
  [`rainbow-energy-client`](https://github.com/rainbow-solar/rainbow-energy-client)
  and will publish measurements to MQTT (for Home Assistant and other
  subscribers).
- Until MQTT lands, successful polls are logged at INFO; do not invent a
  temporary publishing path.
- Depend on `rainbow-energy-client` for Modbus transport, profiles, and
  decoding; do not reimplement Modbus framing or register decode here.
- Python dependencies and locking are managed with `uv`. The client package
  is pulled from git (see `[tool.uv.sources]` in `pyproject.toml`).
- Lint and tests run locally through the `Makefile`. `make build` produces
  the Alpine runtime image for the service.

## Development process

- Follow strict TDD, one test per cycle:
  1. Add one test for one behaviour.
  2. Run it and confirm it fails for the expected reason.
  3. Write only enough production code to pass.
  4. Refactor while keeping all tests green.
- Work through one test at a time and ask for user confirmation of next step.
- Use injected fake readers in unit tests; tests must not require Modbus
  hardware, a live inverter, or a real MQTT broker.
- Aim for 100% code coverage; cover new code and close gaps shown by
  `make test` (`--cov-report=term-missing`).
- Prefer clear application errors while preserving underlying exceptions as
  causes.
- Add concise docstrings to modules and public classes, functions, and
  methods.
- Do not add speculative abstractions or unrelated features.
- Keep config validation minimal: enforce only the XOR rules already in
  `load_config` (profile vs `profile_path`; `modbus.tcp` vs `modbus.usb`)
  unless the user asks for more.

## Documentation

- Keep docs in sync with behaviour changes in the same change set when
  practical.
- Update [README.md](README.md) when install, run, Docker, or Make workflow
  changes.
- Update [config.yaml.example](config.yaml.example) when the config shape
  changes (new keys, defaults, or transport options).
- Do not leave docs describing removed or outdated behaviour.
- Do not commit operator `config.yaml` (it is gitignored).

## Commit messages

- Summarize the change in a subject of about 50 characters or fewer.
- Separate the subject from an optional body with a blank line.
- Wrap body text at about 72 characters.
- Explain the problem and why the change is needed rather than how the code
  works.
- Document important side effects or unintuitive consequences.
- Put issue references at the end, for example `Resolves: #123`.

## Commands

- `make sync` — synchronize locked dependencies.
- `make lint` — run Ruff.
- `make test` — run the test suite.
- `make check` — run lint and tests.
- `make build` — build the service Docker image.
- `make run` — run the service locally with `config.yaml`.
- `make help` — list available targets.
