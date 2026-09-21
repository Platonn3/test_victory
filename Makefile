.PHONY: install build up down restart logs test lint typecheck format check

install:
	uv sync --all-groups

build:
	docker compose build

up:
	docker compose up --build -d

down:
	docker compose down

restart: down up

logs:
	docker compose logs -f app

test:
	uv run pytest

lint:
	uv run ruff check .

typecheck:
	uv run mypy app

format:
	uv run ruff format .

check: lint typecheck test
