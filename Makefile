.PHONY: dev build up down test test-backend test-frontend lint clean

PROJECT_DIR := $(shell pwd)

## Development

dev-backend:
	cd backend && python -m uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8002

dev-frontend:
	cd frontend && npm run dev

## Docker

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

## Testing

test: test-backend test-frontend

test-backend:
	cd backend && python -m pytest tests/ -v

test-frontend:
	cd frontend && npm run build

## Linting

lint-backend:
	cd backend && ruff check src/

lint-frontend:
	cd frontend && npm run lint

## Cleanup

clean:
	docker compose down -v
	rm -rf frontend/.next frontend/node_modules
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
