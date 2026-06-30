"""Narrative Engine API app factory with domain router registration."""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException

from api import app_legacy as _legacy
from api import state  # noqa: F401
from api.app_legacy import *  # noqa: F403
from api.routers import health, narratives, securities, signals

# Preserve imports used by legacy tests and scripts that expect symbols on api.main.
STUB_AUTH_TOKEN = _legacy.STUB_AUTH_TOKEN
_validate_symbol = _legacy._validate_symbol
_csv_safe = _legacy._csv_safe
_safe_json_list = _legacy._safe_json_list
_securities_lock = _legacy._securities_lock


def _get_jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET_KEY", "")
    if not secret or len(secret) < 32:
        raise HTTPException(status_code=500, detail="JWT_SECRET_KEY must be at least 32 characters")
    return secret

_legacy_get_repo = _legacy.get_repo


def get_repo():
    return _legacy_get_repo()


_legacy.get_repo = lambda: get_repo()


def _copy_middleware(app: FastAPI) -> None:
    for middleware in reversed(_legacy.app.user_middleware):
        app.add_middleware(middleware.cls, **middleware.kwargs)


def _copy_exception_handlers(app: FastAPI) -> None:
    app.exception_handlers.update(_legacy.app.exception_handlers)


def _copy_state(app: FastAPI) -> None:
    for key, value in vars(_legacy.app.state).items():
        setattr(app.state, key, value)


def _copy_event_handlers(app: FastAPI) -> None:
    for startup_handler in _legacy.app.router.on_startup:
        app.router.add_event_handler("startup", startup_handler)
    for shutdown_handler in _legacy.app.router.on_shutdown:
        app.router.add_event_handler("shutdown", shutdown_handler)


def create_app() -> FastAPI:
    app = FastAPI(
        title=_legacy.app.title,
        version=_legacy.app.version,
        docs_url=_legacy.app.docs_url,
        redoc_url=_legacy.app.redoc_url,
        openapi_url=_legacy.app.openapi_url,
    )

    _copy_middleware(app)
    _copy_exception_handlers(app)
    _copy_state(app)

    app.include_router(narratives.router)
    app.include_router(securities.router)
    app.include_router(signals.router)
    app.include_router(health.router)

    _copy_event_handlers(app)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
