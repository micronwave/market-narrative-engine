"""Load the legacy monolithic repository module from repository.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_legacy_module() -> ModuleType:
    root = Path(__file__).resolve().parent.parent
    legacy_path = root / "repository.py"
    spec = importlib.util.spec_from_file_location("repository_legacy", legacy_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load legacy repository module: {legacy_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_legacy = _load_legacy_module()

Repository = _legacy.Repository
LegacySqliteRepository = _legacy.SqliteRepository

