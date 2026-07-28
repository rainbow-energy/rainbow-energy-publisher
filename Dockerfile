# syntax=docker/dockerfile:1

# Build production:
#   docker build -t rainbow-energy-publisher .
#
# Build development (lint/tests):
#   docker build --target development -t rainbow-energy-publisher-dev .
#
# Run (mount a config file):
#   docker run --rm -v "$PWD/config.yaml:/app/config.yaml:ro" \
#     rainbow-energy-publisher
#
# Profile maps are cloned from rainbow-energy-modbus-profiles into /profiles.
# Override the git ref with --build-arg PROFILES_REF=<sha|tag|branch>.

ARG PYTHON_VERSION=3.12
ARG UV_VERSION=0.11.29
ARG PROFILES_REPO=https://github.com/rainbow-energy/rainbow-energy-modbus-profiles.git
ARG PROFILES_REF=main

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

FROM alpine:3.21 AS profiles
ARG PROFILES_REPO
ARG PROFILES_REF
RUN apk add --no-cache git \
    && git clone --depth 1 --branch "${PROFILES_REF}" "${PROFILES_REPO}" /tmp/repo \
    && mkdir -p /profiles \
    && cp /tmp/repo/profiles/*.yaml /profiles/ \
    && rm -rf /tmp/repo

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

FROM build AS development

RUN uv sync --locked --no-editable

COPY --from=profiles /profiles /profiles

CMD ["uv", "run", "--locked", "pytest"]

FROM python:${PYTHON_VERSION}-alpine AS production

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN adduser -D -u 10001 energy

COPY --from=build /opt/venv /opt/venv
COPY --from=profiles /profiles /profiles

USER energy

ENTRYPOINT ["rainbow-energy-publisher"]
CMD ["--config", "/app/config.yaml"]
