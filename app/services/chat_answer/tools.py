"""Chat answer agent tools."""

from pydantic_ai import ModelRetry
from app.services.chat_answer.constants import CHAT_ANSWER_NOT_FOUND_MESSAGE
from app.services.chat_answer.dependencies import ChatAgentDeps
from app.services.chat_answer.schemas import ChatAgentOutput


async def search_company_knowledge_tool(deps: ChatAgentDeps, *, query: str) -> str:
    """Run ACL-aware hybrid search for company-specific questions and return grounded excerpts."""

    user = deps.identity_resolver.resolve_user(deps.user_email)
    if user is None:
        return CHAT_ANSWER_NOT_FOUND_MESSAGE

    results = await deps.hybrid_search_service.search(
        query=query,
        user_email=user.email,
        user_groups=user.groups,
    )
    if not results:
        return CHAT_ANSWER_NOT_FOUND_MESSAGE

    excerpts: list[str] = []
    for result in results:
        source_id = result.payload.source_id.strip()
        deps.remember_retrieved_source_id(source_id)
        excerpts.append(f"Source ID: {source_id}\nContent:\n{result.payload.text.strip()}")

    return "\n\n---\n\n".join(excerpts)


def validate_citation_verified_output_tool(output: ChatAgentOutput, deps: ChatAgentDeps) -> ChatAgentOutput:
    """Validate that RAG answers cite only source ids returned by the search tool."""

    def _normalized_unique(values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))

    cited_source_ids = _normalized_unique(output.sources)

    if not output.used_rag:
        if cited_source_ids:
            raise ModelRetry("Do not include sources when `used_rag` is false.")
        return output

    if output.answer.strip() == CHAT_ANSWER_NOT_FOUND_MESSAGE:
        return output

    retrieved_source_ids = _normalized_unique(deps.retrieved_source_ids)
    if not retrieved_source_ids:
        raise ModelRetry(
            "No company knowledge sources were retrieved. If the retrieved content is insufficient, return the "
            f"not-found answer exactly: {CHAT_ANSWER_NOT_FOUND_MESSAGE!r}."
        )

    if not cited_source_ids:
        raise ModelRetry("RAG answers must include at least one source returned by the search tool.")

    unknown_source_ids = [source_id for source_id in cited_source_ids if source_id not in retrieved_source_ids]
    if unknown_source_ids:
        valid_sources = ", ".join(retrieved_source_ids)
        invalid_sources = ", ".join(unknown_source_ids)
        raise ModelRetry(
            f"Source ids not returned by the search tool: {invalid_sources}. Cite only these source ids: "
            f"{valid_sources}."
        )

    return output
