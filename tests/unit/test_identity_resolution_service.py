from pathlib import Path

import pytest

from app.services.identity_resolution_service import IdentityMetadataError, LocalIdentityResolver, ResolvedIdentity


def test_resolve_user_returns_identity_from_sample_metadata() -> None:
    resolver = LocalIdentityResolver(Path("sample_company_kb/metadata"))

    identity = resolver.resolve_user("aida.mamatova@ala-too-digital.kg")

    assert identity == ResolvedIdentity(
        email="aida.mamatova@ala-too-digital.kg",
        full_name="Aida Mamatova",
        location="Bishkek, Kyrgyzstan",
        department="Engineering",
        groups=["employees", "engineering"],
    )


def test_resolve_user_normalizes_email_before_lookup() -> None:
    resolver = LocalIdentityResolver(Path("sample_company_kb/metadata"))

    identity = resolver.resolve_user("  AIDA.MAMATOVA@ALA-TOO-DIGITAL.KG  ")

    assert identity is not None
    assert identity.email == "aida.mamatova@ala-too-digital.kg"


def test_resolve_user_returns_none_for_unknown_email() -> None:
    resolver = LocalIdentityResolver(Path("sample_company_kb/metadata"))

    assert resolver.resolve_user("unknown@ala-too-digital.kg") is None


def test_resolve_user_allows_known_user_with_no_groups(tmp_path: Path) -> None:
    metadata_path = _write_metadata(
        tmp_path,
        users_yaml="""
users:
  guest@example.com:
    full_name: Guest User
    location: Bishkek, Kyrgyzstan
    department: Visitor
    groups: []
""",
        groups_yaml="""
groups:
  employees:
    description: All full-time employees.
""",
    )
    resolver = LocalIdentityResolver(metadata_path)

    identity = resolver.resolve_user("guest@example.com")

    assert identity == ResolvedIdentity(
        email="guest@example.com",
        full_name="Guest User",
        location="Bishkek, Kyrgyzstan",
        department="Visitor",
        groups=[],
    )


def test_resolver_rejects_user_group_missing_from_groups_metadata(tmp_path: Path) -> None:
    metadata_path = _write_metadata(
        tmp_path,
        users_yaml="""
users:
  aida@example.com:
    full_name: Aida
    location: Bishkek
    department: Engineering
    groups:
      - engineering
""",
        groups_yaml="""
groups:
  employees:
    description: All full-time employees.
""",
    )

    with pytest.raises(IdentityMetadataError, match="unknown group"):
        LocalIdentityResolver(metadata_path)


def _write_metadata(tmp_path: Path, *, users_yaml: str, groups_yaml: str) -> Path:
    metadata_path = tmp_path / "metadata"
    metadata_path.mkdir()
    (metadata_path / "users.yaml").write_text(users_yaml.strip() + "\n", encoding="utf-8")
    (metadata_path / "groups.yaml").write_text(groups_yaml.strip() + "\n", encoding="utf-8")
    return metadata_path
