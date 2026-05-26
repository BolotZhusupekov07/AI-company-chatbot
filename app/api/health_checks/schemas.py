from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

type LivenessStatus = Literal["UP", "DOWN"]
type ReadinessStatus = Literal["READY", "NOT_READY"]


class HealthCheckLiveResponse(BaseModel):
    """Liveness response."""

    version: str
    status: LivenessStatus
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class HealthCheckReadyResponse(BaseModel):
    """Readiness response."""

    version: str
    status: ReadinessStatus
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
