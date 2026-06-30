"""Router extraction helpers for the api.main refactor."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter
from fastapi.routing import APIRoute

from api import app_legacy as legacy

RouteKey = tuple[str, tuple[str, ...]]
_ASSIGNED_ROUTE_KEYS: set[RouteKey] = set()


def _route_key(route: APIRoute) -> RouteKey:
    methods = tuple(sorted(route.methods or set()))
    return (route.path, methods)


def _iter_api_routes():
    for route in legacy.app.router.routes:
        if not isinstance(route, APIRoute):
            continue
        if not route.path.startswith("/api/"):
            continue
        yield route


def build_router(
    *,
    matcher: Callable[[str], bool],
    tags: list[str],
) -> APIRouter:
    router = APIRouter(tags=tags)
    for route in _iter_api_routes():
        if not matcher(route.path):
            continue
        key = _route_key(route)
        if key in _ASSIGNED_ROUTE_KEYS:
            raise RuntimeError(f"Route assigned more than once: {key}")
        _ASSIGNED_ROUTE_KEYS.add(key)
        router.add_api_route(
            route.path,
            route.endpoint,
            methods=sorted(route.methods or set()),
            name=route.name,
            response_model=route.response_model,
            status_code=route.status_code,
            tags=route.tags,
            dependencies=route.dependencies,
            summary=route.summary,
            description=route.description,
            response_description=route.response_description,
            responses=route.responses,
            deprecated=route.deprecated,
            operation_id=route.operation_id,
            response_model_include=route.response_model_include,
            response_model_exclude=route.response_model_exclude,
            response_model_by_alias=route.response_model_by_alias,
            response_model_exclude_unset=route.response_model_exclude_unset,
            response_model_exclude_defaults=route.response_model_exclude_defaults,
            response_model_exclude_none=route.response_model_exclude_none,
            include_in_schema=route.include_in_schema,
            response_class=route.response_class,
            callbacks=route.callbacks,
            openapi_extra=route.openapi_extra,
            generate_unique_id_function=route.generate_unique_id_function,
        )
    return router


def assert_all_routes_assigned() -> None:
    expected = {_route_key(route) for route in _iter_api_routes()}
    missing = sorted(expected - _ASSIGNED_ROUTE_KEYS)
    if missing:
        raise RuntimeError(f"Unassigned API routes: {missing}")
