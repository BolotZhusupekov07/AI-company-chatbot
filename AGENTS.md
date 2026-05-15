# Repository Guidelines

## Project Shape
This project follows the `ats-service` style split, kept intentionally minimal:

- `domain/` — pure business concepts and exceptions.
- `application/use_cases/` — orchestration code.
- `infrastructure/` — external adapters when you add them.
- `entrypoints/http/` — FastAPI app, routers, and HTTP wiring.
- `tests/integration/` — executable behavior checks.

AI, RAG, embeddings, Qdrant, and ingestion are intentionally not implemented in this scaffold.

## Commands
- `uv sync` — install dependencies.
- `make run` — run the HTTP API.
- `make test` — run tests.
- `make lint` — format and lint.
- `make typecheck` — run type checks.
- `make check` — lint, typecheck, and test.

## Coding Style
Python 3.13+, 120-character line length, double quotes. Keep `__init__.py` files as package markers only: docstring, no logic, no re-exports.

## Git
Stage new files after creating them. Do not commit unless explicitly asked.

