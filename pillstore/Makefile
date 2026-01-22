up: ## Запуск psql и fastapi
	docker compose up db -d
	@echo "🚀 DB ready на 5434. Запускай uvicorn:"
	@docker compose logs -f db --tail=5 &
	uvicorn app.main:app --port 8001 --reload

logs:
	docker compose logs -f db

lint:
	docker compose build linters  # первый раз
	docker compose run --rm linters ruff check /app --output-format full || exit 1
	docker compose run --rm --profile donotstart editorconfig-checker /check

lint-flake8:
	docker compose run --rm linters flake8 /app

lint-fix:
	docker compose run --rm linters ruff check /app --fix
	