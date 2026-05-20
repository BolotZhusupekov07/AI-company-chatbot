from hashlib import sha256
from pathlib import Path
from typing import Any

import yaml

from app.knowledge.schemas import model as knowledge_model


class MarkdownFrontmatterError(ValueError):
    """Raised when a Markdown file has invalid or missing frontmatter."""


class MarkdownKnowledgeLoader:
    """Loads Markdown files with YAML frontmatter into normalized source documents."""

    def __init__(self, kb_path: Path | str) -> None:
        self._kb_path = Path(kb_path)

    def load_documents(self) -> list[knowledge_model.SourceDocument]:
        """Load all Markdown documents under the configured knowledge base path."""

        documents: list[knowledge_model.SourceDocument] = []
        for path in sorted(self._kb_path.glob("**/*.md")):
            documents.append(self._load_document(path))
        return documents

    def _load_document(self, path: Path) -> knowledge_model.SourceDocument:
        frontmatter, body = _read_markdown_with_frontmatter(path)
        relative_path = path.relative_to(self._kb_path)
        title = _get_title(frontmatter, body, path)
        language = _get_language(frontmatter, path)
        document_group_id = _get_document_group_id(frontmatter, path, language)

        return knowledge_model.SourceDocument(
            source_id=relative_path.as_posix(),
            title=title,
            document_group_id=document_group_id,
            language=language,
            space=str(frontmatter.get("space") or relative_path.parts[0]),
            content_markdown=body,
            allowed_users=_get_string_list(frontmatter, "allowed_users"),
            allowed_groups=_get_string_list(frontmatter, "allowed_groups"),
            version=int(frontmatter.get("version", 1)),
            updated_at=frontmatter.get("updated_at"),
            content_hash=sha256(body.encode("utf-8")).hexdigest(),
            path=relative_path,
        )


def _read_markdown_with_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise MarkdownFrontmatterError(f"Markdown file is missing YAML frontmatter: {path}")

    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            raw_frontmatter = "".join(lines[1:index])
            body = "".join(lines[index + 1 :])
            parsed = yaml.safe_load(raw_frontmatter) or {}
            if not isinstance(parsed, dict):
                raise MarkdownFrontmatterError(f"Markdown frontmatter must be a mapping: {path}")
            return parsed, body

    raise MarkdownFrontmatterError(f"Markdown frontmatter is not closed: {path}")


def _get_title(frontmatter: dict[str, Any], body: str, path: Path) -> str:
    title = frontmatter.get("title")
    if title:
        return str(title)

    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped.removeprefix("# ").strip()

    return _title_from_filename(path)


def _get_language(frontmatter: dict[str, Any], path: Path) -> str:
    language = frontmatter.get("language")
    if language:
        return str(language)

    parts = path.name.split(".")
    if len(parts) >= 3:
        return parts[-2]

    return "unknown"


def _get_document_group_id(frontmatter: dict[str, Any], path: Path, language: str) -> str:
    document_group_id = frontmatter.get("document_group_id")
    if document_group_id:
        return str(document_group_id)

    suffix = f".{language}.md"
    if path.name.endswith(suffix):
        return path.name[: -len(suffix)]

    return path.stem


def _get_string_list(frontmatter: dict[str, Any], key: str) -> list[str]:
    values = frontmatter.get(key, [])
    if values is None:
        return []
    if not isinstance(values, list):
        raise MarkdownFrontmatterError(f"Markdown frontmatter field `{key}` must be a list")
    return [str(value) for value in values]


def _title_from_filename(path: Path) -> str:
    name = path.name
    parts = name.split(".")
    if len(parts) >= 3:
        name = ".".join(parts[:-2])
    else:
        name = path.stem
    return name.replace("-", " ").replace("_", " ").title()
