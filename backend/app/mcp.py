from fastapi import Request

# 无状态 Streamable HTTP：保留工具、权限和确认流程；工具错误回滚后独立审计。
import os, json, re
from sqlalchemy import select
from fastapi.responses import JSONResponse, Response
from .common import *
from .models import AgentCall
from .database import transaction
from . import oauth, agent_tools, agent_operations as operations, agent_files


LATEST_PROTOCOL_VERSION = "2025-11-25"
SUPPORTED_PROTOCOL_VERSIONS = [
    "2025-11-25",
    "2025-06-18",
    "2025-03-26",
    "2024-11-05",
    "2024-10-07",
]


def schema(properties=None, required=None):
    return {
        "type": "object",
        "properties": properties or {},
        "additionalProperties": False,
        **({"required": required} if required else {}),
    }


def catalogue():
    business = []
    for tool in agent_tools.TOOLS.values():
        business.append(
            dict(
                name=tool["name"],
                description=tool["description"],
                inputSchema=tool["inputSchema"],
                annotations=dict(
                    readOnlyHint=tool["scope"] == "read",
                    destructiveHint=tool["destructive"],
                    idempotentHint=tool["scope"] != "read",
                    openWorldHint=False,
                ),
            )
        )
    protocols = {
        "state_get": schema(),
        "operation_get": schema(
            {"operationId": {"type": "string", "format": "uuid"}}, ["operationId"]
        ),
        "file_upload_request": schema(
            {"kind": {"type": "string", "enum": ["icon"]}}, ["kind"]
        ),
        "file_status": schema(
            {"fileId": {"type": "string", "format": "uuid"}}, ["fileId"]
        ),
        "icon_image": schema({"id": {"type": "string", "format": "uuid"}}, ["id"]),
        "connection_info": schema(),
        "connection_revoke": schema(),
    }
    for tool in agent_tools.CONTRACTS["protocolTools"]:
        business.append(
            dict(
                name=tool["name"],
                description=tool["description"],
                inputSchema=protocols[tool["name"]],
                annotations=dict(
                    readOnlyHint=tool["name"]
                    not in ("file_upload_request", "connection_revoke"),
                    destructiveHint=False,
                    idempotentHint=tool["name"]
                    not in ("file_upload_request", "connection_revoke"),
                    openWorldHint=False,
                ),
            )
        )
    return business


def protocol_call(s, g, name, p):
    if name in agent_tools.TOOLS:
        return operations.call(s, g, name, p)
    expected = {
        "operation_get": {"operationId"},
        "file_upload_request": {"kind"},
        "file_status": {"fileId"},
        "icon_image": {"id"},
    }
    if not isinstance(p, dict) or set(p) != expected.get(name, set()):
        fail("工具参数无效")
    if name == "state_get":
        return {"state": operations.state(s, g.userId)}
    if name == "operation_get":
        return operations.view(operations.get(s, g.userId, p["operationId"], g.id))
    if name == "connection_info":
        return dict(
            name=g.name,
            scopes=g.scopes,
            expiresAt=g.expiresAt,
            authorizationExpiresAt=g.refreshExpiresAt if g.clientId else g.expiresAt,
            resource=g.resource,
            permission="write"
            if "write" in g.scopes
            else "draft"
            if "draft" in g.scopes
            else "read",
            readHidden="hidden_read" in g.scopes,
            writeHidden="hidden_write" in g.scopes,
        )
    if name == "connection_revoke":
        g.revokedAt = now()
        return {"revoked": True}
    if name == "file_upload_request":
        if p["kind"] != "icon":
            fail("不支持的文件类型")
        if not {"draft", "write"}.intersection(g.scopes):
            fail("上传需要 draft 或 write 权限", 403)
        return agent_files.issue(s, g, "icon")
    if name == "file_status":
        return agent_files.status(g, p["fileId"])
    if name == "icon_image":
        return agent_files.issue(s, g, "image", p["id"])
    fail("未知工具")


async def handle(request: Request):
    resource, issuer, web = oauth.urls()
    origin = request.headers.get("origin")
    allowed = [v.strip() for v in os.getenv("MCP_ALLOWED_ORIGINS", web).split(",")]
    if (
        origin
        and origin not in allowed
        and not (
            "*" in allowed
            and __import__("app.config", fromlist=["flag"]).flag(
                "NETWORK_ALLOW_WILDCARD_ORIGINS", True
            )
        )
    ):
        return JSONResponse({"error": "Untrusted origin"}, 403)
    hosts = [
        v.strip().lower()
        for v in os.getenv("MCP_ALLOWED_HOSTS", "").split(",")
        if v.strip()
    ]
    if not hosts:
        from urllib.parse import urlsplit

        host = urlsplit(resource)
        hosts = [host.netloc.lower()]
        if __import__("app.config", fromlist=["flag"]).flag(
            "MCP_ALLOW_LOOPBACK_HOSTS", True
        ):
            hosts += [
                "localhost:"
                + str(host.port or (443 if host.scheme == "https" else 80)),
                "127.0.0.1:"
                + str(host.port or (443 if host.scheme == "https" else 80)),
            ]
    if "*" not in hosts and request.headers.get("host", "").lower() not in hosts:
        return JSONResponse({"error": "Untrusted host"}, 403)
    if request.method == "OPTIONS":
        return Response(
            status_code=204,
            headers={
                "Access-Control-Allow-Methods": "POST, GET, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "Authorization, Content-Type, Accept, MCP-Protocol-Version, MCP-Session-Id",
            },
        )
    try:
        with transaction() as s:
            g = oauth.bearer(s, request)
            grant_id = g.id
    except HTTPException as e:
        return JSONResponse(
            {"error": "invalid_token", "error_description": e.detail},
            e.status_code,
            headers={
                "WWW-Authenticate": 'Bearer resource_metadata="'
                + issuer
                + '/.well-known/oauth-protected-resource/mcp"'
            },
        )
    if request.method != "POST":
        return Response(status_code=405, headers={"Allow": "POST"})
    accept = request.headers.get("accept", "")
    if "application/json" not in accept or "text/event-stream" not in accept:
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32000,
                    "message": "Not Acceptable: Client must accept both application/json and text/event-stream",
                },
            },
            406,
        )
    if not request.headers.get("content-type", "").startswith("application/json"):
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32000,
                    "message": "Unsupported Media Type: Content-Type must be application/json",
                },
            },
            415,
        )
    protocol_version = request.headers.get("mcp-protocol-version")
    if protocol_version and protocol_version not in SUPPORTED_PROTOCOL_VERSIONS:
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32000, "message": "Unsupported protocol version"},
            },
            400,
        )
    try:
        raw = await request.body()
        if len(raw) > 8 * 1024 * 1024:
            return JSONResponse({"message": "文件不能超过 8 MB"}, 413)
        body = json.loads(raw)
    except ValueError:
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            },
            400,
        )
    if (
        not isinstance(body, dict)
        or body.get("jsonrpc") != "2.0"
        or not isinstance(body.get("method"), str)
    ):
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32600, "message": "Invalid Request"},
            },
            400,
        )
    id = body.get("id")
    method = body["method"]
    params = body.get("params", {})
    if id is None:
        return Response(status_code=202)
    if method == "initialize":
        result = dict(
            protocolVersion=params.get("protocolVersion")
            if params.get("protocolVersion") in SUPPORTED_PROTOCOL_VERSIONS
            else LATEST_PROTOCOL_VERSION,
            capabilities={"tools": {"listChanged": True}},
            serverInfo={"name": "WorthPath", "version": "1.0.0"},
            instructions="金额为十进制字符串；业务日期 UTC+8，时间戳 ISO UTC。先 state_get 再写入，所有写入要求幂等键。pending 返回网页入口，用户确认后用 operation_get 查询。只使用稳定 UUID；重名询问用户。",
        )
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": catalogue()}
    elif method == "tools/call":
        if not isinstance(params, dict) or not isinstance(params.get("name"), str):
            return JSONResponse(
                {
                    "jsonrpc": "2.0",
                    "id": id,
                    "error": {
                        "code": -32602,
                        "message": "Unknown tool or invalid parameters",
                    },
                }
            )
        # 与原 SDK 一致：未知工具作为 isError 工具结果返回，客户端仍可继续会话。
        name = params.get("name")
        status = "success"
        try:
            from starlette.concurrency import run_in_threadpool

            def invoke_tool():
                from sqlalchemy.exc import OperationalError
                import time

                for attempt in range(4):
                    try:
                        with transaction(
                            write=(
                                name in agent_tools.TOOLS
                                and agent_tools.TOOLS[name]["scope"] != "read"
                            )
                            or name == "connection_revoke"
                        ) as session:
                            g = oauth.grant(session, grant_id)
                            result = serializable(
                                protocol_call(
                                    session, g, name, params.get("arguments", {})
                                )
                            )
                            session.flush()
                            return result
                    except OperationalError as error:
                        if (
                            getattr(error.orig, "args", [None])[0] not in (1205, 1213)
                            or attempt == 3
                        ):
                            raise
                        time.sleep(0.02 * 2**attempt)

            value = await run_in_threadpool(invoke_tool)
            summary = (
                "操作状态："
                + (
                    "[object Object]"
                    if isinstance(value["status"], dict)
                    else str(value["status"])
                )
                if isinstance(value, dict) and value.get("status")
                else "查询或操作已完成"
            )
            result = {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {"summary": summary, "data": value},
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    }
                ],
                "structuredContent": {"data": value},
            }
        except Exception as e:
            status = "error"
            result = {
                "isError": True,
                "content": [
                    {
                        "type": "text",
                        "text": e.detail
                        if isinstance(e, HTTPException)
                        else "操作失败，未提交账目变更；请检查参数或稍后重试",
                    }
                ],
            }
        finally:
            try:
                with transaction() as s:
                    g = oauth.grant(s, grant_id)
                    s.add(
                        AgentCall(
                            userId=g.userId,
                            grantId=g.id,
                            tool=str(name)[:100],
                            status=status,
                        )
                    )
            except Exception:
                pass
    else:
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": id,
                "error": {"code": -32601, "message": "Method not found"},
            }
        )
    return JSONResponse({"jsonrpc": "2.0", "id": id, "result": result})
