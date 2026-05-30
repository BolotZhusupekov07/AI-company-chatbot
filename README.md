# AI Chatbot Company

Minimal FastAPI project for learning how to build a company knowledge chatbot. The current implementation covers local
Markdown ingestion, structure-aware chunking, Bedrock Cohere embeddings, Qdrant vector storage, hybrid search, and
remote reranking.

## What Is Implemented

- FastAPI application with health checks.
- Sample company knowledge base in `sample_company_kb/`.
- Markdown loader that parses YAML frontmatter into `SourceDocument` models.
- Structure-aware Markdown chunking into `KnowledgeChunk` models.
- AWS Bedrock Cohere Embed Multilingual v3 provider.
- Local Qdrant vector store integration with dense and BM25 sparse vectors.
- Ingestion CLI that loads, chunks, embeds, and stores dense plus sparse chunk vectors in Qdrant.
- Dense-search CLI that embeds a query and searches Qdrant.
- Hybrid-search CLI that asks Qdrant to fuse dense vector search and BM25 sparse search with RRF, then reranks candidates.
- Basic Qdrant ACL filter helper using `allowed_users` and `allowed_groups`.
- Local YAML identity resolver using `sample_company_kb/metadata/users.yaml` and `groups.yaml`.
- HTTP chat API backed by PostgreSQL chats and chat messages.

Not implemented yet:

- Chat memory, evaluations, and streaming.

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
  -> Qdrant collection with dense vectors and BM25 sparse vectors
```

Hybrid search works like this:

```text
user query
  -> BedrockCohereEmbeddingProvider.embed_query()
  -> QdrantVectorRepository.search_hybrid()
     -> Qdrant prefetch: dense vector search with ACL filter
     -> Qdrant prefetch: BM25 sparse search with ACL + source-language filters
     -> Qdrant RRF fusion
  -> Bedrock Cohere Rerank 3.5
     -> OpenAI fallback with smaller candidate budget when Bedrock rerank is unavailable
  -> reranked chunk payloads
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
QDRANT_DENSE_VECTOR_NAME=dense
QDRANT_SPARSE_VECTOR_NAME=sparse
QDRANT_BM25_MODEL_ID=Qdrant/bm25
QDRANT_BM25_LANGUAGE=english
KNOWLEDGE_SOURCE_LANGUAGE=en
BEDROCK_RERANK_MODEL_ID=cohere.rerank-v3-5:0
OPENAI_API_KEY=
OPENAI_RERANK_MODEL_ID=gpt-4o-mini
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
collection if needed, and upserts dense vectors, explicit BM25 sparse vectors, and payloads.

```bash
uv run python -m app.cli.ingestion_pipeline
```

Expected output is a short report like:

```text
Loaded 20 documents, created 20 chunks, embedded 20 vectors.
Dense and sparse embeddings are stored
```

The exact chunk count can change when chunking settings or knowledge files change.

### Run Dense Search

Run this after ingestion has stored vectors in Qdrant:

```bash
uv run python -m app.cli.dense_search "How do I access VPN?" aida@example.com
```

The script embeds the query with Cohere, searches Qdrant, and prints matching chunk payloads with scores.

Current dense-search CLI behavior:

- uses `QDRANT_COLLECTION_NAME` from `config/.env`
- returns up to 3 results
- applies a basic ACL filter using the hardcoded user/groups in the script
- applies a score threshold of `0.5`

Those values should move behind CLI flags or a retrieval service when the next retrieval slice is implemented.

### Run Hybrid Search

Run this after re-ingestion has stored dense and sparse vectors in Qdrant:

```bash
uv run python -m app.cli.hybrid_search "How do I access VPN?" aida@example.com
```

Hybrid search uses:

- Dense branch: Cohere Embed Multilingual v3 query vector over the full multilingual index with the ACL filter.
- Sparse branch: Qdrant BM25 over chunks in `KNOWLEDGE_SOURCE_LANGUAGE` with the same ACL filter.
- Fusion: Qdrant native Reciprocal Rank Fusion with `HYBRID_RRF_K`.
- Rerank: Bedrock Cohere Rerank 3.5 first, OpenAI fallback over `OPENAI_RERANK_CANDIDATE_LIMIT` candidates.

If you already have a dense-only Qdrant collection from an older run, delete or rename it before re-ingesting because
the hybrid collection needs the named `dense` vector and the `sparse` BM25 vector field.

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
