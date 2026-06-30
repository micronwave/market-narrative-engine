"""Security and market data endpoints."""

from api.routers._shared import build_router

router = build_router(
    matcher=lambda path: path.startswith("/api/ticker")
    or path.startswith("/api/securities")
    or path.startswith("/api/stocks")
    or path.startswith("/api/asset-classes")
    or path.startswith("/api/brief")
    or path.startswith("/api/earnings")
    or path.startswith("/api/sentiment")
    or path.startswith("/api/social"),
    tags=["securities"],
)
