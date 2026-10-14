# HTTP 入口：统一安全校验和错误格式，接口业务同时供 MCP 复用。
"""FastAPI HTTP entry; business services are also consumed by MCP."""

import os, json, re
from pathlib import Path
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, OperationalError
from starlette.middleware.cors import CORSMiddleware
from .config import ROOT, flag
from .database import transaction
from .common import *
from .models import *
from . import auth, portfolio, queries, transfers
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(application):
    import asyncio
    from .quotes import hourly
    from .maintenance import prune, run as maintain

    production = os.getenv("NODE_ENV") == "production"
    if not os.getenv("DATABASE_URL") or not os.getenv("WEB_ORIGIN"):
        raise RuntimeError("Missing local environment configuration")
    if "*" in os.getenv("WEB_ORIGIN", "").split(",") and not flag(
        "NETWORK_ALLOW_WILDCARD_ORIGINS", not production
    ):
        raise RuntimeError("Explicit web origin required")
    if flag("NETWORK_REQUIRE_SECURE_COOKIE", production) and not flag(
        "COOKIE_SECURE", production
    ):
        raise RuntimeError("Secure cookies required")
    same_site = os.getenv("COOKIE_SAME_SITE", "strict")
    if same_site not in ("strict", "lax", "none") or (
        same_site == "none" and not flag("COOKIE_SECURE", production)
    ):
        raise RuntimeError("Invalid cookie policy")
    with transaction(write=True) as session:
        auth.bootstrap(session)
    prune()
    task = asyncio.create_task(hourly())
    cleaner = asyncio.create_task(maintain())
    try:
        yield
    finally:
        task.cancel()
        cleaner.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        try:
            await cleaner
        except asyncio.CancelledError:
            pass
        prune(True)


app = FastAPI(
    lifespan=lifespan,
    title="WorthPath",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)
origins = [v.strip() for v in os.getenv("WEB_ORIGIN", "").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def allowed_origin(origin):
    try:
        from urllib.parse import urlsplit

        u = urlsplit(origin or "")
        if u.scheme not in ("http", "https") or u.path or u.query or u.fragment:
            return False
        return origin in origins or (
            "*" in origins
            and flag(
                "NETWORK_ALLOW_WILDCARD_ORIGINS", os.getenv("NODE_ENV") != "production"
            )
        )
    except ValueError:
        return False


@app.middleware("http")
async def security(request, call_next):
    hosts = [v.strip().lower() for v in os.getenv("API_ALLOWED_HOSTS", "*").split(",")]
    if "*" not in hosts and request.headers.get("host", "").lower() not in hosts:
        return JSONResponse({"message": "请求 Host 不受信任"}, 403)
    if (
        request.url.path.startswith("/api")
        and not request.url.path.startswith("/api/agent/files/")
        and request.method not in ("GET", "HEAD", "OPTIONS")
        and not allowed_origin(request.headers.get("origin"))
    ):
        return JSONResponse({"message": "请求来源不受信任"}, 403)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "no-referrer"
    if flag("NETWORK_HSTS", os.getenv("NODE_ENV") == "production"):
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
    return response


@app.exception_handler(HTTPException)
async def http_error(request, e):
    return JSONResponse({"message": e.detail}, e.status_code, headers=e.headers)


async def validation_error(request, e):
    message = "；".join(
        ".".join(str(v) for v in err["loc"])
        + ": "
        + err["msg"].removeprefix("Value error, ")
        for err in e.errors()
    )
    return JSONResponse({"message": message}, 400)


app.add_exception_handler(ValidationError, validation_error)
app.add_exception_handler(RequestValidationError, validation_error)


@app.exception_handler(IntegrityError)
async def integrity_error(request, e):
    return JSONResponse({"message": "数据已存在或已被其他操作更新，请刷新后重试"}, 409)


@app.exception_handler(Exception)
async def safe_error(request, e):
    return JSONResponse({"message": "服务暂时不可用，请稍后重试"}, 500)


def dispatch(s, r, request, response, body):
    p = request.path_params
    q = dict(request.query_params)
    method = request.method
    path = request.scope["route"].path
    if path == "/api/health":
        return {"status": "ok"}
    if path == "/api/auth/register":
        fail("公开注册已关闭，请联系管理员创建账号", 403)
    if path == "/api/auth/login":
        return auth.login(s, body, request, response)
    if path == "/api/auth/logout":
        return auth.logout(s, request, response)
    if path == "/api/auth/me":
        return auth.profile(s, r)
    if path == "/api/auth/credentials":
        return auth.change_credentials(s, r, body, request, response)
    if path == "/api/auth/reveal":
        return auth.reveal(s, r, body, request)
    if path == "/api/auth/lock":
        s.get(Session, r.sessionId).revealUntil = None
        return {"ok": True}
    if path == "/api/auth/activity":
        s.get(Session, r.sessionId).lastActivity = now()
        return {"ok": True}
    if path == "/api/positions":
        return (
            portfolio.create(s, r, body)
            if method == "POST"
            else portfolio.list_positions(s, r, q.get("kind"))
        )
    if path == "/api/positions/{id}":
        if method == "GET":
            return portfolio.detail(s, r, p["id"])
        if method == "PATCH":
            return portfolio.edit(s, r, p["id"], body)
        return portfolio.remove(s, r, p["id"], body)
    if path == "/api/history":
        return queries.history(s, r, q)
    if path == "/api/positions/{id}/history":
        queries.own(s, r, p["id"])
        return queries.history(s, r, {**q, "positionId": p["id"]})
    if path == "/api/overview":
        return portfolio.overview(s, r)
    if path == "/api/trend":
        return portfolio.trend_data(s, r, q)
    if path == "/api/positions/{id}/inclusion":
        return portfolio.quick_meta(s, r, p["id"], body)
    if path == "/api/positions/{id}/repayment-mark":
        return portfolio.quick_meta(s, r, p["id"], body, True)
    if path == "/api/positions/{id}/deletion":
        return portfolio.deletion(s, r, p["id"])
    if path == "/api/positions/{id}/links":
        return portfolio.links(s, r, p["id"], body)
    if path == "/api/positions/{id}/revisions":
        return portfolio.revise(s, r, p["id"], body)
    if path == "/api/positions/{id}/revisions/{revisionId}":
        if method == "PUT":
            return portfolio.revise(s, r, p["id"], body, p["revisionId"])
        return portfolio.delete_revision(s, r, p["id"], p["revisionId"])
    if path == "/api/transfers":
        return (
            transfers.execute(s, r, body)
            if method == "POST"
            else transfers.list_transfers(s, r, q)
        )
    if path == "/api/transfers/revision/{revisionId}":
        t = s.scalar(transfers.visible_transfer(s, r, revision_id=p["revisionId"]))
        if not t:
            fail("资金往来记录不存在", 404)
        return transfers.describe(s, t)
    if path == "/api/transfers/{id}":
        return transfers.change(s, r, p["id"], body if method == "PUT" else None)
    for module in extensions:
        result = module.dispatch(s, r, request, response, body)
        if result is not NotImplemented:
            return result
    fail("接口不存在", 404)


from . import (
    settings,
    calendar,
    schedules,
    admin,
    icons,
    metals,
    backup_restore,
    agent_management,
)

extensions = [
    settings,
    calendar,
    schedules,
    admin,
    icons,
    metals,
    backup_restore,
    agent_management,
]


def endpoint_factory():
    async def endpoint(request: Request):
        body = {}
        if request.method not in ("GET", "HEAD", "OPTIONS") and request.headers.get(
            "content-type", ""
        ).startswith("multipart/form-data"):
            maximum = (
                512 * 1024 * 1024
                if request.url.path == "/api/backup/upload"
                else 2 * 1024 * 1024
            )
            form = await request.form(
                max_files=1,
                max_fields=0 if request.url.path == "/api/backup/upload" else 3,
                max_part_size=maximum,
            )
            body = {k: v for k, v in form.items() if k != "file"}
            file = form.get("file")
            if file:
                if maximum > 2 * 1024 * 1024:
                    import tempfile

                    folder = ROOT / "runtime/imports"
                    folder.mkdir(parents=True, exist_ok=True)
                    target = folder / (str(__import__("uuid").uuid4()) + ".zip")
                    size = 0
                    with target.open("wb") as out:
                        while chunk := await file.read(1024 * 1024):
                            size += len(chunk)
                            if size > maximum:
                                target.unlink(missing_ok=True)
                                fail("文件过大", 413)
                            out.write(chunk)
                    body["_filePath"] = target
                else:
                    raw = await file.read(maximum + 1)
                    if len(raw) > maximum:
                        fail("图标不能超过 2 MB", 413)
                    body["_file"] = raw
                await file.close()
        elif request.method not in ("GET", "HEAD", "OPTIONS"):
            raw = await request.body()
            if len(raw) > 8 * 1024 * 1024:
                fail("文件不能超过 8 MB", 413)
            if raw:
                try:
                    body = json.loads(raw)
                except (ValueError, UnicodeDecodeError):
                    fail("JSON 文件或请求格式无效")
        response = JSONResponse(
            None, status_code=201 if request.method == "POST" else 200
        )
        # 同步 SQLAlchemy 和密码哈希在工作线程执行，避免网络刷新阻塞事件循环。
        from starlette.concurrency import run_in_threadpool

        def invoke():
            try:
                with transaction(
                    write=request.method not in ("GET", "HEAD", "OPTIONS")
                    or request.url.path == "/api/backup"
                ) as session:
                    public = request.url.path in (
                        "/api/health",
                        "/api/auth/register",
                        "/api/auth/login",
                    )
                    principal = None if public else auth.context(session, request)
                    if principal:
                        request.state.user_id = principal.userId
                    business_request = request
                    if request.method == "HEAD":
                        # Express 原 GET 控制器同时接受 HEAD；复制业务视图，保留原始 HTTP 方法供服务器省略响应体。
                        business_request = Request({**request.scope, "method": "GET"})
                    value = dispatch(
                        session, principal, business_request, response, body
                    )
                    session.flush()
                    return (
                        serializable(value)
                        if not isinstance(value, Response)
                        else value
                    )
            except Exception:
                temporary = body.get("_filePath") if isinstance(body, dict) else None
                if temporary:
                    temporary.unlink(missing_ok=True)
                raise

        for attempt in range(4):
            try:
                result = await run_in_threadpool(invoke)
                if isinstance(result, Response):
                    return result
                response.body = json.dumps(
                    result, ensure_ascii=False, separators=(",", ":"), allow_nan=False
                ).encode()
                response.headers["content-length"] = str(len(response.body))
                return response
            except OperationalError as e:
                # 只重试整个事务；已回滚的网络重试仍使用原始请求及幂等键。
                if (
                    getattr(e.orig, "args", [None])[0] not in (1205, 1213)
                    or attempt == 3
                ):
                    raise
                await __import__("asyncio").sleep(0.02 * 2**attempt)
            except Exception as error:
                if (
                    request.scope["route"].path == "/api/agent/operations/{id}"
                    and request.method == "POST"
                ):
                    user_id = getattr(request.state, "user_id", None)
                    if user_id:
                        failure_message = (
                            error.detail
                            if isinstance(error, HTTPException)
                            else "提交失败，账目已回滚；可重试或取消"
                        )

                        def record_failure():
                            with transaction() as session:
                                op = one(
                                    session,
                                    AgentOperation,
                                    id=request.path_params["id"],
                                    userId=user_id,
                                    status="pending",
                                )
                                if op:
                                    op.result = {
                                        "status": "submission_failed",
                                        "message": failure_message,
                                    }
                                    session.add(
                                        AgentCall(
                                            userId=user_id,
                                            grantId=op.grantId,
                                            tool=op.tool,
                                            status="error",
                                        )
                                    )

                        await run_in_threadpool(record_failure)
                raise

    return endpoint


from .routes import ROUTES

inventory = {"http": ROUTES}
core = {"auth.ts", "portfolio.ts", "transfers.ts"}
for route in inventory["http"]:
    path = re.sub(r":(\w+)", r"{\1}", route["path"])
    app.add_api_route(
        path,
        endpoint_factory(),
        methods=[route["method"], "HEAD"]
        if route["method"] == "GET"
        else [route["method"]],
        name=route["method"] + " " + path,
    )

# OAuth/MCP 使用 Bearer 验证，不沿用网页 Cookie；必须先匹配各自协议的来源策略。
from . import oauth, mcp, agent_files

for path in [
    "/.well-known/oauth-authorization-server",
    "/.well-known/oauth-protected-resource",
    "/.well-known/oauth-protected-resource/mcp",
    "/authorize",
]:
    app.add_api_route(path, oauth.protocol, methods=["GET"], include_in_schema=False)
for path in ["/register", "/token", "/revoke"]:
    app.add_api_route(path, oauth.protocol, methods=["POST"], include_in_schema=False)
app.add_api_route(
    "/mcp",
    mcp.handle,
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
    include_in_schema=False,
)
app.add_api_route(
    "/api/agent/files/{id}",
    agent_files.handle,
    methods=["GET", "POST", "PUT", "DELETE"],
    include_in_schema=False,
)


@app.exception_handler(ValueError)
async def value_error(request, e):
    return JSONResponse({"message": str(e) or "请求参数无效"}, 400)


from .openapi_contract import DOCUMENT

app.openapi = lambda: DOCUMENT

# Starlette 的默认 405/422 响应与原接口不一致，统一为旧接口的错误契约。
from starlette.exceptions import HTTPException as StarletteHTTPException


@app.exception_handler(StarletteHTTPException)
async def routing_error(request, e):
    status = 404 if e.status_code == 405 else e.status_code
    message = (
        ("Cannot " + request.method + " " + request.url.path)
        if e.status_code in (404, 405)
        else e.detail
    )
    return JSONResponse({"message": message}, status)


# 最后安装前端托管；API、MCP 和 OAuth 路由始终先匹配。
from .web import install_web

install_web(app)
