"""Health, auth, and system endpoints."""

from api.routers._shared import build_router

router = build_router(
    matcher=lambda path: path.startswith("/api/health")
    or path.startswith("/api/websocket/status")
    or path.startswith("/api/stream")
    or path.startswith("/api/pipeline/buffer")
    or path.startswith("/api/dashboard/layout")
    or path.startswith("/api/admin/narrative-quality")
    or path.startswith("/api/auth"),
    tags=["health"],
)
