# Repository Guidelines

## Project Shape
This project follows a simple API service structure, matching the `ai-hr-chatbot` style and kept intentionally minimal:

- `app/main.py` — FastAPI app factory and local run entrypoint.
- `app/api/` — HTTP routers and request/response schemas.
- `app/core/` — settings and core application wiring.
- `app/services/` — orchestration code when you add it.
- `app/infrastructure/` — external adapters when you add them.
- `app/knowledge/` — internal knowledge schemas.
- `app/cli/` — CLI utilities.
- `tests/api/` and `tests/unit/` — executable behavior checks.

AI, RAG, embeddings, and Qdrant are intentionally not implemented in this scaffold. Markdown extraction exists as the
first ingestion learning slice.

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
