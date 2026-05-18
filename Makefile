# Makefile for Wyolo Manager Orchestrator

# Variables
ENV_FILE := control_host.env
DOCKER_COMPOSE := docker compose

.PHONY: help setup build start stop up down logs clean shell test run-test

help:
	@echo "🚀 Wyolo Manager Orchestrator - Management CLI"
	@echo ""
	@echo "Usage:"
	@echo "  make setup        - Create the environment file ($(ENV_FILE))"
	@echo "  make build        - Build the Docker images"
	@echo "  make up           - Start the containers in background"
	@echo "  make down         - Stop and remove the containers"
	@echo "  make logs         - View real-time container logs"
	@echo "  make shell        - Enter the running manager container shell"
	@echo "  make test         - Run unit tests with pytest"
	@echo "  make run-test     - Run the manual integration test container"
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


create_network:
	docker network create control_network


build:
	$(DOCKER_COMPOSE) build

start: $(ENV_FILE)
	$(DOCKER_COMPOSE) up -d --build

stop:
	$(DOCKER_COMPOSE) down

logs:
	$(DOCKER_COMPOSE) logs -f

shell:
	$(DOCKER_COMPOSE) exec manager_study /bin/bash

test:
	pytest tests/

run-test:
	$(DOCKER_COMPOSE) --profile debug run --rm tester

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf src/optuna_study.db
