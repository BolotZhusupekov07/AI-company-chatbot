from dataclasses import dataclass
from hashlib import sha256
import re

from app.knowledge.schemas import model as knowledge_model

DEFAULT_TARGET_CHARACTERS = 500
DEFAULT_OVERLAP_CHARACTERS = 100
DEFAULT_MAX_CHARACTERS = 700

_HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$")
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_TABLE_SEPARATOR_CELL_RE = re.compile(r":?-{3,}:?")


@dataclass(frozen=True)
class _Block:
    kind: str
    text: str


@dataclass(frozen=True)
class _Section:
    headings: list[str]
    blocks: list[_Block]


@dataclass(frozen=True)
class _ChunkCandidate:
    text: str
    can_combine: bool


class MarkdownChunker:
    """Splits Markdown into structure-aware chunks for indexing."""

    def __init__(
        self,
        target_characters: int = DEFAULT_TARGET_CHARACTERS,
        overlap_characters: int = DEFAULT_OVERLAP_CHARACTERS,
        max_characters: int = DEFAULT_MAX_CHARACTERS,
    ) -> None:
        if target_characters <= 0:
            raise ValueError("target_characters must be greater than zero")
        if overlap_characters < 0:
            raise ValueError("overlap_characters must be greater than or equal to zero")
        if max_characters < target_characters:
            raise ValueError("max_characters must be greater than or equal to target_characters")

        self.target_characters = target_characters
        self.overlap_characters = min(overlap_characters, target_characters - 1)
        self.max_characters = max_characters

    def chunk_document(self, document: knowledge_model.SourceDocument) -> list[knowledge_model.KnowledgeChunk]:
        """Chunk a loaded source document and copy source metadata onto each chunk."""

        chunk_texts = self.chunk_markdown(document.content_markdown)
        chunks: list[knowledge_model.KnowledgeChunk] = []

        for index, chunk_text in enumerate(chunk_texts):
            chunks.append(
                knowledge_model.KnowledgeChunk(
                    chunk_id=f"{document.source_id}:chunk:{index + 1:04d}",
                    source_id=document.source_id,
                    document_group_id=document.document_group_id,
                    language=document.language,
                    space=document.space,
                    content_markdown=chunk_text,
                    chunk_index=index,
                    character_count=len(chunk_text),
                    content_hash=sha256(chunk_text.encode("utf-8")).hexdigest(),
                    allowed_users=list(document.allowed_users),
                    allowed_groups=list(document.allowed_groups),
                ),
            )

        return chunks

    def chunk_markdown(self, markdown: str) -> list[str]:
        """Split Markdown text into chunk strings."""

        sections = _parse_sections(markdown)
        candidates: list[_ChunkCandidate] = []

        for section in sections:
            section_text = _section_text(section)
            if not section_text:
                continue
            if len(section_text) <= self.target_characters:
                candidates.append(_ChunkCandidate(text=section_text, can_combine=True))
                continue

            candidates.extend(
                _ChunkCandidate(text=chunk, can_combine=False) for chunk in self._chunk_large_section(section)
            )

        return self._pack_small_sections(candidates)

    def _pack_small_sections(self, candidates: list[_ChunkCandidate]) -> list[str]:
        chunks: list[str] = []
        current_parts: list[str] = []

        for candidate in candidates:
            if not candidate.text:
                continue

            if not candidate.can_combine:
                if current_parts:
                    chunks.append(_join_markdown_parts(current_parts))
                    current_parts = []
                chunks.append(candidate.text)
                continue

            if not current_parts:
                current_parts = [candidate.text]
                continue

            combined = _join_markdown_parts([*current_parts, candidate.text])
            if len(combined) <= self.target_characters:
                current_parts.append(candidate.text)
            else:
                chunks.append(_join_markdown_parts(current_parts))
                current_parts = [candidate.text]

        if current_parts:
            chunks.append(_join_markdown_parts(current_parts))

        return chunks

    def _chunk_large_section(self, section: _Section) -> list[str]:
        prefix = _join_markdown_parts(section.headings)
        chunks: list[str] = []
        current_content = ""

        for index, block in enumerate(section.blocks):
            if block.kind == "table":
                if current_content:
                    chunks.append(_join_markdown_parts([prefix, current_content]))
                    current_content = ""

                intro = _table_intro(section.blocks, index)
                chunks.extend(self._chunk_table(prefix, intro, block.text))
                continue

            block_chunks, current_content = self._chunk_text_block(prefix, current_content, block.text)
            chunks.extend(block_chunks)

        if current_content:
            chunks.append(_join_markdown_parts([prefix, current_content]))

        if not chunks and prefix:
            chunks.append(prefix)

        return chunks

    def _chunk_text_block(self, prefix: str, current_content: str, text: str) -> tuple[list[str], str]:
        chunks: list[str] = []

        for piece in self._split_text_block(prefix, text):
            chunk, current_content = self._append_text_piece(prefix, current_content, piece)
            if chunk is not None:
                chunks.append(chunk)

        return chunks, current_content

    def _append_text_piece(
        self,
        prefix: str,
        current_content: str,
        piece: str,
    ) -> tuple[str | None, str]:
        if not current_content:
            return None, piece

        combined_content = _join_markdown_parts([current_content, piece])
        if self._fits_with_prefix(prefix, combined_content):
            return None, combined_content

        chunk = _join_markdown_parts([prefix, current_content])
        overlap = _ending_overlap(current_content, self.overlap_characters)
        next_content = _join_markdown_parts([overlap, piece]) if overlap else piece
        if not self._fits_with_prefix(prefix, next_content) and overlap:
            return chunk, piece

        return chunk, next_content

    def _chunk_table(self, prefix: str, intro: str, table_text: str) -> list[str]:
        table_prefix = _join_markdown_parts([prefix, intro])
        full_table_chunk = _join_markdown_parts([table_prefix, table_text])
        if len(full_table_chunk) <= self.max_characters:
            return [full_table_chunk]

        table_lines = table_text.splitlines()
        if len(table_lines) <= 2:
            return [full_table_chunk]

        header_lines = table_lines[:2]
        rows = table_lines[2:]
        chunks: list[str] = []
        current_rows: list[str] = []

        for row in rows:
            candidate_rows = [*current_rows, row]
            candidate_table = "\n".join([*header_lines, *candidate_rows])
            candidate_chunk = _join_markdown_parts([table_prefix, candidate_table])

            if current_rows and len(candidate_chunk) > self.target_characters:
                chunks.append(_join_markdown_parts([table_prefix, "\n".join([*header_lines, *current_rows])]))
                current_rows = [row]
            else:
                current_rows = candidate_rows

        if current_rows:
            chunks.append(_join_markdown_parts([table_prefix, "\n".join([*header_lines, *current_rows])]))

        return chunks

    def _split_text_block(self, prefix: str, text: str) -> list[str]:
        content_capacity = max(1, self.target_characters - len(prefix))
        if len(text) <= content_capacity:
            return [text]

        sentences = _split_sentences(text)
        if len(sentences) > 1:
            return self._merge_units(sentences, content_capacity)

        return _split_by_characters(text, content_capacity)

    def _merge_units(self, units: list[str], content_capacity: int) -> list[str]:
        chunks: list[str] = []
        current = ""

        for unit in units:
            if len(unit) > content_capacity:
                if current:
                    chunks.append(current)
                    current = ""
                chunks.extend(_split_by_characters(unit, content_capacity))
                continue

            combined = _join_markdown_parts([current, unit])
            if current and len(combined) > content_capacity:
                chunks.append(current)
                current = unit
            else:
                current = combined

        if current:
            chunks.append(current)

        return chunks

    def _fits_with_prefix(self, prefix: str, content: str) -> bool:
        return len(_join_markdown_parts([prefix, content])) <= self.target_characters


def chunk_document(
    document: knowledge_model.SourceDocument,
    target_characters: int = DEFAULT_TARGET_CHARACTERS,
    overlap_characters: int = DEFAULT_OVERLAP_CHARACTERS,
    max_characters: int = DEFAULT_MAX_CHARACTERS,
) -> list[knowledge_model.KnowledgeChunk]:
    """Chunk a source document with the default Markdown chunker."""

    return MarkdownChunker(
        target_characters=target_characters,
        overlap_characters=overlap_characters,
        max_characters=max_characters,
    ).chunk_document(document)


def _parse_sections(markdown: str) -> list[_Section]:
    blocks = _parse_blocks(markdown)
    sections: list[_Section] = []
    heading_stack: list[str] = []
    current = _Section(headings=[], blocks=[])

    for block in blocks:
        heading_match = _HEADING_RE.match(block.text)
        if block.kind == "heading" and heading_match:
            if current.blocks:
                sections.append(current)

            heading_level = len(heading_match.group(1))
            heading_stack = heading_stack[: heading_level - 1]
            heading_stack.append(block.text)
            current = _Section(headings=list(heading_stack), blocks=[])
            continue

        current.blocks.append(block)

    if current.blocks or (current.headings and not sections):
        sections.append(current)

    return sections


def _parse_blocks(markdown: str) -> list[_Block]:
    lines = markdown.splitlines()
    blocks: list[_Block] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue

        if _HEADING_RE.match(line):
            blocks.append(_Block(kind="heading", text=line.strip()))
            index += 1
            continue

        if _is_table_start(lines, index):
            table_lines = [lines[index].rstrip(), lines[index + 1].rstrip()]
            index += 2
            while index < len(lines) and lines[index].strip() and _is_table_row(lines[index]):
                table_lines.append(lines[index].rstrip())
                index += 1
            blocks.append(_Block(kind="table", text="\n".join(table_lines)))
            continue

        if _LIST_ITEM_RE.match(line):
            item_lines = [line.rstrip()]
            index += 1
            while index < len(lines) and _is_list_continuation(lines, index):
                item_lines.append(lines[index].rstrip())
                index += 1
            blocks.append(_Block(kind="list_item", text="\n".join(item_lines).strip()))
            continue

        paragraph_lines = [line.rstrip()]
        index += 1
        while index < len(lines) and _is_paragraph_continuation(lines, index):
            paragraph_lines.append(lines[index].rstrip())
            index += 1
        blocks.append(_Block(kind="paragraph", text="\n".join(paragraph_lines).strip()))

    return blocks


def _is_paragraph_continuation(lines: list[str], index: int) -> bool:
    line = lines[index]
    return (
        bool(line.strip())
        and not _HEADING_RE.match(line)
        and not _LIST_ITEM_RE.match(line)
        and not _is_table_start(lines, index)
    )


def _is_list_continuation(lines: list[str], index: int) -> bool:
    line = lines[index]
    return (
        bool(line.strip())
        and not _HEADING_RE.match(line)
        and not _LIST_ITEM_RE.match(line)
        and not _is_table_start(lines, index)
    )


def _is_table_start(lines: list[str], index: int) -> bool:
    return index + 1 < len(lines) and _is_table_row(lines[index]) and _is_table_separator(lines[index + 1])


def _is_table_row(line: str) -> bool:
    return "|" in line and bool(line.strip())


def _is_table_separator(line: str) -> bool:
    if not _is_table_row(line):
        return False

    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return len(cells) >= 2 and all(_TABLE_SEPARATOR_CELL_RE.fullmatch(cell) for cell in cells)


def _section_text(section: _Section) -> str:
    return _join_markdown_parts([*section.headings, *(block.text for block in section.blocks)])


def _table_intro(blocks: list[_Block], table_index: int) -> str:
    if table_index == 0:
        return ""

    previous_block = blocks[table_index - 1]
    if previous_block.kind != "paragraph":
        return ""

    return previous_block.text


def _split_sentences(text: str) -> list[str]:
    return [sentence.strip() for sentence in _SENTENCE_SPLIT_RE.split(text) if sentence.strip()]


def _split_by_characters(text: str, content_capacity: int) -> list[str]:
    chunks: list[str] = []
    remaining = text.strip()
    max_chars = max(1, content_capacity)

    while remaining:
        end = min(len(remaining), max_chars)

        chunk = remaining[:end].strip()
        if not chunk:
            chunk = remaining[:1]
            end = 1

        chunks.append(chunk)
        remaining = remaining[end:].strip()

    return chunks


def _join_markdown_parts(parts: list[str]) -> str:
    return "\n\n".join(part.strip() for part in parts if part and part.strip())


def _ending_overlap(text: str, max_characters: int) -> str:
    if max_characters <= 0:
        return ""

    return text[-max_characters:].strip()
