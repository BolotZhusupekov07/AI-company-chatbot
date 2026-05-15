from hashlib import sha256

import pytest

from infrastructure.knowledge_sources.markdown import loader


def test_load_documents_parses_frontmatter_and_markdown_body(tmp_path) -> None:
    kb_path = tmp_path / "sample_company_kb"
    hr_path = kb_path / "hr"
    hr_path.mkdir(parents=True)
    document_path = hr_path / "vacation-policy.en.md"
    document_body = "# Vacation Policy\n\nEmployees receive 24 vacation days.\n"
    document_path.write_text(
        "\n".join(
            [
                "---",
                "title: Vacation Policy",
                "document_group_id: vacation-policy",
                "language: en",
                "space: hr",
                "allowed_users:",
                "  - aida@example.com",
                "allowed_groups:",
                "  - employees",
                "version: 2",
                'updated_at: "2026-05-15T09:00:00Z"',
                "---",
                document_body,
            ],
        ),
        encoding="utf-8",
    )

    documents = loader.MarkdownKnowledgeLoader(kb_path).load_documents()

    assert len(documents) == 1
    document = documents[0]
    assert document.source_id == "hr/vacation-policy.en.md"
    assert document.title == "Vacation Policy"
    assert document.document_group_id == "vacation-policy"
    assert document.language == "en"
    assert document.space == "hr"
    assert document.content_markdown == document_body
    assert document.allowed_users == ["aida@example.com"]
    assert document.allowed_groups == ["employees"]
    assert document.version == 2
    assert document.updated_at == "2026-05-15T09:00:00Z"
    assert document.content_hash == sha256(document_body.encode("utf-8")).hexdigest()


def test_load_documents_infers_title_language_document_group_and_space(tmp_path) -> None:
    kb_path = tmp_path / "sample_company_kb"
    company_path = kb_path / "company"
    company_path.mkdir(parents=True)
    body = "# Working Hours\n\nCore hours are 10:30 to 16:30 Bishkek time.\n"
    (company_path / "working-hours.en.md").write_text(
        "\n".join(
            [
                "---",
                "allowed_groups:",
                "  - employees",
                "---",
                body,
            ],
        ),
        encoding="utf-8",
    )

    document = loader.MarkdownKnowledgeLoader(kb_path).load_documents()[0]

    assert document.title == "Working Hours"
    assert document.document_group_id == "working-hours"
    assert document.language == "en"
    assert document.space == "company"
    assert document.allowed_users == []
    assert document.allowed_groups == ["employees"]
    assert document.version == 1
    assert document.updated_at is None


def test_load_documents_rejects_markdown_without_frontmatter(tmp_path) -> None:
    kb_path = tmp_path / "sample_company_kb"
    hr_path = kb_path / "hr"
    hr_path.mkdir(parents=True)
    (hr_path / "broken.en.md").write_text("# Broken\n\nNo frontmatter.\n", encoding="utf-8")

    with pytest.raises(loader.MarkdownFrontmatterError, match="missing YAML frontmatter"):
        loader.MarkdownKnowledgeLoader(kb_path).load_documents()
