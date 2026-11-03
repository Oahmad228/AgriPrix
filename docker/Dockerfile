# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install minimal system dependencies required by LightGBM (libgomp1) and curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for security best practices
RUN groupadd --gid 1000 agriprix && \
    useradd --uid 1000 --gid agriprix --shell /bin/bash --create-home agriprix && \
    mkdir -p /mlflow/artifacts /app/data/raw /app/data/processed /app/data/reports && \
    chown -R agriprix:agriprix /app /mlflow

# Copy dependency specification first to maximize Docker layer caching
COPY --chown=agriprix:agriprix pyproject.toml README.md ./
COPY --chown=agriprix:agriprix src ./src
COPY --chown=agriprix:agriprix tests ./tests

# Install application and dev/test tools inside the container
RUN pip install --no-cache-dir -e ".[dev]"

USER agriprix

EXPOSE 8000 8501 5000
