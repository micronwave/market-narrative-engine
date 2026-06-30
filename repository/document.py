"""Document domain repository facade."""

from __future__ import annotations

from ._legacy import LegacySqliteRepository


class DocumentRepository:
    def __init__(self, core: LegacySqliteRepository) -> None:
        self._core = core

    def get_candidate_buffer(self, status: str = "pending"):
        return self._core.get_candidate_buffer(status=status)

    def insert_candidate(self, candidate: dict) -> None:
        self._core.insert_candidate(candidate)

    def update_candidate_status(
        self, doc_id: str, status: str, narrative_id_assigned: str | None = None
    ) -> None:
        self._core.update_candidate_status(
            doc_id=doc_id,
            status=status,
            narrative_id_assigned=narrative_id_assigned,
        )

    def __getattr__(self, name: str):
        return getattr(self._core, name)

