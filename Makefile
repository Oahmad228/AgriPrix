# =============================================================================
# AgriPrix Observatory — Makefile
# All development, testing, linting, ETL, and ML training commands execute
# exclusively inside Docker containers (Zero host dependency).
# =============================================================================

.PHONY: help build up down ps logs lint format test etl train clean

COMPOSE := docker compose
RUN_JOB := $(COMPOSE) --profile jobs run --rm job-runner

help: ## Show available Makefile targets
	@echo "AgriPrix Observatory — Available commands:"
	@echo "  make build   : Build the shared application image (agriprix-app:latest)"
	@echo "  make up      : Build and start all MVP services in background (db, mlflow, api, dashboard)"
	@echo "  make down    : Stop and remove running containers"
	@echo "  make ps      : Show container status and healthchecks"
	@echo "  make logs    : Tail logs from all services"
	@echo "  make lint    : Run Ruff linter and format check inside Docker"
	@echo "  make format  : Auto-format code with Ruff inside Docker"
	@echo "  make test    : Run pytest suite with coverage (>= 70%) inside Docker"
	@echo "  make etl     : Run the ETL ingestion and validation pipeline inside Docker"
	@echo "  make train   : Run the ML global training and anomaly detection pipeline inside Docker"
	@echo "  make clean   : Stop containers and remove volumes (resets database)"

build: ## Build the shared application image used by every Python service
	$(COMPOSE) build api

up: ## Start all MVP services (PostgreSQL, MLflow, FastAPI, Streamlit) and wait for healthchecks
	$(COMPOSE) up -d --build --wait

down: ## Stop all running services
	$(COMPOSE) --profile jobs down

ps: ## List running containers and health status
	$(COMPOSE) ps

logs: ## Follow container logs
	$(COMPOSE) logs -f --tail=100

lint: ## Run Ruff code linter and formatter check inside job-runner container
	$(RUN_JOB) sh -c "ruff check src tests && ruff format --check src tests"

format: ## Format Python code using Ruff inside job-runner container
	$(RUN_JOB) sh -c "ruff check --fix src tests && ruff format src tests"

test: ## Run automated test suite with coverage check (>= 70%) inside job-runner container
	$(RUN_JOB) pytest

etl: ## Execute the ETL pipeline (HDX/FAOSTAT ingestion, validation, warehouse upsert)
	$(RUN_JOB) python -m src.etl.cli

train: ## Execute the ML forecasting and anomaly detection pipeline
	$(RUN_JOB) python -m src.ml.cli

clean: ## Stop containers and remove named volumes
	$(COMPOSE) --profile jobs down -v
