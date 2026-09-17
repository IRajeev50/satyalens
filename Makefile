.PHONY: dev test postgres

dev:
	uv run uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

test:
	uv run --extra dev pytest -q

postgres:
	docker compose up -d postgres
