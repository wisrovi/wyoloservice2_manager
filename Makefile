# Makefile for Wyolo Manager Orchestrator

# Variables
ENV_FILE := control_host.env
DOCKER_COMPOSE := docker compose

.PHONY: help setup build up down logs clean shell test

help:
	@echo "🚀 Wyolo Manager Orchestrator - Management CLI"
	@echo ""
	@echo "Usage:"
	@echo "  make setup        - Create the environment file ($(ENV_FILE))"
	@echo "  make build        - Build the Docker image"
	@echo "  make up           - Start the manager container in background"
	@echo "  make down         - Stop and remove the container"
	@echo "  make logs         - View real-time container logs"
	@echo "  make shell        - Enter the running container shell"
	@echo "  make test         - Run unit tests with pytest"
	@echo "  make clean        - Remove python artifacts and temporary files"
	@echo ""

setup:
	@if [ ! -f $(ENV_FILE) ]; then \
		echo "Creating $(ENV_FILE)..."; \
		echo "# Wyolo Manager Configuration" > $(ENV_FILE); \
		echo "REDIS_URL=redis://192.168.1.137:23437/0" >> $(ENV_FILE); \
		echo "✅ $(ENV_FILE) created with default values. Please edit it if needed."; \
	else \
		echo "⚠️  $(ENV_FILE) already exists."; \
	fi

build:
	$(DOCKER_COMPOSE) build

start: $(ENV_FILE)
	$(DOCKER_COMPOSE) up -d

$(ENV_FILE):
	@$(MAKE) setup

stop:
	$(DOCKER_COMPOSE) down

logs:
	$(DOCKER_COMPOSE) logs -f

shell:
	$(DOCKER_COMPOSE) exec manager_study /bin/bash

test:
	pytest tests/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf app/optuna_study.db
