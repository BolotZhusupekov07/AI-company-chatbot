from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class IdentityMetadataError(ValueError):
    """Raised when local identity metadata is malformed."""


@dataclass(frozen=True)
class ResolvedIdentity:
    """Trusted local identity resolved from sample company metadata."""

    email: str
    full_name: str
    location: str
    department: str
    groups: list[str]


class LocalIdentityResolver:
    """Resolves trusted user emails against local YAML metadata."""

    def __init__(self, metadata_path: Path | str = Path("sample_company_kb/metadata")) -> None:
        self._metadata_path = Path(metadata_path)
        self._groups = _load_group_ids(self._metadata_path / "groups.yaml")
        self._users = _load_users(self._metadata_path / "users.yaml", self._groups)

    def resolve_user(self, email: str) -> ResolvedIdentity | None:
        """Resolve a trusted email into local user identity metadata."""
        normalized_email = _normalize_email(email)
        if not normalized_email:
            return None

        user = self._users.get(normalized_email)
        if user is None:
            return None

        return ResolvedIdentity(
            email=normalized_email,
            full_name=user.full_name,
            location=user.location,
            department=user.department,
            groups=list(user.groups),
        )


@dataclass(frozen=True)
class _LocalUser:
    full_name: str
    location: str
    department: str
    groups: list[str]


def _load_group_ids(path: Path) -> set[str]:
    raw_groups = _load_mapping(path, "groups")
    return {_normalize_group_id(group_id) for group_id in raw_groups}


def _load_users(path: Path, known_groups: set[str]) -> dict[str, _LocalUser]:
    raw_users = _load_mapping(path, "users")
    users: dict[str, _LocalUser] = {}

    for raw_email, raw_user in raw_users.items():
        email = _normalize_email(str(raw_email))
        if not email:
            raise IdentityMetadataError(f"User email must not be blank: {path}")
        if not isinstance(raw_user, dict):
            raise IdentityMetadataError(f"User metadata must be a mapping: {email}")

        groups = _get_string_list(raw_user, "groups")
        unknown_groups = sorted(group for group in groups if group not in known_groups)
        if unknown_groups:
            raise IdentityMetadataError(f"User {email} references unknown group(s): {', '.join(unknown_groups)}")

        users[email] = _LocalUser(
            full_name=_get_required_string(raw_user, "full_name", email),
            location=_get_required_string(raw_user, "location", email),
            department=_get_required_string(raw_user, "department", email),
            groups=groups,
        )

    return users


def _load_mapping(path: Path, key: str) -> dict[str, Any]:
    try:
        parsed = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError as error:
        raise IdentityMetadataError(f"Identity metadata file is missing: {path}") from error
    if not isinstance(parsed, dict):
        raise IdentityMetadataError(f"Identity metadata file must contain a mapping: {path}")

    values = parsed.get(key)
    if not isinstance(values, dict):
        raise IdentityMetadataError(f"Identity metadata field `{key}` must be a mapping: {path}")

    return values


def _get_required_string(values: dict[str, Any], key: str, email: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value.strip():
        raise IdentityMetadataError(f"User {email} field `{key}` must be a non-blank string")
    return value.strip()


def _get_string_list(values: dict[str, Any], key: str) -> list[str]:
    raw_values = values.get(key, [])
    if raw_values is None:
        return []
    if not isinstance(raw_values, list):
        raise IdentityMetadataError(f"User field `{key}` must be a list")
    return [_normalize_group_id(value) for value in raw_values if _normalize_group_id(value)]


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _normalize_group_id(group_id: Any) -> str:
    return str(group_id).strip()
