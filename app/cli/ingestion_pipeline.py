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
    qdrant_repo = QdrantVectorRepository(client=qdrant_client, collection_name=settings.QDRANT_COLLECTION_NAME)
    qdrant_repo.ensure_collection(vector_size=1024)

    qdrant_repo.upsert_chunks(all_chunks, chunk_embeddings)

    print("Embeddings are stored")


if __name__ == "__main__":
    main()
