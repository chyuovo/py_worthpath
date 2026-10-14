# 管理员共享图标管理：只下架和恢复，不删除图片，不改动账户引用。
from sqlalchemy import func, select

from .admin import require_admin
from .common import fail, now
from .models import Icon


def summary(icon):
    return {
        "id": icon.id,
        "name": icon.name,
        "shared": True,
        "deletedAt": icon.deletedAt,
    }


def dispatch(s, r, request, response, body):
    path = request.scope["route"].path
    if not path.startswith("/api/admin/icons"):
        return NotImplemented
    require_admin(s, r)
    if request.method == "GET":
        q = request.query_params.get("q", "").strip()
        status = request.query_params.get("status", "active")
        try:
            offset = int(request.query_params.get("offset", 0))
            limit = int(request.query_params.get("limit", 50))
            assert offset >= 0 and 1 <= limit <= 100 and len(q) <= 100
            assert status in ("active", "deleted", "all")
        except (ValueError, AssertionError):
            fail("图标查询参数无效")
        where = [Icon.shared.is_(True), Icon.name.contains(q, autoescape=True)]
        if status != "all":
            where.append(
                Icon.deletedAt.is_(None)
                if status == "active"
                else Icon.deletedAt.is_not(None)
            )
        items = s.scalars(
            select(Icon)
            .where(*where)
            .order_by(Icon.name, Icon.id)
            .offset(offset)
            .limit(limit)
        )
        return {
            "items": [summary(i) for i in items],
            "total": s.scalar(select(func.count()).select_from(Icon).where(*where)),
            "offset": offset,
            "limit": limit,
        }
    if (
        not isinstance(body, dict)
        or set(body) != {"confirmed"}
        or body["confirmed"] is not True
    ):
        fail("请确认图标管理操作")
    # 锁定目标行保证并发修改串行执行；重复下架不会覆盖首次下架时间。
    icon = s.scalar(
        select(Icon)
        .where(Icon.id == request.path_params["id"], Icon.shared.is_(True))
        .with_for_update()
    )
    if not icon:
        fail("共享图标不存在", 404)
    if request.method == "DELETE":
        if icon.deletedAt is None:
            icon.deletedAt = now()
    else:
        icon.deletedAt = None
    return summary(icon)
