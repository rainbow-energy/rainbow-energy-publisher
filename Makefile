.PHONY: help sync lint test check build run shell

IMAGE ?= rainbow-energy-mqtt
DEV_IMAGE ?= rainbow-energy-mqtt-dev
CONFIG ?= config.yaml

help:
	@printf '%s\n' \
		"make sync   Build the development Docker image (locked deps)" \
		"make lint   Run Ruff in the development image" \
		"make test   Run tests in the development image" \
		"make check  Run lint and tests" \
		"make build  Build the production Docker image" \
		"make run    Run the service with $(CONFIG)" \
		"make shell  Open a shell in the production image with $(CONFIG)"

sync: build-dev

build-dev:
	docker build --target development -t $(DEV_IMAGE) .

lint: build-dev
	docker run --rm $(DEV_IMAGE) uv run --locked ruff check .

test: build-dev
	docker run --rm $(DEV_IMAGE)

check: lint test

build:
	docker build --target production -t $(IMAGE) .

shell: build
	@test -f "$(CONFIG)" || (echo "Missing $(CONFIG); copy config.yaml.example and edit it" >&2; exit 2)
	docker run --rm -it \
		-v "$(PWD)/$(CONFIG):/app/config.yaml:ro" \
		$(IMAGE) /bin/sh

run: build
	@test -f "$(CONFIG)" || (echo "Missing $(CONFIG); copy config.yaml.example and edit it" >&2; exit 2)
	docker run --rm \
		-v "$(PWD)/$(CONFIG):/app/config.yaml:ro" \
		$(IMAGE)
