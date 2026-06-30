"""Signals, analytics, and manipulation endpoints."""

from api.routers._shared import build_router

router = build_router(
    matcher=lambda path: path.startswith("/api/signals")
    or path.startswith("/api/manipulation")
    or path.startswith("/api/correlations")
    or path.startswith("/api/coordination")
    or path.startswith("/api/analytics"),
    tags=["signals"],
)
