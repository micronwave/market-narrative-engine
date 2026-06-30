from dataclasses import dataclass, field
import asyncio
import threading
from typing import Any


@dataclass
class AppState:
    """Mutable API runtime state shared across handlers/background tasks."""

    sse_connections: int = 0
    sse_per_user: dict[str, int] = field(default_factory=dict)
    latest_ticker_payload: dict[str, Any] = field(
        default_factory=lambda: {"type": "ticker-update", "items": []}
    )
    login_attempts: dict[str, list[float]] = field(default_factory=dict)
    login_attempts_lock: threading.Lock = field(default_factory=threading.Lock)
    sse_lock: asyncio.Lock | None = None
