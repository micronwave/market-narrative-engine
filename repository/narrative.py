"""Narrative domain repository facade."""

from __future__ import annotations

from ._legacy import LegacySqliteRepository


class NarrativeRepository:
    def __init__(self, core: LegacySqliteRepository) -> None:
        self._core = core

    def get_narrative(self, narrative_id: str):
        return self._core.get_narrative(narrative_id)

    def get_all_active_narratives(
        self,
        *,
        limit: int = 0,
        offset: int = 0,
        stage: str | None = None,
        topic: str | None = None,
    ):
        return self._core.get_all_active_narratives(
            limit=limit,
            offset=offset,
            stage=stage,
            topic=topic,
        )

    def insert_narrative(self, narrative: dict) -> None:
        self._core.insert_narrative(narrative)

    def update_narrative(self, narrative_id: str, updates: dict) -> None:
        self._core.update_narrative(narrative_id, updates)

    def __getattr__(self, name: str):
        return getattr(self._core, name)

