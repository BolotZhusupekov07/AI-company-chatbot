from hashlib import sha256
from pathlib import Path

from app.knowledge.schemas import model as knowledge_model
from app.services.chunking_service import MarkdownChunker


def _source_document(content_markdown: str) -> knowledge_model.SourceDocument:
    return knowledge_model.SourceDocument(
        source_id="hr/policy.en.md",
        title="Policy",
        document_group_id="policy",
        language="en",
        space="hr",
        content_markdown=content_markdown,
        allowed_users=["aida@example.com"],
        allowed_groups=["employees"],
        version=3,
        updated_at="2026-05-15T09:00:00Z",
        content_hash=sha256(content_markdown.encode("utf-8")).hexdigest(),
        path=Path("hr/policy.en.md"),
    )


def test_chunk_document_preserves_source_metadata() -> None:
    document = _source_document("# Policy\n\nEmployees receive support.\n")
    expected_content_markdown = "# Policy\n\nEmployees receive support."
    expected_chunk = knowledge_model.KnowledgeChunk(
        chunk_id="hr/policy.en.md:chunk:0001",
        source_id=document.source_id,
        document_group_id=document.document_group_id,
        language=document.language,
        space=document.space,
        content_markdown=expected_content_markdown,
        chunk_index=0,
        character_count=len(expected_content_markdown),
        content_hash=sha256(expected_content_markdown.encode("utf-8")).hexdigest(),
        allowed_users=document.allowed_users,
        allowed_groups=document.allowed_groups,
    )

    chunks = MarkdownChunker(target_characters=300, overlap_characters=50, max_characters=400).chunk_document(document)

    assert chunks == [expected_chunk]


def test_large_heading_section_does_not_cross_into_next_heading() -> None:
    alpha_paragraphs = "\n\n".join(
        f"Alpha paragraph {index} has enough plain words to force another chunk boundary." for index in range(1, 9)
    )
    markdown = f"# Alpha\n\n{alpha_paragraphs}\n\n# Beta\n\nBeta stays separate."

    chunks = MarkdownChunker(target_characters=180, overlap_characters=30, max_characters=220).chunk_markdown(markdown)

    assert len(chunks) > 2
    alpha_chunks = [chunk for chunk in chunks if "# Alpha" in chunk]
    assert alpha_chunks
    assert all("# Beta" not in chunk for chunk in alpha_chunks)
    assert any("# Beta" in chunk for chunk in chunks)


def test_overlap_is_added_between_chunks_from_one_large_section() -> None:
    markdown = "\n\n".join(
        [
            "# Policy",
            "aa bb cc dd",
            "ee ff gg hh",
            "ii jj kk ll",
        ],
    )

    chunks = MarkdownChunker(target_characters=28, overlap_characters=5, max_characters=40).chunk_markdown(markdown)

    assert len(chunks) == 3
    assert "cc dd" in chunks[1]
    assert "gg hh" in chunks[2]


def test_list_items_are_kept_as_split_boundaries() -> None:
    markdown = "\n".join(
        [
            "# Onboarding",
            "",
            "- First item has words for the first chunk.",
            "- Second item has words for the second chunk.",
            "- Third item has words for the third chunk.",
        ],
    )

    chunks = MarkdownChunker(target_characters=80, overlap_characters=15, max_characters=120).chunk_markdown(markdown)

    assert len(chunks) > 1
    assert any("- First item has words for the first chunk." in chunk for chunk in chunks)
    assert any("- Second item has words for the second chunk." in chunk for chunk in chunks)
    assert any("- Third item has words for the third chunk." in chunk for chunk in chunks)


def test_large_paragraph_splits_on_sentence_boundaries_before_characters() -> None:
    markdown = (
        "# Policy\n\n"
        "First sentence has enough words to stand alone. "
        "Second sentence has enough words to become another piece. "
        "Third sentence has enough words to become the final piece."
    )

    chunks = MarkdownChunker(target_characters=75, overlap_characters=15, max_characters=120).chunk_markdown(markdown)

    assert len(chunks) > 1
    assert any("First sentence has enough words to stand alone." in chunk for chunk in chunks)
    assert any("Second sentence has enough words to become another piece." in chunk for chunk in chunks)
    assert any("Third sentence has enough words to become the final piece." in chunk for chunk in chunks)


def test_table_that_fits_is_kept_whole_with_heading_and_intro() -> None:
    markdown = "\n".join(
        [
            "# Expenses",
            "",
            "Use these limits.",
            "",
            "| Type | Limit |",
            "| --- | --- |",
            "| Meal | 20 |",
            "| Taxi | 40 |",
        ],
    )

    chunks = MarkdownChunker(target_characters=400, overlap_characters=50, max_characters=500).chunk_markdown(markdown)

    table_chunks = [chunk for chunk in chunks if "| Type | Limit |" in chunk]
    assert len(table_chunks) == 1
    assert table_chunks[0] == "\n".join(
        [
            "# Expenses",
            "",
            "Use these limits.",
            "",
            "| Type | Limit |",
            "| --- | --- |",
            "| Meal | 20 |",
            "| Taxi | 40 |",
        ],
    )


def test_large_table_splits_by_rows_with_header_heading_and_intro_repeated() -> None:
    rows = [f"| Month {index} | {index * 100} |" for index in range(1, 8)]
    markdown = "\n".join(
        [
            "# Payroll",
            "",
            "Amounts by month.",
            "",
            "| Month | Amount |",
            "| --- | --- |",
            *rows,
        ],
    )

    chunks = MarkdownChunker(target_characters=120, overlap_characters=20, max_characters=180).chunk_markdown(markdown)
    table_chunks = [chunk for chunk in chunks if "| Month | Amount |" in chunk]

    assert len(table_chunks) > 1
    emitted_rows: list[str] = []
    for chunk in table_chunks:
        assert chunk.startswith("# Payroll\n\nAmounts by month.\n\n| Month | Amount |\n| --- | --- |")
        assert chunk.count("| Month | Amount |") == 1
        emitted_rows.extend(line for line in chunk.splitlines() if line.startswith("| Month ") and "Amount" not in line)

    assert emitted_rows == rows
