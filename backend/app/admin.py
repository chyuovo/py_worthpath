# 管理员业务：角色不授予其他用户的财务访问权限，权限变化撤销原有授权。
from sqlalchemy import select, delete, update, func
from .common import *
from .models import *
from . import auth


def summary(u):
    return {
        k: getattr(u, k)
        for k in ("id", "username", "role", "banned", "mustChangePassword", "createdAt")
    }


def require_admin(s, r):
    u = s.scalar(select(User).where(User.id == r.userId).with_for_update())
    if not u or u.role != "admin" or u.banned or u.mustChangePassword:
        fail("需要已完成改密的管理员账号", 403)
    return u


def dispatch(s, r, request, response, body):
    path = request.scope["route"].path
    if not path.startswith("/api/admin/users"):
        return NotImplemented
    actor = require_admin(s, r)
    method = request.method
    if method == "GET":
        try:
            offset = int(request.query_params.get("offset", 0))
            limit = int(request.query_params.get("limit", 50))
            assert offset >= 0 and 1 <= limit <= 100
        except (ValueError, AssertionError):
            fail("分页参数无效")
        return dict(
            items=[
                summary(u)
                for u in s.scalars(
                    select(User)
                    .order_by(User.createdAt, User.id)
                    .offset(offset)
                    .limit(limit)
                )
            ],
            total=s.scalar(select(func.count()).select_from(User)),
            offset=offset,
            limit=limit,
        )
    if method == "POST":
        if (
            not isinstance(body, dict)
            or set(body) - {"username", "password", "role"}
            or not {"username", "password"}.issubset(body)
        ):
            fail("账号参数无效")
        role = body.get("role", "user")
        if role not in ("admin", "user", "readonly"):
            fail("角色无效")
        u = User(
            username=auth.username(body["username"]),
            passwordHash=auth.hash_password(auth.password(body["password"], True)),
            role=role,
            mustChangePassword=True,
        )
        s.add(u)
        s.flush()
        return summary(u)
    id = request.path_params["id"]
    if id == r.userId:
        fail(
            "不能修改自己的系统权限或封禁自己"
            if method == "PATCH"
            else "不能删除当前登录的管理员账号",
            403,
        )
    s.scalars(
        select(User).where(User.role == "admin").order_by(User.id).with_for_update()
    ).all()
    target = s.get(User, id)
    if not target:
        fail("账号不存在", 404)
    if method == "DELETE":
        auth.limit(request)
        if not isinstance(body, dict) or set(body) != {
            "currentPassword",
            "confirmationUsername",
        }:
            fail("删除确认参数无效")
        if not auth.compare(auth.password(body["currentPassword"]), actor.passwordHash):
            fail("当前密码错误", 403)
        if target.username != "admin" or target.role != "admin":
            fail("仅允许删除默认 admin 账号，其他账号不可删除", 403)
        if body["confirmationUsername"] != target.username:
            fail("确认账号名称不一致，请重新核对")
        if not s.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.id != id,
                User.role == "admin",
                User.banned.is_(False),
                User.mustChangePassword.is_(False),
            )
        ):
            fail("请先设置另一位已完成改密且未封禁的管理员", 403)
        s.execute(delete(Icon).where(Icon.ownerId == id, Icon.shared.is_(False)))
        s.delete(target)
        return {"ok": True}
    if not isinstance(body, dict) or not body or set(body) - {"role", "banned"}:
        fail("账号参数无效")
    if "role" in body and body["role"] not in ("admin", "user", "readonly"):
        fail("角色无效")
    if "banned" in body and type(body["banned"]) is not bool:
        fail("封禁参数无效")
    if (
        target.role == "admin"
        and not target.banned
        and (body.get("banned") or body.get("role", target.role) != "admin")
        and s.scalar(
            select(func.count())
            .select_from(User)
            .where(User.role == "admin", User.banned.is_(False))
        )
        <= 1
    ):
        fail("必须保留至少一个可用管理员", 403)
    changed = any(getattr(target, k) != v for k, v in body.items())
    for k, v in body.items():
        setattr(target, k, v)
    if changed:
        s.execute(delete(Session).where(Session.userId == id))
        s.execute(
            update(AgentGrant)
            .where(AgentGrant.userId == id, AgentGrant.revokedAt.is_(None))
            .values(revokedAt=now())
        )
        s.execute(
            update(AgentAuthorization)
            .where(
                AgentAuthorization.userId == id,
                AgentAuthorization.status.in_(["pending", "approved"]),
            )
            .values(status="cancelled")
        )
        s.execute(
            update(AgentOperation)
            .where(AgentOperation.userId == id, AgentOperation.status == "pending")
            .values(status="cancelled", completedAt=now())
        )
    return summary(target)
