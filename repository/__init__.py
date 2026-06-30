"""Multi-domain repository package with backward-compatible facade."""

from __future__ import annotations

from ._legacy import LegacySqliteRepository
from .asset import AssetRepository
from .base import Repository
from .document import DocumentRepository
from .llm_audit import LlmAuditRepository
from .narrative import NarrativeRepository


class SqliteRepository(LegacySqliteRepository):
    """Unified repository facade that exposes domain repositories."""

    def __init__(self, db_path: str) -> None:
        super().__init__(db_path)
        self.narrative = NarrativeRepository(self)
        self.document = DocumentRepository(self)
        self.asset = AssetRepository(self)
        self.llm_audit = LlmAuditRepository(self)


def get_repo(db_path: str | None = None) -> SqliteRepository:
    if db_path is None:
        from settings import settings

        db_path = settings.DB_PATH
    return SqliteRepository(db_path)


__all__ = [
    "Repository",
    "SqliteRepository",
    "NarrativeRepository",
    "DocumentRepository",
    "AssetRepository",
    "LlmAuditRepository",
    "get_repo",
]
