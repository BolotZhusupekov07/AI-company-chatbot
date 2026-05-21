from pathlib import Path

from app.infrastructure.knowledge_sources.markdown import loader
from app.services.chunking_service import MarkdownChunker


def main() -> None:
    documents = loader.MarkdownKnowledgeLoader(Path("sample_company_kb")).load_documents()
    
    chunker = MarkdownChunker()
    all_chunks = []
    for document in documents:
        chunks = chunker.chunk_document(document)
        all_chunks.extend(chunks)
    


if __name__ == "__main__":
    main()
