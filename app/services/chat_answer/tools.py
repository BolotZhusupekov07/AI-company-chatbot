"""Chat answer agent tools."""

from app.services.chat_answer.constants import CHAT_ANSWER_NOT_FOUND_MESSAGE
from app.services.chat_answer.dependencies import ChatAgentDeps


async def search_company_knowledge_tool(deps: ChatAgentDeps, *, query: str) -> str:
    """Run ACL-aware hybrid search for company-specific questions and return grounded answer"""

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

    return f'Content: {results[0].payload.text}\n\nSource ID: {results[0].payload.source_id}'
