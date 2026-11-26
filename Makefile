.PHONY: install test lint run

install:
	pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check .

run:
	uvicorn ledgerline.app:create_app --factory --reload --port 8080
