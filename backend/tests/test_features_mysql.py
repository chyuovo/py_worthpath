# 使用真实 MySQL 和专用临时用户验证模块；不会清空共享库或修改既有用户。
import io, json, uuid, base64, hashlib
import httpx, pytest
from PIL import Image
from sqlalchemy import select
from test_core_mysql import users, make, API_URL, ROOT_URL
from app.common import today, now, business_time, fixed, dec
from app.database import transaction
from app.models import *


def test_settings_calendar_schedule(users):
    a, b = users
    account = make(a, "migration scheduled", "100")
    assert (
        a.patch(
            "/settings", json={"accountGroupOrder": ["甲", "乙"], "showNotes": False}
        ).status_code
        == 200
    )
    assert a.get("/settings").json()["accountGroupOrder"] == ["甲", "乙"]
    assert a.patch("/settings", json={"sessionHours": 0}).status_code == 400
    plan = dict(
        name="migration plan",
        operation="expense",
        sourceId=account,
        amount="3.12",
        nextAt=today() + "T00:00",
        intervalDays=0,
    )
    created = a.post("/schedules", json=plan)
    assert created.status_code == 201, created.text
    id = created.json()["id"]
    assert b.delete("/schedules/" + id).status_code == 404
    run = a.post("/schedules/run")
    assert run.status_code == 201, run.text
    assert run.json()["executed"] == 1
    assert a.post("/schedules/run").json()["executed"] == 0
    assert a.get("/positions/" + account).json()["amount"] == "96.88"
    month = a.get("/calendar").json()
    assert month["items"][int(today()[-2:]) - 1]["expense"] == "3.12"
    assert (
        a.get("/calendar/day", params={"date": today()}).json()["items"][0]["amount"]
        == "3.12"
    )
    assert a.patch("/schedules/" + id, json={"enabled": True}).status_code == 400


def test_icon_and_zip_roundtrip(users):
    a, b = users
    source = make(a, "migration zip source", "50")
    target = make(a, "migration zip target", "0")
    png = io.BytesIO()
    Image.new("RGB", (400, 100), (255, 0, 0)).save(png, format="PNG")
    icon = a.post(
        "/icons/upload",
        data={"name": "迁移图标", "shared": "false"},
        files={"file": ("migration.png", png.getvalue(), "image/png")},
    )
    assert icon.status_code == 201, icon.text
    assert (
        a.patch(
            "/positions/" + source,
            json=dict(
                name="migration zip source", category="other", iconId=icon.json()["id"]
            ),
        ).status_code
        == 200
    )
    assert b.get("/icons/" + icon.json()["id"] + "/image").status_code == 404
    a.post(
        "/transfers",
        json=dict(
            sourceId=source,
            targetId=target,
            amount="1",
            received="1",
            date=today(),
            requestId=str(uuid.uuid4()),
        ),
    )
    backup = a.get("/backup")
    assert backup.status_code == 200 and backup.headers["content-type"].startswith(
        "application/zip"
    ), backup.text[:100]
    preview = b.post(
        "/backup/upload",
        files={"file": ("migration.zip", backup.content, "application/zip")},
    )
    assert preview.status_code == 201, preview.text
    assert preview.json()["positions"] == 2
    result = b.post(
        "/backup/import-file",
        json={"confirmed": True, "token": preview.json()["token"]},
    )
    assert result.status_code == 201, result.text
    assert b.get("/overview").json()["net"] == a.get("/overview").json()["net"]
    assert len(b.get("/positions").json()) == 2
    duplicate = b.post(
        "/backup/upload",
        files={"file": ("migration.zip", backup.content, "application/zip")},
    )
    assert duplicate.status_code == 409, duplicate.text
    # 内容变化使之前的清空凭据失效，不能清掉新写入的数据。
    assert a.get("/backup/clear-status").json()["ready"] is True
    a.post(
        "/positions/" + source + "/revisions", json={"amount": "52", "date": today()}
    )
    assert a.post("/backup/clear", json={"confirmation": "确定清空"}).status_code == 409


def test_metal_decimal_valuation(users):
    a, b = users
    uid = a.get("/auth/me").json()["id"]
    with transaction() as s:
        s.add(
            MetalPrice(
                userId=uid,
                metalType="gold",
                currency="CNY",
                price="600.123456789012",
                date=__import__("datetime").date.fromisoformat(today()),
                source="manual",
                quotedAt=now(),
            )
        )
    created = a.post(
        "/metals/holdings",
        json=dict(
            name="migration gold",
            metalType="gold",
            metalGrams="1.12345678",
            metalCostPerGram="500",
            autoValuation=False,
            currency="CNY",
            date=today(),
        ),
    )
    assert created.status_code == 201, created.text
    id = created.json()["id"]
    detail = a.get("/positions/" + id).json()
    assert detail["amount"] == fixed(
        dec(fixed(dec("1.12345678") * dec("600.123456789012"), 8))
    )
    assert detail["valuationAvailable"] is True
    assert b.post("/metals/" + id + "/value").status_code == 404


def token(a, scopes):
    with transaction() as s:
        # 仅给本次创建的临时用户设置测试密码，既有用户不会进入此函数。
        from app.auth import hash_password

        u = s.get(User, a.get("/auth/me").json()["id"])
        assert u.username.startswith("py_migration_")
        u.passwordHash = hash_password("MigrationTest!23456")
    res = a.post(
        "/agent/tokens",
        json=dict(
            name="migration connector",
            scopes=scopes,
            days=1,
            password="MigrationTest!23456",
        ),
    )
    assert res.status_code == 201, res.text
    return res.json()


def rpc(token, name, args=None, id=1):
    res = httpx.post(
        ROOT_URL + "/mcp",
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/json, text/event-stream",
        },
        json={
            "jsonrpc": "2.0",
            "id": id,
            "method": "tools/call",
            "params": {"name": name, "arguments": args or {}},
        },
        timeout=30,
    )
    assert res.status_code == 200, res.text
    return res.json()["result"]


def test_mcp_permissions_idempotency_and_draft(users):
    a, b = users
    read = token(a, ["read"])
    direct = token(a, ["read", "write", "hidden_read", "hidden_write"])
    draft = token(a, ["read", "draft"])
    # 已移除的工具必须返回工具错误，不能中断整个 MCP 会话。
    assert rpc(direct["token"], "backup_export")["isError"]
    info = rpc(direct["token"], "connection_info")["structuredContent"]["data"]
    assert info["readHidden"] and info["writeHidden"] and info["permission"] == "write"
    state = rpc(direct["token"], "state_get")["structuredContent"]["data"]["state"]
    v = dict(
        name="migration MCP",
        kind="account",
        side="asset",
        category="other",
        currency="CNY",
        amount="1",
        date=today(),
        expectedState=state,
        idempotencyKey="migration-" + uuid.uuid4().hex,
    )
    denied = rpc(read["token"], "position_create", v)
    assert denied["isError"]
    first = rpc(direct["token"], "position_create", v)
    assert not first.get("isError"), first
    assert first["structuredContent"]["data"]["status"] == "completed"
    second = rpc(direct["token"], "position_create", v)
    assert second == first
    conflict = rpc(direct["token"], "position_create", {**v, "amount": "2"})
    assert conflict["isError"]
    state = rpc(draft["token"], "state_get")["structuredContent"]["data"]["state"]
    pending = rpc(
        draft["token"],
        "position_create",
        {
            **v,
            "name": "migration draft",
            "expectedState": state,
            "idempotencyKey": "migration-" + uuid.uuid4().hex,
        },
    )["structuredContent"]["data"]
    assert pending["status"] == "pending" and "confirmationUrl" in pending
    id = pending["operationId"]
    assert b.get("/agent/operations/" + id).status_code == 404
    before = len(a.get("/positions").json())
    confirmed = a.post("/agent/operations/" + id, json={"approve": True})
    assert confirmed.status_code == 201, confirmed.text
    assert len(a.get("/positions").json()) == before + 1
    assert (
        rpc(draft["token"], "operation_get", {"operationId": id})["structuredContent"][
            "data"
        ]["status"]
        == "completed"
    )
    assert a.delete("/agent/connections/" + direct["id"]).status_code == 200
    assert (
        httpx.post(
            ROOT_URL + "/mcp",
            headers={"Authorization": "Bearer " + direct["token"]},
            json={},
        ).status_code
        == 401
    )


def test_oauth_pkce_rotation(users):
    a, b = users
    base = ROOT_URL
    metadata = httpx.get(base + "/.well-known/oauth-authorization-server").json()
    resource = httpx.get(base + "/.well-known/oauth-protected-resource/mcp").json()[
        "resource"
    ]
    client = httpx.post(
        base + "/register",
        json=dict(
            client_name="migration PKCE",
            redirect_uris=["http://localhost:8989/callback"],
            token_endpoint_auth_method="none",
        ),
    ).json()
    verifier = "A" * 64
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    authorization = httpx.get(
        base + "/authorize",
        params=dict(
            client_id=client["client_id"],
            redirect_uri="http://localhost:8989/callback",
            response_type="code",
            code_challenge=challenge,
            code_challenge_method="S256",
            resource=resource,
            scope="read write hidden_read hidden_write",
            state="migration",
        ),
        follow_redirects=False,
    )
    assert authorization.status_code == 302, authorization.text
    from urllib.parse import urlsplit, parse_qs

    auth_id = parse_qs(urlsplit(authorization.headers["location"]).query)[
        "agent_authorization"
    ][0]
    consent = a.post(
        "/agent/authorizations/" + auth_id,
        json={
            "approve": True,
            "scopes": ["read", "write", "hidden_read", "hidden_write"],
            "days": 1,
        },
    )
    assert consent.status_code == 201, consent.text
    code = parse_qs(urlsplit(consent.json()["redirect"]).query)["code"][0]
    args = dict(
        grant_type="authorization_code",
        client_id=client["client_id"],
        code=code,
        code_verifier=verifier,
        redirect_uri="http://localhost:8989/callback",
        resource=resource,
    )
    invalid = httpx.post(base + "/token", data={**args, "code_verifier": "B" * 64})
    assert invalid.status_code == 400
    issued = httpx.post(base + "/token", data=args)
    assert issued.status_code == 200, issued.text
    tokens = issued.json()
    assert httpx.post(base + "/token", data=args).status_code == 400
    refresh = dict(
        grant_type="refresh_token",
        client_id=client["client_id"],
        refresh_token=tokens["refresh_token"],
        resource=resource,
    )
    renewed = httpx.post(base + "/token", data=refresh)
    assert renewed.status_code == 200, renewed.text
    assert renewed.json()["refresh_token"] != tokens["refresh_token"]
    assert httpx.post(base + "/token", data=refresh).status_code == 400
    # 动态客户端元数据没有用户外键，显式仅清理本次注册的随机客户端。
    with transaction() as s:
        row = s.get(AgentClient, client["client_id"])
        if row:
            s.delete(row)
