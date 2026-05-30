"""Chat answer agent dependencies."""

from pydantic import BaseModel, ConfigDict, SkipValidation

from app.services.hybrid_search_service import HybridSearchService
from app.services.identity_resolution_service import LocalIdentityResolver


class ChatAgentDeps(BaseModel):
    """Dependencies available to chat agent tools."""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    user_email: str
    identity_resolver: SkipValidation[LocalIdentityResolver]
    hybrid_search_service: SkipValidation[HybridSearchService]
