"""LLM audit domain repository facade."""

from __future__ import annotations

from ._legacy import LegacySqliteRepository


class LlmAuditRepository:
    def __init__(self, core: LegacySqliteRepository) -> None:
        self._core = core

    def __getattr__(self, name: str):
        return getattr(self._core, name)

