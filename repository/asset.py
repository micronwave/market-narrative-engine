"""Asset domain repository facade."""

from __future__ import annotations

from ._legacy import LegacySqliteRepository


class AssetRepository:
    def __init__(self, core: LegacySqliteRepository) -> None:
        self._core = core

    def get_all_assets(self):
        return self._core.get_all_assets()

    def insert_asset(self, asset_data: dict) -> int:
        return self._core.insert_asset(asset_data)

    def get_asset_by_ticker(self, ticker: str):
        return self._core.get_asset_by_ticker(ticker)

    def __getattr__(self, name: str):
        return getattr(self._core, name)

