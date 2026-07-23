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

shell:
	docker run --rm -it $(IMAGE) /bin/sh

run:
	@test -f "$(CONFIG)" || (echo "Missing $(CONFIG); copy config.yaml.example and edit it" >&2; exit 2)
	docker run --rm \
		-v "$(PWD)/$(CONFIG):/app/config.yaml:ro" \
		rainbow-energy-mqtt

