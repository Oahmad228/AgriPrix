# syntax=docker/dockerfile:1
# Single application image shared by api, dashboard, mlflow and job-runner.
# Technical debt tracked in docs/adr/008: split into per-service runtime targets in Sprint 4.
FROM python:3.11.18-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System dependencies: libgomp1 (LightGBM OpenMP runtime), curl (healthchecks),
# git (MLflow records the source commit of each run)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Non-root runtime user
RUN groupadd --gid 1000 agriprix && \
    useradd --uid 1000 --gid agriprix --shell /bin/bash --create-home agriprix && \
    mkdir -p /mlflow/artifacts /app/data/raw /app/data/processed /app/data/reports && \
    chown -R agriprix:agriprix /app /mlflow

# 1) Third-party dependencies, pinned exactly by requirements.lock.
#    This layer only changes when the lock file changes (fast rebuilds on code edits).
#    --no-deps guarantees nothing outside the lock is installed; `pip check` fails the
#    build if the lock is incomplete or inconsistent.
COPY requirements.lock ./
RUN pip install --prefer-binary --default-timeout=180 --retries=10 --no-deps \
        -r requirements.lock && \
    pip check

# 2) Project code, installed in editable mode without touching dependencies.
COPY --chown=agriprix:agriprix pyproject.toml README.md ./
COPY --chown=agriprix:agriprix src ./src
COPY --chown=agriprix:agriprix tests ./tests
RUN pip install --no-deps -e .

USER agriprix

EXPOSE 8000 8501 5000
