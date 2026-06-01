# AI Chatbot Company

Minimal FastAPI project for learning how to build a company knowledge chatbot. The current implementation covers local
Markdown ingestion, structure-aware chunking, Bedrock Cohere embeddings, Qdrant vector storage, hybrid search, remote
reranking, PostgreSQL chat persistence, and a retrieval-backed Bedrock chat API.

## What Is Implemented

- FastAPI application with health checks.
- Versioned chat API for listing, reading, updating, soft-deleting, and creating chat messages.
- PostgreSQL chat and chat-message persistence with SQLAlchemy models and Alembic migrations.
- Chat-answer service using Pydantic AI with Bedrock Converse.
- Structured agent output with `answer`, `used_rag`, and `confidence`.
- Message history passed into the chat model for follow-up answers.
- Company knowledge search tool that runs ACL-aware hybrid retrieval before answering.
- Sample company knowledge base in `sample_company_kb/`.
- Markdown loader that parses YAML frontmatter into `SourceDocument` models.
- Structure-aware Markdown chunking into `KnowledgeChunk` models.
- AWS Bedrock Cohere Embed Multilingual v3 provider.
- Local Qdrant vector store integration with dense and BM25 sparse vectors.
- Ingestion CLI that loads, chunks, embeds, and stores dense plus sparse chunk vectors in Qdrant.
- Hybrid search service that asks Qdrant to fuse dense vector search and BM25 sparse search with RRF, then reranks candidates.
- Bedrock Cohere reranker with an OpenAI fallback reranker.
- Basic Qdrant ACL filter helper using `allowed_users` and `allowed_groups`.
- Local YAML identity resolver using `sample_company_kb/metadata/users.yaml` and `groups.yaml`.

Not implemented yet:

- Usage limits.
- Output validation and fallback on malformed output beyond the structured schema. There is no custom Pydantic AI output
  validator, retry on invalid answer contracts, or fallback provider when model output fails validation.
- Query rewrite agent. RAG embeds the user query directly; there is no native-language query rewrite agent or conditional
  English-translated fallback query pass.
- Document-group deduplication. Reranked chunks are returned as-is, without deduplication by `document_group_id`,
  language-preference tie-breaks, or citation target selection.
- Grounded answer citations. The RAG tool returns only the best chunk text, without source IDs, page URLs, chunk IDs,
  document summaries, citation metadata, or verified citation targets.
- Prompt-injection hardening around retrieved content. Retrieved text is not wrapped in explicit untrusted-content
  delimiters, and there is no citation verification or post-check.
- Token usage and cost attribution. There are no token-usage tables or per-call usage captures for chat, RAG, rerank,
  fallback, latency, or cost.
- Configurable sliding-window memory. Chat history is passed directly, without a configurable last-N window or
  summarization fallback.
- SSE streaming endpoint. Only synchronous JSON request-response exists; there is no `/stream` endpoint or SSE response
  flow.
- Evaluations.

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

Chat answering works like this:

```text
POST /v1/chats/messages
  -> ChatService creates or loads a PostgreSQL chat
  -> ChatService stores the user message
  -> ChatAnswerService runs the Bedrock Converse chat agent
  -> search_company_knowledge tool resolves the user from local YAML
  -> HybridSearchService retrieves ACL-visible knowledge chunks
  -> agent returns structured output with answer metadata
  -> ChatService stores and returns the answer text
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

## Run CLI Script

### Ingest Knowledge Into Qdrant

This command loads Markdown from `sample_company_kb/`, chunks it, embeds chunks with Bedrock Cohere, creates the Qdrant
collection if needed, and upserts dense vectors, explicit BM25 sparse vectors, and payloads.

```bash
uv run python -m app.cli.ingestion_pipeline
```

Expected output is a short report like:

```text
Loaded 20 documents, created 20 chunks, embedded 20 vectors.
Embeddings are stored
```

The exact chunk count can change when chunking settings or knowledge files change.

### Ask The Chat API

Run this after migrations have been applied and ingestion has stored dense and sparse vectors in Qdrant:

```bash
curl -X POST http://localhost:8000/v1/chats/messages \
  -H "Content-Type: application/json" \
  -H "X-User-Email: aida@example.com" \
  -d '{"content":"How do I access VPN?"}'
```

The chat answer path uses:

- Dense branch: Cohere Embed Multilingual v3 query vector over the full multilingual index with the ACL filter.
- Sparse branch: Qdrant BM25 over chunks in `KNOWLEDGE_SOURCE_LANGUAGE` with the same ACL filter.
- Fusion: Qdrant native Reciprocal Rank Fusion with `HYBRID_RRF_K`.
- Rerank: Bedrock Cohere Rerank 3.5 first, OpenAI fallback over `OPENAI_RERANK_CANDIDATE_LIMIT` candidates.
- Final answer: Bedrock Converse chat model with retrieved company knowledge as a tool result.

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
make check
```
