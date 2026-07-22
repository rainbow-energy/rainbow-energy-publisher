"""Command-line entry point for the MQTT publisher service."""

from __future__ import annotations

import sys

from rainbow_energy_mqtt.service import run_service


def main(argv: list[str] | None = None) -> int:
    """Start the service and run until interrupted."""
    _ = argv if argv is not None else sys.argv[1:]
    run_service()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
