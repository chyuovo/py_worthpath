from fastapi import Request

# MCP 文件票据：短期入口还必须匹配 Bearer 连接，不能通过网页 Cookie 越权。
from uuid import uuid4
from sqlalchemy import select
from fastapi.responses import JSONResponse, Response
from .common import *
from . import oauth, icons
from .database import transaction

TICKETS = {}


def issue(s, g, kind, icon_id=None):
    for key, t in list(TICKETS.items()):
        if t["expiresAt"] < now():
            TICKETS.pop(key)
    if (
        len(TICKETS) >= 1000
        or sum(t["userId"] == g.userId for t in TICKETS.values()) >= 20
    ):
        fail("文件请求过多，请等待过期")
    id = str(uuid4())
    expires = now() + timedelta(minutes=10)
    TICKETS[id] = dict(
        userId=g.userId, grantId=g.id, kind=kind, iconId=icon_id, expiresAt=expires
    )
    return dict(
        fileId=id,
        url=oauth.urls()[1] + "/api/agent/files/" + id,
        method="GET" if kind == "image" else "POST",
        headers={"Authorization": "Bearer <your access token>"},
        expiresAt=iso(expires),
        maxBytes=2 * 1024 * 1024,
        format="image/png"
        if kind == "image"
        else "multipart/form-data; field file; image",
    )


def ticket(g, id):
    t = TICKETS.get(id)
    if (
        not t
        or t["userId"] != g.userId
        or t["grantId"] != g.id
        or t["expiresAt"] < now()
    ):
        fail("文件入口已失效或不属于此连接", 403)
    return t


def status(g, id):
    t = ticket(g, id)
    return dict(fileId=id, uploaded=bool(t.get("buffer")), expiresAt=t["expiresAt"])


def publish(s, g, p):
    t = ticket(g, p["fileId"])
    if t["kind"] != "icon" or not t.get("buffer"):
        fail("请先上传图标")
    if p.get("shared") is not False:
        fail("不允许发布共享图标")
    return icons.upload(
        s,
        oauth.context(s, g, True),
        dict(name=p["name"], shared="false", _file=t["buffer"]),
    )


async def handle(request: Request):
    try:
        with transaction() as s:
            g = oauth.bearer(s, request)
            id = request.path_params["id"]
            t = ticket(g, id)
            if (request.method == "POST") != (
                t["kind"] == "icon"
            ) or request.method not in ("GET", "POST"):
                return Response(status_code=405)
            if request.method == "GET":
                icon = icons.visible(s, oauth.context(s, g), t["iconId"])
                return Response(bytes(icon.data), media_type="image/png")
            if not {"draft", "write"}.intersection(g.scopes):
                fail("上传需要 draft 或 write 权限", 403)
            form = await request.form(max_files=1, max_fields=0)
            file = form.get("file")
            if not file:
                fail("请选择文件")
            raw = await file.read(2 * 1024 * 1024 + 1)
            await file.close()
            if len(raw) > 2 * 1024 * 1024:
                fail("图标不能超过 2 MB")
            t["buffer"] = raw
            return JSONResponse(serializable(status(g, id)))
    except HTTPException as e:
        return JSONResponse({"message": e.detail}, e.status_code)
