"""Chat answer agent tools."""

from app.infrastructure.vector_store.qdrant.repository import build_acl_filter
from app.services.chat_answer.constants import CHAT_ANSWER_NOT_FOUND_MESSAGE, CHAT_ANSWER_SCORE_THRESHOLD
from app.services.chat_answer.dependencies import ChatAgentDeps


def search_company_knowledge_tool(deps: ChatAgentDeps, *, query: str) -> str:
    """Run ACL-aware dense search and return the first result text."""

    user = deps.identity_resolver.resolve_user(deps.user_email)
    if user is None:
        return CHAT_ANSWER_NOT_FOUND_MESSAGE

    query_vector = deps.embedding_provider.embed_query(query)
    results = deps.qdrant_repo.search_dense(
        query_vector,
        limit=1,
        query_filter=build_acl_filter(user.email, user.groups),
        score_threshold=CHAT_ANSWER_SCORE_THRESHOLD,
    )
    if not results:
        return CHAT_ANSWER_NOT_FOUND_MESSAGE

    return results[0].payload.text
