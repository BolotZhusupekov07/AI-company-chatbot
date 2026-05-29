# AI Chatbot Company

Minimal FastAPI project for learning how to build a company knowledge chatbot. The current implementation covers local
Markdown ingestion, structure-aware chunking, Bedrock Cohere embeddings, Qdrant vector storage, and dense search.

## What Is Implemented

- FastAPI application with health checks.
- Sample company knowledge base in `sample_company_kb/`.
- Markdown loader that parses YAML frontmatter into `SourceDocument` models.
- Structure-aware Markdown chunking into `KnowledgeChunk` models.
- AWS Bedrock Cohere Embed Multilingual v3 provider.
- Local Qdrant vector store integration.
- Ingestion CLI that loads, chunks, embeds, and stores chunks in Qdrant.
- Dense-search CLI that embeds a query and searches Qdrant.
- Basic Qdrant ACL filter helper using `allowed_users` and `allowed_groups`.
- Local YAML identity resolver using `sample_company_kb/metadata/users.yaml` and `groups.yaml`.
- HTTP chat API backed by PostgreSQL chats and chat messages.

Not implemented yet:

- LLM answer generation.
- Hybrid search, reranking, chat memory, evaluations, and streaming.

## How It Works

The current data flow is:

```text
sample_company_kb/*.md
  -> MarkdownKnowledgeLoader
  -> SourceDocument
  -> MarkdownChunker
  -> KnowledgeChunk
  -> BedrockCohereEmbeddingProvider.embed_chunks()
  -> QdrantVectorRepository.upsert_chunks()
  -> Qdrant collection
```

Dense search works like this:

```text
user query
  -> BedrockCohereEmbeddingProvider.embed_query()
  -> optional Qdrant ACL filter
  -> QdrantVectorRepository.search_dense()
  -> scored chunk payloads
```

Qdrant payloads store:

- `chunk_id`
- `source_id`
- `document_group_id`
- `language`
- `space`
- `allowed_users`
- `allowed_groups`
- `text`
- `chunk_index`
- `character_count`

## Project Structure

```text
app/main.py                         FastAPI app factory and local run entrypoint
app/api/                            HTTP routers and schemas
app/core/                           settings and core wiring
app/services/                       application services such as chunking
app/infrastructure/embeddings/      Bedrock Cohere embedding adapter
app/infrastructure/knowledge_sources/ Markdown source loader
app/infrastructure/db/              SQLAlchemy database session and models
app/infrastructure/vector_store/    Qdrant vector store adapter
app/knowledge/                      internal knowledge schemas
app/cli/                            CLI scripts
sample_company_kb/                  local sample knowledge base
tests/api/                          API behavior checks
tests/unit/                         unit behavior checks
docs/learning-roadmap.md            implementation roadmap
```

## Prerequisites

- Python 3.13 or newer.
- `uv`.
- Docker, for local PostgreSQL and Qdrant.
- AWS credentials with access to Bedrock Cohere Embed Multilingual v3.

The app uses normal `boto3` credential discovery. Configure credentials through your AWS profile, environment variables,
or another supported AWS credential source.

## Setup

Install dependencies:

```bash
uv sync
```

Create local config:

```bash
cp config/.env.example config/.env
```

Important config values:

```env
AWS_REGION_NAME=eu-central-1
DATABASE_URL=postgresql+psycopg://chatbot:chatbot@localhost:5433/ai_chatbot_company
CHAT_LLM_MODEL_ID=eu.anthropic.claude-haiku-4-5-20251001-v1:0
QDRANT_URL=http://localhost:6335
QDRANT_API_KEY=
QDRANT_COLLECTION_NAME=company_knowledge_chunks
```

Start PostgreSQL and Qdrant:

```bash
docker compose up -d postgres qdrant
```

The included compose file maps:

- host `5433` to PostgreSQL port `5432`
- host `6335` to Qdrant HTTP port `6333`
- host `6336` to Qdrant gRPC port `6334`

Run migrations:

```bash
uv run alembic upgrade head
```

Check Qdrant:

```bash
curl http://localhost:6335/collections
```

## Run The API

```bash
make run
```

API docs:

- http://localhost:8000/docs
- http://localhost:8000/redoc

Health checks and chat endpoints are available through the FastAPI app.

## Run CLI Scripts

### Ingest Knowledge Into Qdrant

This command loads Markdown from `sample_company_kb/`, chunks it, embeds chunks with Bedrock Cohere, creates the Qdrant
collection if needed, and upserts chunk vectors plus payloads.

```bash
uv run python -m app.cli.ingestion_pipeline
```

Expected output is a short report like:

```text
Loaded 20 documents, created 20 chunks, embedded 20 vectors.
Embeddings are stored
```

The exact chunk count can change when chunking settings or knowledge files change.

### Run Dense Search

Run this after ingestion has stored vectors in Qdrant:

```bash
uv run python -m app.cli.dense_search "How do I access VPN?"
```

The script embeds the query with Cohere, searches Qdrant, and prints matching chunk payloads with scores.

Current dense-search CLI behavior:

- uses `QDRANT_COLLECTION_NAME` from `config/.env`
- returns up to 3 results
- applies a basic ACL filter using the hardcoded user/groups in the script
- applies a score threshold of `0.5`

Those values should move behind CLI flags or a retrieval service when the next retrieval slice is implemented.

## Checks

Run all checks:

```bash
make check
```

Or run individual checks:

```bash
make lint
make typecheck
make test
```

## Useful Development Commands

```bash
docker compose up -d qdrant
docker compose up -d postgres
docker compose ps
docker compose stop postgres qdrant
uv run alembic upgrade head
uv run python -m app.cli.ingestion_pipeline
uv run python -m app.cli.dense_search "vacation policy"
make check
```
