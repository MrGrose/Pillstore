.PHONY: up build logs logs-db stop down rest migrate shell install migrate-local run lint format test

up:
	docker compose up db -d
	@echo "🚀 DB ready на localhost:5434"
	docker compose up api -d
	@echo "🚀 API ready на localhost:8000"
	@docker compose logs -f api --tail=10

build:
	docker compose up -d --build

logs:
	docker compose logs -f api

logs-db:
	docker compose logs -f db

stop:
	docker compose stop

down:
	docker compose down -v

rest:
	docker compose restart api

migrate:
	docker compose exec api poetry run alembic upgrade head

shell:
	docker compose exec api bash

install:
	poetry install

migrate-local:
	poetry run alembic upgrade head

run:
	poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

lint:
	poetry run flake8 app

format:
	poetry run black app

test:
	poetry run pytest