from pathlib import Path

from app.core.config import get_settings
from app.infrastructure.embeddings.bedrock_cohere_provider import BedrockCohereEmbeddingProvider
from app.infrastructure.knowledge_sources.markdown import loader
from app.infrastructure.vector_store.qdrant.client import build_qdrant_client
from app.infrastructure.vector_store.qdrant.repository import QdrantVectorRepository
from app.services.chunking_service import MarkdownChunker


def main() -> None:
    # Loading documents from local folder
    documents = loader.MarkdownKnowledgeLoader(Path("sample_company_kb")).load_documents()

    # Structure aware chunking
    chunker = MarkdownChunker()
    all_chunks = []
    for document in documents:
        chunks = chunker.chunk_document(document)
        all_chunks.extend(chunks)

    settings = get_settings()

    # AWS Cohere Embed Multilingual V3
    embedding_provider = BedrockCohereEmbeddingProvider(region_name=settings.AWS_REGION_NAME)
    chunk_embeddings = embedding_provider.embed_chunks([chunk.content_markdown for chunk in all_chunks])

    print(
        f"Loaded {len(documents)} documents, created {len(all_chunks)} chunks, "
        f"embedded {len(chunk_embeddings)} vectors."
    )

    # Store chunk embeddings in Qdrant vector store
    qdrant_client = build_qdrant_client(settings)
    qdrant_repo = QdrantVectorRepository(
        client=qdrant_client,
        collection_name=settings.QDRANT_COLLECTION_NAME,
        dense_vector_name=settings.QDRANT_DENSE_VECTOR_NAME,
        sparse_vector_name=settings.QDRANT_SPARSE_VECTOR_NAME,
        sparse_model_id=settings.QDRANT_BM25_MODEL_ID,
        bm25_language=settings.QDRANT_BM25_LANGUAGE,
        dense_search_limit=settings.HYBRID_DENSE_LIMIT,
        sparse_search_limit=settings.HYBRID_SPARSE_LIMIT,
        rrf_k=settings.HYBRID_RRF_K,
        dense_score_threshold=settings.HYBRID_DENSE_SCORE_THRESHOLD,
    )
    qdrant_repo.ensure_collection(vector_size=settings.QDRANT_VECTOR_SIZE)

    qdrant_repo.upsert_chunks(all_chunks, chunk_embeddings)

    print("Embeddings are stored")


if __name__ == "__main__":
    main()
