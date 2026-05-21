from argparse import ArgumentParser
from typing import Sequence
from app.core.config import get_settings
from app.infrastructure.embeddings.bedrock_cohere_provider import BedrockCohereEmbeddingProvider
from app.infrastructure.vector_store.qdrant.client import build_qdrant_client
from app.infrastructure.vector_store.qdrant.repository import QdrantVectorRepository, build_acl_filter


def main(argv: Sequence[str] | None = None) -> None:
    """Run dense search."""

    parser = ArgumentParser(description="Run dense search")
    parser.add_argument("query")
    
    args = parser.parse_args(argv)

    if not args.query.strip():
        raise ValueError("query must not be blank")

    settings = get_settings()

    embedding_provider = BedrockCohereEmbeddingProvider(region_name=settings.AWS_REGION_NAME)
    query_vector = embedding_provider.embed_query(args.query)

    qdrant_client = build_qdrant_client(settings)
    qdrant_repo = QdrantVectorRepository(client=qdrant_client, collection_name=settings.QDRANT_COLLECTION_NAME)
    results = qdrant_repo.search_dense(
        query_vector,
        limit=3,
        query_filter=build_acl_filter("example@gmail.com", ["hr"]),
        score_threshold=0.5
    )

    print(
        {
            "query": args.query,
            "result_count": len(results),
            "results": [
                {
                    "score": result.score,
                    **result.payload.model_dump(mode="json"),
                }
                for result in results
            ],
        }
    )


if __name__ == "__main__":
    main()
