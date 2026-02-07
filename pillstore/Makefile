up:
	docker compose up db -d
	@echo "🚀 DB ready на localhost:5434"
	@echo "🚀 API ready на localhost:8000" 
	docker compose up api -d
	@docker compose logs -f api --tail=10

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