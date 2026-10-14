# MCP 与 HTTP 复用业务服务；分页、金额和隐藏权限遵守相同规则。
from types import SimpleNamespace
from copy import deepcopy
from jsonschema import Draft202012Validator, validators, FormatChecker
from fastapi.responses import JSONResponse
from .common import *
from . import oauth, portfolio, transfers, queries
from .mcp_contracts import CONTRACTS

TOOLS = {t["name"]: t for t in CONTRACTS["tools"]}


def default_properties(validator, properties, instance, schema):
    if isinstance(instance, dict):
        for key, subschema in properties.items():
            if "default" in subschema:
                instance.setdefault(key, deepcopy(subschema["default"]))
    yield from Draft202012Validator.VALIDATORS["properties"](
        validator, properties, instance, schema
    )


Validator = validators.extend(Draft202012Validator, {"properties": default_properties})


def validate(name, params):
    if name not in TOOLS:
        fail("未知工具")
    if not isinstance(params, dict):
        fail("工具参数必须为对象")
    params = deepcopy(params)
    errors = list(
        Validator(
            TOOLS[name]["inputSchema"], format_checker=FormatChecker()
        ).iter_errors(params)
    )
    if errors:
        fail("；".join(".".join(map(str, e.path)) + ": " + e.message for e in errors))
    return params


def page(items, p):
    offset = p.get("offset", 0)
    limit = p.get("limit", 50)
    return dict(
        items=items[offset : offset + limit],
        total=len(items),
        nextOffset=offset + limit if offset + limit < len(items) else None,
    )


ROUTES = {
    "position_get": ("GET", "/api/positions/{id}"),
    "position_create": ("POST", "/api/positions"),
    "position_update": ("PATCH", "/api/positions/{id}"),
    "balance_record": ("POST", "/api/positions/{id}/revisions"),
    "history_update": ("PUT", "/api/positions/{id}/revisions/{revisionId}"),
    "history_delete": ("DELETE", "/api/positions/{id}/revisions/{revisionId}"),
    "debt_links_set": ("PUT", "/api/positions/{id}/links"),
    "trend_get": ("GET", "/api/trend"),
    "movements_list": ("GET", "/api/transfers"),
    "movement_by_revision": ("GET", "/api/transfers/revision/{revisionId}"),
    "movement_create": ("POST", "/api/transfers"),
    "movement_update": ("PUT", "/api/transfers/{id}"),
    "movement_delete": ("DELETE", "/api/transfers/{id}"),
    "calendar_month": ("GET", "/api/calendar"),
    "calendar_day": ("GET", "/api/calendar/day"),
    "schedules_list": ("GET", "/api/schedules"),
    "schedule_create": ("POST", "/api/schedules"),
    "schedule_update": ("PUT", "/api/schedules/{id}"),
    "schedule_toggle": ("PATCH", "/api/schedules/{id}"),
    "schedule_delete": ("DELETE", "/api/schedules/{id}"),
    "schedules_run": ("POST", "/api/schedules/run"),
    "settings_get": ("GET", "/api/settings"),
    "settings_update": ("PATCH", "/api/settings"),
    "metal_holding_create": ("POST", "/api/metals/holdings"),
    "metals_prices": ("GET", "/api/metals"),
    "metal_configure": ("PUT", "/api/metals/{id}"),
    "metal_value": ("POST", "/api/metals/{id}/value"),
    "icons_list": ("GET", "/api/icons"),
}


def run(s, g, name, p):
    r = oauth.context(s, g, TOOLS[name]["scope"] != "read")
    if name == "positions_list":
        rows = portfolio.list_positions(s, r, p.get("kind"))
        rows = [
            v
            for v in rows
            if (not p.get("q") or p["q"] in v["name"])
            and all(
                k not in p or p[k] == v[k]
                for k in ("archived", "side", "currency", "groupName")
            )
        ]
        rows.sort(
            key=lambda v: (v["name"] if p.get("order") == "name" else "", v["id"])
        )
        return page(rows, p)
    if name == "overview_get":
        v = portfolio.overview(s, r)
        return {**v, **page(v["items"], p)}
    if name == "history_list":
        return queries.history(s, r, p)
    if name == "icon_publish":
        from .agent_files import publish

        return publish(s, g, p)
    if name == "schedules_run":
        from .schedules import run

        return run(s, r, True)
    from .main import dispatch

    method, path = ROUTES[name]
    path_params = {key: p[key] for key in ("id", "revisionId") if key in p}
    query = {
        key: str(value).lower() if isinstance(value, bool) else str(value)
        for key, value in p.items()
        if key not in ("id", "revisionId", "offset", "data")
    }
    if name in ("calendar_day", "schedules_list"):
        query = {k: v for k, v in query.items() if k not in ("limit", "offset")}
    if name == "settings_get":
        query = {"rates": "true"}
    body = p.get("data", p)
    if name == "debt_links_set":
        body = {"targetIds": p["targetIds"]}
    if name == "schedule_toggle":
        body = {"enabled": p["enabled"]}
    req = SimpleNamespace(
        method=method,
        path_params=path_params,
        query_params=query,
        scope={"route": SimpleNamespace(path=path)},
        cookies={},
    )
    value = dispatch(s, r, req, JSONResponse(None), body)
    if name in ("calendar_day", "schedules_list"):
        if isinstance(value, list):
            return page(value, p)
        return {**value, **page(value["items"], p)}
    return value
