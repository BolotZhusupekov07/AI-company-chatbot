"""Core enums."""

from enum import StrEnum


class Language(StrEnum):
    """Supported chat message languages."""

    EN = "EN"
    RU = "RU"
    UK = "UK"


class Role(StrEnum):
    """Chat message author roles."""

    USER = "USER"
    AGENT = "AGENT"
