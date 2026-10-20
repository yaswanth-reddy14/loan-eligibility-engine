.PHONY: up down test benchmark demo
up:
	docker compose build api
	docker compose up -d --no-build
down:
	docker compose down
test:
	python scripts/run_checks.py
benchmark:
	python scripts/benchmark.py
demo:
	python scripts/demo.py
