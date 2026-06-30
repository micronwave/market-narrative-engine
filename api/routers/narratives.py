"""Narrative-focused endpoints."""

from api.routers._shared import build_router

router = build_router(
    matcher=lambda path: path.startswith("/api/narratives")
    and path
    not in {"/api/narratives/{narrative_id}/export", "/api/narratives/{narrative_id}/analyze"}
    or path in {"/api/constellation", "/api/activity"},
    tags=["narratives"],
)
