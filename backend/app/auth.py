# 登录与权限：兼容 bcrypt 哈希、原会话 Cookie、隐藏项目解锁和只读角色。
"""Cookie authentication compatible with existing bcrypt hashes and session rows."""

import os, re, secrets, time, threading
from dataclasses import dataclass
from datetime import timedelta
import bcrypt
from sqlalchemy import select, delete, update
from .common import *
from .config import flag
from .models import User, Session, AgentGrant
from .schemas import money


@dataclass
class Context:
    userId: str
    sessionId: str
    revealed: bool = False
    agent: bool = False
    agentGrantId: str | None = None


attempts = {}
attempt_lock = threading.Lock()


def limit(request):
    if not flag("NETWORK_RATE_LIMIT_ENABLED", True):
        return
    key = request.client.host if request.client else "local"
    user_id = getattr(getattr(request, "state", None), "user_id", None)
    if user_id:
        key += ":" + user_id
    current = time.monotonic()
    with attempt_lock:
        entry = attempts.get(key)
        if not entry or entry[1] < current:
            entry = [
                0,
                current
                + int(os.getenv("NETWORK_RATE_LIMIT_WINDOW_MS", "900000")) / 1000,
            ]
            attempts[key] = entry
        entry[0] += 1
        if entry[0] > int(os.getenv("NETWORK_AUTH_RATE_LIMIT_MAX", "30")):
            fail("尝试过于频繁，请稍后重试", 429)
        if len(attempts) > 10000:
            for k in list(attempts):
                if attempts[k][1] < current:
                    del attempts[k]
            if len(attempts) > 10000:
                fail("服务繁忙，请稍后重试", 429)


def password(value, strong=False):
    if (
        not isinstance(value, str)
        or not 1 <= len(value.encode("utf8")) <= 72
        or (strong and len(value) < 10)
    ):
        fail("密码至少 10 个字符、最多 72 字节" if strong else "密码无效")
    return value


def username(value):
    if not isinstance(value, str):
        fail("账号无效")
    value = value.strip()
    if not 3 <= len(value) <= 64 or any(
        not (c.isalnum() or c in "_@.-") for c in value
    ):
        fail("账号无效")
    return value


def compare(value, hashed):
    try:
        return bcrypt.checkpw(value.encode(), hashed.encode())
    except (ValueError, TypeError):
        return False


def hash_password(value):
    return bcrypt.hashpw(value.encode(), bcrypt.gensalt(rounds=12)).decode()


def cookie(response, token, expires):
    secure = flag("COOKIE_SECURE", os.getenv("NODE_ENV") == "production")
    response.set_cookie(
        "wp_session",
        token,
        expires=expires.replace(tzinfo=timezone.utc),
        path="/api",
        httponly=True,
        secure=secure,
        samesite=os.getenv("COOKIE_SAME_SITE", "strict"),
    )
    response.raw_headers = [
        (
            k,
            v.replace(b"expires=", b"Expires=")
            .replace(b"SameSite=strict", b"SameSite=Strict")
            .replace(b"SameSite=lax", b"SameSite=Lax")
            .replace(b"SameSite=none", b"SameSite=None"),
        )
        if k == b"set-cookie"
        else (k, v)
        for k, v in response.raw_headers
    ]


def issue(s, user, response):
    token = secrets.token_hex(32)
    expires = now() + timedelta(hours=user.sessionHours)
    s.add(
        Session(id=digest(token), userId=user.id, expiresAt=expires, lastActivity=now())
    )
    cookie(response, token, expires)


# 登录态、首次改密和角色在每次请求重新核对，避免权限被撤销后继续使用。
def context(s, request):
    token = request.cookies.get("wp_session", "")
    if not re.fullmatch("[a-f0-9]{64}", token):
        fail("请先登录", 401)
    session = s.get(Session, digest(token))
    if not session or session.expiresAt <= now():
        fail("请先登录", 401)
    u = s.get(User, session.userId)
    if not u or u.banned:
        fail("账号已被封禁", 401)
    if u.idleMinutes and now() - session.lastActivity >= timedelta(
        minutes=u.idleMinutes
    ):
        fail("长时间无操作，已自动退出登录", 401)
    path = request.url.path.rstrip("/")
    if u.mustChangePassword and path not in [
        "/api/auth/me",
        "/api/auth/credentials",
        "/api/auth/logout",
        "/api/auth/activity",
    ]:
        fail("首次登录必须修改密码", 403)
    management = path == "/api/agent/tokens" or bool(
        re.fullmatch(r"/api/agent/(authorizations|connections)/[a-f0-9-]{36}", path)
    )
    if (
        u.role == "readonly"
        and request.method not in ("GET", "HEAD", "OPTIONS")
        and not path.startswith("/api/auth/")
        and not management
    ):
        fail("只读账号不能修改数据", 403)
    return Context(
        u.id, session.id, bool(session.revealUntil and session.revealUntil > now())
    )


def profile(s, r, settings=False):
    u = s.get(User, r.userId)
    session = s.get(Session, r.sessionId)
    keys = [
        "id",
        "role",
        "mustChangePassword",
        "username",
        "baseCurrency",
        "hiddenMenus",
        "showNotes",
        "idleMinutes",
        "accountGroupOrder",
        "sessionHours",
        "requireHiddenPassword",
        "overviewCards",
        "includeIndependentAssets",
    ]
    result = {key: getattr(u, key) for key in keys}
    result.update(
        accountGroupOrder=u.accountGroupOrder or [],
        overviewCards=u.overviewCards if u.overviewCards is not None else DEFAULT_CARDS,
        hiddenMenus=list(filter(None, u.hiddenMenus.split(","))),
        sessionExpiresAt=session.expiresAt,
        revealed=r.revealed,
        revealUntil=session.revealUntil if r.revealed or not settings else None,
        lastActivity=session.lastActivity,
    )
    return result


def login(s, body, request, response):
    limit(request)
    if not isinstance(body, dict) or set(body) != {"username", "password"}:
        fail("登录请求格式无效")
    name = username(body["username"])
    pw = password(body["password"])
    u = one(s, User, username=name)
    valid = compare(
        pw,
        u.passwordHash
        if u
        else "$2b$12$JZKvzAzfqM3obKxMQTFBjOzqIIKG97kn96/xUMbgTuWUnlMAT2bSi",
    )
    if not u or not valid:
        fail("账号或密码错误", 401)
    if u.banned:
        fail("账号已被封禁", 403)
    issue(s, u, response)
    return dict(
        username=u.username,
        baseCurrency=u.baseCurrency,
        role=u.role,
        mustChangePassword=u.mustChangePassword,
        hiddenMenus=[],
    )


def change_credentials(s, r, body, request, response):
    limit(request)
    if (
        not isinstance(body, dict)
        or set(body) - {"currentPassword", "username", "newPassword"}
        or not ("username" in body or "newPassword" in body)
    ):
        fail("请填写新的账号或密码")
    current = password(body.get("currentPassword"))
    u = s.scalar(select(User).where(User.id == r.userId).with_for_update())
    if not compare(current, u.passwordHash):
        fail("当前密码错误", 403)
    pw = body.get("newPassword")
    if pw is not None:
        password(pw, True)
    if u.mustChangePassword and (not pw or compare(pw, u.passwordHash)):
        fail("请设置与初始密码不同的新密码（至少 10 个字符）")
    name = username(body["username"]) if "username" in body else u.username
    if name == u.username and not pw:
        fail("请填写新的账号或密码")
    u.username = name
    if pw:
        u.passwordHash = hash_password(pw)
        u.mustChangePassword = False
    s.execute(
        update(AgentGrant)
        .where(AgentGrant.userId == u.id, AgentGrant.revokedAt.is_(None))
        .values(revokedAt=now())
    )
    s.execute(delete(Session).where(Session.userId == u.id))
    issue(s, u, response)
    return {"ok": True}


def reveal(s, r, body, request):
    limit(request)
    u = s.scalar(select(User).where(User.id == r.userId).with_for_update())
    if u.requireHiddenPassword:
        if not isinstance(body, dict) or set(body) != {"password"}:
            fail("密码参数无效")
        if not compare(password(body.get("password")), u.passwordHash):
            fail("密码错误", 403)
    until = now() + timedelta(minutes=5)
    s.get(Session, r.sessionId).revealUntil = until
    return {"revealUntil": until}


def logout(s, request, response):
    token = request.cookies.get("wp_session")
    if token:
        s.execute(delete(Session).where(Session.id == digest(token)))
    response.delete_cookie(
        "wp_session",
        path="/api",
        httponly=True,
        secure=flag("COOKIE_SECURE"),
        samesite=os.getenv("COOKIE_SAME_SITE", "strict"),
    )
    return {"ok": True}


# 仅在没有管理员时初始化；要求显式配置凭据，绝不重置已有密码或提升同名用户。
def bootstrap(s):
    from sqlalchemy import func

    if s.scalar(select(func.count()).select_from(User).where(User.role == "admin")):
        return
    configured_name = os.getenv("ADMIN_USERNAME")
    configured_password = os.getenv("ADMIN_PASSWORD")
    if not configured_name or not configured_password:
        raise RuntimeError(
            "Administrator credentials must be configured for an empty database"
        )
    name = username(configured_name)
    pw = password(configured_password, True)
    if one(s, User, username=name):
        raise RuntimeError("Default administrator username already exists")
    s.add(
        User(
            username=name,
            passwordHash=hash_password(pw),
            role="admin",
            mustChangePassword=True,
        )
    )
