.PHONY: help sync test lint check build run

IMAGE ?= rainbow-energy-mqtt
CONFIG ?= config.yaml

help:
	@printf '%s\n' \
		"make sync   Install locked dependencies" \
		"make lint   Run Ruff checks" \
		"make test   Run the test suite" \
		"make check  Run lint and tests" \
		"make build  Build the service Docker image" \
		"make run    Run the service with $(CONFIG) (local)"

sync:
	uv sync

lint:
	uv run --locked ruff check .

test:
	uv run --locked pytest

check: lint test

build:
	docker build -t $(IMAGE) .

run:
	@test -f "$(CONFIG)" || (echo "Missing $(CONFIG); copy config.yaml.example and edit it" >&2; exit 2)
	uv run --locked rainbow-energy-mqtt --config "$(CONFIG)"
