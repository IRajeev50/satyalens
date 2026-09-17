.PHONY: dev test postgres eval

dev:
	uv run uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

test:
	uv run --extra dev pytest -q

postgres:
	docker compose up -d postgres

# Run the eval harness: gold set through the live pipeline, METRICS.md gates,
# JSON + Markdown reports under evals/reports/.
eval:
	uv run python -m evals.runner
