# syntax=docker/dockerfile:1

# Build:
#   docker build -t rainbow-energy-mqtt .
#
# Run (mount a config file):
#   docker run --rm -v "$PWD/config.yaml:/config/config.yaml:ro" \
#     rainbow-energy-mqtt

ARG PYTHON_VERSION=3.12
ARG UV_VERSION=0.11.29

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

FROM python:${PYTHON_VERSION}-alpine AS build

COPY --from=uv /uv /uvx /bin/

RUN apk add --no-cache git

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_PREFERENCE=only-system \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project

COPY . .
RUN uv sync --locked --no-dev --no-editable

FROM python:${PYTHON_VERSION}-alpine AS production

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN adduser -D -u 10001 energy

COPY --from=build /opt/venv /opt/venv

USER energy

CMD ["rainbow-energy-mqtt", "--config", "/app/config.yaml"]
