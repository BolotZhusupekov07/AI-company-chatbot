import argparse
import json
from pathlib import Path

from infrastructure.knowledge_sources.markdown import loader


def main() -> None:
    """Load Markdown documents and print normalized source documents as JSON."""

    parser = argparse.ArgumentParser(description="Extract local Markdown company knowledge.")
    parser.add_argument("--kb-path", default="sample_company_kb", help="Path to the Markdown knowledge base.")
    args = parser.parse_args()

    documents = loader.MarkdownKnowledgeLoader(Path(args.kb_path)).load_documents()
    payload = {
        "documents_count": len(documents),
        "documents": [document.model_dump(mode="json") for document in documents],
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
