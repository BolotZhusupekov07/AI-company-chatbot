# AI Chatbot Company

Minimal project scaffold for learning how to build a company knowledge chatbot step by step.

This setup only gives you the application structure and a working FastAPI health endpoint. AI-related parts are intentionally left for you to build:

- knowledge extraction
- chunking
- embeddings
- Qdrant indexing
- retrieval
- reranking
- answer generation

## Local Setup

```bash
uv sync
cp config/.env.example config/.env
make run
```

API docs:

- http://localhost:8000/docs
- http://localhost:8000/redoc

## Checks

```bash
make check
```

## Structure

```text
app/main.py                         FastAPI app factory and run hook
app/api/                            HTTP routers and API schemas
app/core/                           Settings and core wiring
app/services/                       Orchestration code you add later
app/infrastructure/                 External adapters you add later
app/knowledge/                      Internal knowledge schemas
app/cli/                            CLI utilities
tests/api/                          API tests
tests/unit/                         Unit tests
```

## Implementation Roadmap

Build this project one working slice at a time. Do not start with the LLM. First make data flow through the system in a boring, testable way.

### Step 1: Add Sample Company Knowledge

Create a local folder that replaces Confluence for the pet project:

```text
sample_company_kb/
  hr/
    vacation-policy.en.md
    sick-leave.en.md
    remote-work.en.md
  it/
    vpn-access.en.md
  metadata/
    users.yaml
```

Each Markdown document should have YAML frontmatter:

```yaml
---
title: Vacation Policy
document_group_id: vacation-policy
language: en
space: hr
allowed_users: []
allowed_groups:
  - employees
version: 1
updated_at: "2026-05-15T09:00:00Z"
---
```

Goal: have 10-20 small documents with headings, lists, and at least one table.

Verify: open the files manually and make sure every document has frontmatter and useful body text.

### Step 2: Define Source Document Schemas

Add internal models for loaded knowledge files:

```text
app/knowledge/
  schemas/
    model.py
```

Create a `SourceDocument` model with fields like:

- `source_id`
- `title`
- `document_group_id`
- `language`
- `space`
- `content_markdown`
- `allowed_users`
- `allowed_groups`
- `version`
- `updated_at`
- `content_hash`
- `citation_url`

Goal: define the internal shape your app uses regardless of where knowledge comes from.

Verify: write a test that constructs `SourceDocument` with valid data.

### Step 3: Implement Markdown Loading

Add a Markdown source adapter:

```text
app/infrastructure/knowledge_sources/markdown/
  loader.py
```

The loader should:

- scan `sample_company_kb/**/*.md`
- parse YAML frontmatter
- return `SourceDocument` objects
- compute a stable `content_hash`
- build `citation_url` values like `kb://hr/vacation-policy.en.md`

Goal: replace Confluence with a simple local source.

Verify: write a test that loads a temporary Markdown file and checks the parsed fields.

### Step 4: Add An Ingestion Use Case

Add orchestration for loading documents:

```text
app/services/
  ingestion_service.py
app/knowledge/
  schemas/model.py
```

Start with a simple ingestion report:

- `documents_seen`
- `documents_loaded`
- `failed_documents`

Do not add embeddings yet.

Goal: run one command or function that loads all knowledge documents and returns a report.

Verify: test the use case with a small fixture KB.

### Step 5: Add An Ingestion CLI

Add a command-line entrypoint:

```text
app/cli/
  markdown_extraction.py
```

Command shape:

```bash
uv run python -m app.cli.markdown_extraction --kb-path sample_company_kb
```

Goal: make ingestion runnable without starting the API.

Verify: run the command and print the ingestion report as JSON.

### Step 6: Add Structure-Aware Chunking

Add chunking as service behavior before embeddings:

```text
app/knowledge/
  schemas/model.py
app/services/
  chunking_service.py
```

Start simple:

- split by Markdown headings
- then paragraphs
- target roughly 500 tokens or 2,000 characters
- add small overlap only after the basic splitter works
- preserve table text instead of splitting rows blindly

Goal: turn one `SourceDocument` into many `KnowledgeChunk` objects.

Verify: test headings, paragraphs, long sections, and tables.

### Step 7: Add Local Identity Resolution

Use local YAML instead of Jira:

```text
sample_company_kb/metadata/users.yaml
app/identity/
app/infrastructure/identity/local_yaml/
```

Example:

```yaml
users:
  alice@example.com:
    groups:
      - employees
      - engineering
  bob@example.com:
    groups:
      - employees
      - hr
```

Goal: resolve trusted user email into groups.

Verify: test known user, unknown user, and user with no groups.

### Step 8: Add Permission Filtering In Plain Python

Before Qdrant, prove ACL logic with normal Python functions.

A chunk is visible if:

- `allowed_users` contains the user email, or
- `allowed_groups` intersects the user's groups.

Goal: make permission behavior obvious before pushing filters into a vector DB.

Verify: test employee-only, HR-only, user-specific, and inaccessible chunks.

### Step 9: Add Embedding Provider Interface

Add only the interface first:

```text
app/services/interfaces/
  embedding_provider.py
```

It should expose something like:

```python
async def embed_texts(self, texts: list[str]) -> list[list[float]]:
    ...
```

Goal: keep the rest of the app independent from Bedrock/OpenAI/local models.

Verify: test downstream code with a fake embedding provider that returns fixed vectors.

### Step 10: Add A Real Embedding Provider

Pick one provider for the first working version.

Recommended for your target architecture:

- Amazon Bedrock
- Cohere Embed Multilingual v3

Keep the provider in infrastructure:

```text
app/infrastructure/embeddings/
  bedrock_cohere_provider.py
```

Goal: convert chunk text and query text into vectors.

Verify: write provider-contract tests with a fake Bedrock client first, then run one manual real-provider call when credentials are configured.

### Step 11: Add Qdrant Locally

Add Qdrant to Docker Compose only when embeddings work.

Then add:

```text
app/infrastructure/vector_store/qdrant/
  client.py
  collection.py
  repository.py
```

Store each chunk with:

- vector
- chunk text
- source metadata
- ACL payload fields
- `document_group_id`
- `language`
- `citation_url`

Goal: persist chunks in a searchable vector collection.

Verify: upsert a few chunks and retrieve them by ID before doing semantic search.

### Step 12: Implement Dense Retrieval

Add a retrieval use case:

```text
app/services/
  retrieval_service.py
```

Flow:

1. resolve user identity
2. embed the query
3. build permission filter
4. search Qdrant
5. return visible chunks only

Goal: retrieve relevant chunks the user is allowed to see.

Verify: ask the same query as `alice@example.com` and `bob@example.com`; HR-only content should only appear for HR users.

### Step 13: Add Chat API Without LLM

Before answer generation, expose retrieval through HTTP:

```text
app/api/v1/chats/
  routes.py
  schemas.py
```

Start with an endpoint that returns retrieved chunks:

```text
POST /v1/chats/messages
```

Request:

```json
{
  "user_email": "alice@example.com",
  "message": "How many vacation days do I have?"
}
```

Goal: prove API -> use case -> retrieval works before adding an LLM.

Verify: write an HTTP test with fake retrieval.

### Step 14: Add Chat Provider Interface

Add only the interface first:

```text
app/services/interfaces/
  chat_provider.py
```

It should accept a system prompt and user/context prompt, and return text.

Goal: keep answer generation independent from provider details.

Verify: test answer orchestration with a fake provider.

### Step 15: Add Grounded Answer Generation

Add an answer use case:

```text
app/services/
  answering_service.py
```

The prompt must require:

- answer only from retrieved context
- decline when context is insufficient
- cite only retrieved sources
- treat retrieved text as untrusted data
- answer in the user's language when practical

Goal: transform retrieved chunks into a final answer with citations.

Verify: test with a fake chat provider first; then manually test with the real provider.

### Step 16: Add Real Chat Provider

Recommended provider for your target architecture:

- Amazon Bedrock Claude

Keep it in infrastructure:

```text
app/infrastructure/llms/
  bedrock_chat_provider.py
```

Goal: call the real model only after retrieval and prompting are testable.

Verify: contract-test request/response parsing with a fake Bedrock client, then run one manual real-provider call.

### Step 17: Add PostgreSQL Chat Memory

Add database support after the request/response path works.

Tables:

- `chats`
- `messages`

Keep storage in:

```text
app/infrastructure/storage/postgres/
```

Goal: store conversations and load the last N messages for context.

Verify: integration-test create chat, append message, list messages.

### Step 18: Add Token Usage Tracking

Add token/cost tracking once real LLM calls exist.

Tables:

- `message_token_usage`
- later: `ingestion_run_token_usage`

Goal: know which user/message/provider/model generated cost.

Verify: fake provider returns fake usage; assert rows are written.

### Step 19: Add Hybrid Search

Only after dense retrieval works, add sparse search:

- BM25 or Qdrant sparse vectors
- RRF fusion

Goal: improve exact-match retrieval for acronyms, names, and internal terms.

Verify: create tests where dense search misses an exact internal keyword and sparse search finds it.

### Step 20: Add Reranking

After hybrid search works, add reranking:

- Bedrock Cohere Rerank if available in your region
- or a small LLM pointwise scorer

Goal: improve top-K precision.

Verify: use a fixed candidate set and assert reranking changes the order correctly.

### Step 21: Add Contextual Enrichment

Only after baseline retrieval is measurable, enrich chunks before embedding.

Flow:

1. send full document + chunk to a small model
2. generate 1-2 sentence context
3. prepend context before embedding
4. keep original chunk text for answers

Goal: improve retrieval without changing cited content.

Verify: compare retrieval results before/after on a small question set.

### Step 22: Add Image Processing

Add this late because it increases cost and complexity.

Flow:

1. extract image references from Markdown
2. describe images with a vision model
3. cache descriptions
4. insert descriptions into text before chunking

Goal: make image information searchable.

Verify: use one sample image and assert its description can be retrieved.

### Step 23: Add Evaluation Tests

Create a small evaluation set:

```text
evals/
  hr_questions.yaml
```

Each case should include:

- user email
- question
- expected source document
- expected answer facts
- should decline or answer

Goal: measure quality before changing chunking, prompts, embeddings, or reranking.

Verify: run evals locally and compare pass/fail counts.

### Step 24: Add Streaming Later

Keep the normal JSON endpoint as the primary API.

Add SSE only after the synchronous path is stable:

```text
POST /v1/chats/messages/stream
```

Goal: improve UX without changing core answer logic.

Verify: test event order and final payload shape.

## Recommended Build Order

Use this strict order:

1. Sample Markdown KB
2. Source document schema
3. Markdown loader
4. Ingestion report
5. CLI
6. Chunking
7. Local identity resolver
8. Plain Python ACL filter
9. Fake embedding provider
10. Real embedding provider
11. Qdrant storage
12. Dense retrieval
13. HTTP retrieval endpoint
14. Fake chat provider
15. Grounded answer use case
16. Real chat provider
17. PostgreSQL chat memory
18. Token usage tracking
19. Hybrid search
20. Reranking
21. Contextual enrichment
22. Image processing
23. Evaluation harness
24. SSE streaming

At every step: write a small test, run it, and do not move to the next step until the current one works.
