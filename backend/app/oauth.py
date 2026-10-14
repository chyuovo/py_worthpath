from fastapi import Request

# OAuth 与个人令牌：只保存摘要；PKCE 授权码一次性消费，刷新令牌每次轮换。
import os, secrets, re, time, base64
from uuid import uuid4
from urllib.parse import urlsplit, urlunsplit, urlencode, parse_qsl
from sqlalchemy import select, func, or_
from fastapi.responses import JSONResponse, RedirectResponse
from .common import *
from .models import *
from .config import flag
from .auth import Context

SCOPES = ["read", "draft", "write", "hidden_read", "hidden_write"]
DAYS = [1, 3, 7, 30, 365, None]


def urls():
    resource = os.getenv("MCP_PUBLIC_URL", "http://localhost:3100/mcp")
    web = os.getenv("MCP_WEB_URL", "http://localhost:5173")
    u = urlsplit(resource)
    w = urlsplit(web)
    allow = flag("NETWORK_ALLOW_HTTP", os.getenv("NODE_ENV") != "production")
    if (
        u.path != "/mcp"
        or u.query
        or u.fragment
        or u.username
        or u.password
        or u.scheme not in (["http", "https"] if allow else ["https"])
    ):
        raise RuntimeError("Invalid MCP_PUBLIC_URL")
    if w.scheme not in (["http", "https"] if allow else ["https"]):
        raise RuntimeError("Invalid MCP_WEB_URL")
    # 与 URL.toString 一样规范化资源地址，避免大小写或默认端口使已有授权失配。
    host = u.hostname.encode("idna").decode().lower()
    if ":" in host:
        host = "[" + host + "]"
    port = u.port
    if port is not None and port != (443 if u.scheme == "https" else 80):
        host += ":" + str(port)
    resource = urlunsplit((u.scheme, host, "/mcp", "", ""))
    return resource, urlunsplit((u.scheme, host, "", "", "")), web


def web_link(key, id):
    web = urls()[2]
    u = urlsplit(web)
    path = u.path.rstrip("/") + (
        "/agent/authorize" if key == "agent_authorization" else "/agent/operation"
    )
    query = dict(parse_qsl(u.query, keep_blank_values=True))
    query[key] = id
    return urlunsplit((u.scheme, u.netloc, path, urlencode(query), u.fragment))


def valid_scopes(value):
    if (
        not isinstance(value, list)
        or not 1 <= len(value) <= 4
        or len(set(value)) != len(value)
        or set(value) - set(SCOPES)
        or "read" not in value
        or ("draft" in value and "write" in value)
        or (
            "hidden_write" in value
            and (
                "hidden_read" not in value or not {"draft", "write"}.intersection(value)
            )
        )
    ):
        fail("授权范围无效")
    return value


def grant(s, id, user_id=None):
    g = s.get(AgentGrant, id)
    if (
        not g
        or (user_id and g.userId != user_id)
        or g.revokedAt
        or (g.expiresAt and g.expiresAt <= now())
        or (not g.expiresAt and g.clientId)
        or (g.clientId and g.refreshExpiresAt and g.refreshExpiresAt <= now())
    ):
        fail("Agent 连接已过期或撤销", 403)
    u = s.get(User, g.userId)
    if not u or u.banned or u.mustChangePassword:
        fail("账号已封禁或需要首次改密", 403)
    return g


def bearer(s, request):
    match = re.fullmatch(
        r"Bearer ([A-Za-z0-9_-]{43})", request.headers.get("authorization", "")
    )
    g = one(s, AgentGrant, accessDigest=digest(match[1])) if match else None
    if not g or g.resource != urls()[0]:
        fail("Invalid token", 401)
    try:
        g = grant(s, g.id)
    except HTTPException:
        fail("Expired, revoked or invalid resource token", 401)
    if "read" not in g.scopes:
        fail("Insufficient scope", 403)
    return g


def issue(s, user_id, name, selected, days, client_id=None, authorization_days=30):
    valid_scopes(selected)
    if authorization_days not in DAYS:
        fail("授权期限无效")
    u = s.scalar(select(User).where(User.id == user_id).with_for_update())
    if not u or u.banned or u.mustChangePassword:
        fail("账号已封禁或需要首次改密", 403)
    if u.role == "readonly" and {"draft", "write", "hidden_write"}.intersection(
        selected
    ):
        fail("只读账号只能授予查询权限", 403)
    access = secrets.token_urlsafe(32)
    refresh = secrets.token_urlsafe(32) if client_id else None
    session_id = digest(secrets.token_urlsafe(32))
    expires = now() + timedelta(days=days) if days is not None else None
    refresh_expires = (
        now() + timedelta(days=authorization_days)
        if client_id and authorization_days is not None
        else None
    )
    s.add(
        Session(
            id=session_id,
            userId=user_id,
            expiresAt=(refresh_expires or now() + timedelta(days=30))
            if client_id
            else expires or now() + timedelta(days=1),
        )
    )
    g = AgentGrant(
        userId=user_id,
        name=name,
        clientId=client_id,
        scopes=selected,
        resource=urls()[0],
        accessDigest=digest(access),
        refreshDigest=digest(refresh) if refresh else None,
        expiresAt=expires,
        refreshExpiresAt=refresh_expires,
        sessionId=session_id,
    )
    s.add(g)
    s.flush()
    tokens = dict(access_token=access, token_type="Bearer", scope=" ".join(selected))
    if days is not None:
        tokens["expires_in"] = int(days * 86400)
    if refresh:
        tokens["refresh_token"] = refresh
    return g, tokens


def context(s, g, writing=False):
    session = s.get(Session, g.sessionId)
    if (
        not g.expiresAt
        and not g.clientId
        and (not session or session.expiresAt <= now())
    ):
        if not session:
            session = Session(
                id=g.sessionId, userId=g.userId, expiresAt=now() + timedelta(days=1)
            )
            s.add(session)
        else:
            session.expiresAt = now() + timedelta(days=1)
            session.revealUntil = None
            session.backupDigest = None
            session.backupExpiresAt = None
        s.flush()
    if not session or session.expiresAt <= now():
        fail("连接会话失效，请重新授权", 403)
    return Context(
        g.userId,
        g.sessionId,
        ("hidden_write" if writing else "hidden_read") in g.scopes,
        True,
        g.id,
    )


def pending(s, id):
    a = s.get(AgentAuthorization, id)
    if not a or a.status != "pending" or a.expiresAt <= now():
        fail("授权请求已失效")
    c = s.get(AgentClient, a.clientId)
    p = a.parameters
    return dict(
        id=id,
        name=c.metadata_.get("client_name") if c else None,
        redirectUri=p["redirectUri"],
        scopes=p["scopes"],
        availableScopes=["read", "draft", "write"]
        + [v for v in p["scopes"] if v.startswith("hidden_")],
        resource=p["resource"],
    )


def consent(s, r, id, body):
    if (
        not isinstance(body, dict)
        or set(body) - {"approve", "scopes", "days"}
        or type(body.get("approve")) is not bool
    ):
        fail("授权参数无效")
    pending(s, id)
    a = s.scalar(
        select(AgentAuthorization).where(AgentAuthorization.id == id).with_for_update()
    )
    p = a.parameters
    selected = valid_scopes(body.get("scopes", ["read"]))
    days = body.get("days", 30)
    if days not in DAYS:
        fail("授权期限无效")
    user = s.get(User, r.userId)
    if (
        body["approve"]
        and user.role == "readonly"
        and {"draft", "write", "hidden_write"}.intersection(selected)
    ):
        fail("只读账号只能授予查询权限", 403)
    if any(v.startswith("hidden_") and v not in p["scopes"] for v in selected):
        fail("不能授予客户端未请求的隐藏权限")
    if a.status != "pending" or a.expiresAt <= now():
        fail("授权请求已处理")
    code = secrets.token_urlsafe(32)
    a.userId = r.userId
    a.status = "approved" if body["approve"] else "denied"
    a.codeDigest = digest(code) if body["approve"] else None
    a.parameters = {**p, "scopes": selected, "authorizationDays": days}
    u = urlsplit(p["redirectUri"])
    q = dict(parse_qsl(u.query))
    q["code" if body["approve"] else "error"] = (
        code if body["approve"] else "access_denied"
    )
    if p.get("state"):
        q["state"] = p["state"]
    return {
        "redirect": urlunsplit((u.scheme, u.netloc, u.path, urlencode(q), u.fragment))
    }


def oauth_error(code, message, status=400):
    return JSONResponse({"error": code, "error_description": message}, status)


# OAuth 公共认证端点按来源和路径独立限流，沿用原有网络配置。
_oauth_attempts = {}


def rate_limit(request, path):
    if not flag("NETWORK_RATE_LIMIT_ENABLED", True):
        return False
    current = time.monotonic()
    key = ((request.client.host if request.client else "local"), path)
    count, until = _oauth_attempts.get(key, (0, 0))
    if until < current:
        count = 0
        until = (
            current + int(os.getenv("NETWORK_RATE_LIMIT_WINDOW_MS", "900000")) / 1000
        )
    _oauth_attempts[key] = (count + 1, until)
    if len(_oauth_attempts) > 10000:
        for old in list(_oauth_attempts):
            if _oauth_attempts[old][1] < current:
                _oauth_attempts.pop(old, None)
    return count + 1 > int(os.getenv("MCP_AUTH_RATE_LIMIT_MAX", "100"))


async def protocol(request: Request):
    from .database import transaction

    path = request.url.path
    if path in ("/authorize", "/token", "/revoke", "/register") and rate_limit(
        request, path
    ):
        return oauth_error("rate_limit_exceeded", "尝试过于频繁，请稍后重试", 429)
    resource, issuer, web = urls()
    if path.startswith("/.well-known/oauth-protected-resource"):
        return JSONResponse(
            dict(
                resource=resource,
                authorization_servers=[issuer],
                scopes_supported=SCOPES,
                bearer_methods_supported=["header"],
                resource_name="WorthPath",
            )
        )
    if path == "/.well-known/oauth-authorization-server":
        return JSONResponse(
            dict(
                issuer=issuer,
                authorization_endpoint=issuer + "/authorize",
                token_endpoint=issuer + "/token",
                registration_endpoint=issuer + "/register",
                revocation_endpoint=issuer + "/revoke",
                response_types_supported=["code"],
                grant_types_supported=["authorization_code", "refresh_token"],
                token_endpoint_auth_methods_supported=["none"],
                code_challenge_methods_supported=["S256"],
                scopes_supported=SCOPES,
            )
        )
    try:
        with transaction(write=True) as s:
            if path == "/register":
                p = await request.json()
                if p.get("token_endpoint_auth_method") != "none":
                    return oauth_error(
                        "invalid_client_metadata",
                        "Only public PKCE clients are supported",
                    )
                uris = p.get("redirect_uris", [])
                if not 1 <= len(uris) <= 10:
                    return oauth_error(
                        "invalid_client_metadata", "Invalid redirect URIs"
                    )
                for value in uris:
                    u = urlsplit(value)
                    if (
                        u.fragment
                        or u.username
                        or u.password
                        or not (
                            u.scheme == "https"
                            or (
                                u.scheme == "http"
                                and (
                                    flag(
                                        "NETWORK_ALLOW_HTTP_REDIRECTS",
                                        os.getenv("NODE_ENV") != "production",
                                    )
                                    or u.hostname in ("localhost", "127.0.0.1", "::1")
                                )
                            )
                        )
                    ):
                        return oauth_error(
                            "invalid_client_metadata",
                            "HTTPS or loopback redirect required",
                        )
                if s.scalar(select(func.count()).select_from(AgentClient)) >= 10000:
                    return oauth_error(
                        "invalid_client_metadata", "Client registration limit reached"
                    )
                name = p.get("client_name", "MCP client")
                if not isinstance(name, str) or not 1 <= len(name) <= 100:
                    return oauth_error("invalid_client_metadata", "Invalid client name")
                c = {
                    **p,
                    "client_name": name,
                    "client_id": str(uuid4()),
                    "client_id_issued_at": int(time.time()),
                }
                s.add(AgentClient(id=c["client_id"], metadata_=c))
                return JSONResponse(c, 201)
            p = (
                dict(request.query_params)
                if request.method == "GET"
                else dict(await request.form())
            )
            client = s.get(AgentClient, p.get("client_id"))
            if path == "/authorize":
                if not client:
                    return oauth_error("invalid_client", "Invalid client", 401)
                if p.get("resource") != resource:
                    return oauth_error(
                        "invalid_target", "WorthPath resource is required"
                    )
                if (
                    p.get("redirect_uri") not in client.metadata_["redirect_uris"]
                    or p.get("response_type") != "code"
                ):
                    return oauth_error(
                        "invalid_request", "Invalid redirect or response type"
                    )
                if p.get("code_challenge_method") != "S256" or not re.fullmatch(
                    "[A-Za-z0-9_-]{43}", p.get("code_challenge", "")
                ):
                    return oauth_error("invalid_request", "S256 PKCE required")
                selected = p.get("scope", "read").split()
                if (
                    not selected
                    or "read" not in selected
                    or len(set(selected)) != len(selected)
                    or set(selected) - set(SCOPES)
                ):
                    return oauth_error("invalid_scope", "Unsupported scope")
                params = dict(
                    redirectUri=p["redirect_uri"],
                    codeChallenge=p["code_challenge"],
                    resource=resource,
                    scopes=selected,
                )
                if p.get("state"):
                    params["state"] = p["state"]
                a = AgentAuthorization(
                    clientId=client.id,
                    parameters=params,
                    expiresAt=now() + timedelta(minutes=10),
                )
                s.add(a)
                s.flush()
                return RedirectResponse(web_link("agent_authorization", a.id), 302)
            if not client:
                return oauth_error("invalid_client", "Invalid client", 401)
            if path == "/revoke":
                g = s.scalar(
                    select(AgentGrant)
                    .where(
                        AgentGrant.clientId == client.id,
                        or_(
                            AgentGrant.accessDigest == digest(p.get("token", "")),
                            AgentGrant.refreshDigest == digest(p.get("token", "")),
                        ),
                    )
                    .with_for_update()
                )
                if g:
                    g.revokedAt = now()
                return JSONResponse({})
            if p.get("resource") != resource:
                return oauth_error("invalid_target", "WorthPath resource is required")
            if p.get("grant_type") == "authorization_code":
                a = s.scalar(
                    select(AgentAuthorization)
                    .where(AgentAuthorization.codeDigest == digest(p.get("code", "")))
                    .with_for_update()
                )
                if (
                    not a
                    or a.clientId != client.id
                    or a.status != "approved"
                    or a.expiresAt <= now()
                ):
                    return oauth_error("invalid_grant", "Invalid authorization code")
                params = a.parameters
                verifier = p.get("code_verifier", "")
                challenge = (
                    base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
                    .decode()
                    .rstrip("=")
                )
                if (
                    not 43 <= len(verifier) <= 128
                    or challenge != params["codeChallenge"]
                    or p.get("redirect_uri") != params["redirectUri"]
                ):
                    return oauth_error("invalid_grant", "PKCE or redirect mismatch")
                a.status = "used"
                a.codeDigest = None
                _, tokens = issue(
                    s,
                    a.userId,
                    client.metadata_.get("client_name", "MCP client"),
                    params["scopes"],
                    1 / 24,
                    client.id,
                    params.get("authorizationDays", 30),
                )
                return JSONResponse(tokens)
            if p.get("grant_type") == "refresh_token":
                g = s.scalar(
                    select(AgentGrant)
                    .where(
                        AgentGrant.refreshDigest == digest(p.get("refresh_token", ""))
                    )
                    .with_for_update()
                )
                if (
                    not g
                    or g.clientId != client.id
                    or g.revokedAt
                    or (g.refreshExpiresAt and g.refreshExpiresAt <= now())
                ):
                    return oauth_error("invalid_grant", "Invalid refresh token")
                user = s.get(User, g.userId)
                if user.banned or user.mustChangePassword:
                    return oauth_error("invalid_grant", "Account unavailable")
                selected = p.get("scope", " ".join(g.scopes)).split()
                valid_scopes(selected)
                if set(selected) - set(g.scopes):
                    return oauth_error("invalid_scope", "Scope escalation rejected")
                access = secrets.token_urlsafe(32)
                refresh = secrets.token_urlsafe(32)
                expires = min(
                    now() + timedelta(hours=1), g.refreshExpiresAt or datetime.max
                )
                g.accessDigest = digest(access)
                g.refreshDigest = digest(refresh)
                g.expiresAt = expires
                g.scopes = selected
                session = s.get(Session, g.sessionId)
                if not session:
                    session = Session(id=g.sessionId, userId=g.userId)
                    s.add(session)
                session.expiresAt = g.refreshExpiresAt or now() + timedelta(days=30)
                session.revealUntil = None
                session.backupDigest = None
                session.backupExpiresAt = None
                return JSONResponse(
                    dict(
                        access_token=access,
                        refresh_token=refresh,
                        token_type="Bearer",
                        expires_in=max(0, int((expires - now()).total_seconds())),
                        scope=" ".join(selected),
                    )
                )
            return oauth_error("unsupported_grant_type", "Unsupported grant type")
    except HTTPException as e:
        return oauth_error("invalid_request", e.detail, e.status_code)
    except (ValueError, KeyError, TypeError):
        return oauth_error("invalid_request", "Invalid OAuth request")
