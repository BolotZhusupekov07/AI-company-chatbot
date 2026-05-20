.PHONY: sync
sync:
	uv sync

.PHONY: lint
lint:
	uv run ruff format
	uv run ruff check . --fix

.PHONY: typecheck
typecheck:
	uv run ty check

.PHONY: test
test:
	uv run pytest

.PHONY: check
check: lint typecheck test

.PHONY: run
run:
	uv run python -m app.main
