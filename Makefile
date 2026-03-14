.PHONY: help build up down logs shell db-shell migrate test lint clean

# Default target
help:
	@echo "Bitenex API - Available Commands:"
	@echo ""
	@echo "Development:"
	@echo "  make build       - Build Docker images"
	@echo "  make up          - Start all services"
	@echo "  make down        - Stop all services"
	@echo "  make restart     - Restart all services"
	@echo "  make logs        - View logs (all services)"
	@echo "  make logs-api    - View API logs only"
	@echo ""
	@echo "Database:"
	@echo "  make db-shell    - Open PostgreSQL shell"
	@echo "  make migrate     - Run Alembic migrations"
	@echo "  make migrate-new - Create new migration"
	@echo ""
	@echo "Development Tools:"
	@echo "  make shell       - Open API container shell"
	@echo "  make test        - Run tests"
	@echo "  make lint        - Run linting"
	@echo "  make format      - Format code"
	@echo "  make dev-tools   - Start with dev tools (pgadmin)"
	@echo ""
	@echo "Production:"
	@echo "  make prod-up     - Start production services"
	@echo "  make prod-down   - Stop production services"
	@echo ""
	@echo "Cleanup:"
	@echo "  make clean       - Remove containers and volumes"
	@echo "  make prune       - Remove all unused Docker resources"

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

logs-api:
	docker compose logs -f api

shell:
	docker compose exec api /bin/bash

dev-tools:
	docker compose --profile dev-tools up -d

db-shell:
	docker compose exec db psql -U postgres -d bitenex

migrate:
	docker compose exec api alembic upgrade head

migrate-new:
	@read -p "Migration message: " msg; \
	docker compose exec api alembic revision --autogenerate -m "$$msg"

migrate-down:
	docker compose exec api alembic downgrade -1

test:
	docker compose exec api pytest -v

test-cov:
	docker compose exec api pytest --cov=app --cov-report=html

lint:
	docker compose exec api ruff check app

format:
	docker compose exec api ruff check --fix app

prod-up:
	docker compose -f docker-compose.prod.yml up -d

prod-down:
	docker compose -f docker-compose.prod.yml down

prod-logs:
	docker compose -f docker-compose.prod.yml logs -f

clean:
	docker compose down -v --remove-orphans

prune:
	docker system prune -af
	docker volume prune -f
