# 保留必要的高风险回归：管理员撤销权限，以及跨线程 Decimal 精度和原序列化。
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal, localcontext
from datetime import datetime
import uuid, httpx
from sqlalchemy import delete
from test_core_mysql import users, ROOT_URL
from app.common import dec, fixed, decimal_string
from app.calculation import totals
from app.database import transaction
from app.models import User


def test_decimal_precision_and_original_serialization():
    assert decimal_string(Decimal("0.00000001")) == "1e-8"
    assert decimal_string(Decimal("0.000001")) == "0.000001"
    assert fixed(Decimal("-0")) == "0"
    holding = dict(
        id="precision",
        name="precision",
        kind="account",
        side="asset",
        currency="USD",
        revisions=[
            dict(
                id="revision",
                amount="9999999999999999.99999999",
                effectiveDate=datetime(2026, 9, 1),
                sequence=1,
                notes="",
                reason="initial",
            )
        ],
    )
    rate = dict(
        currency="USD",
        baseCurrency="CNY",
        date=__import__("datetime").date(2026, 9, 1),
        rate="999999999999.999999999999",
        source="manual",
    )
    with localcontext() as context:
        context.prec = 50
        expected = fixed(dec(holding["revisions"][0]["amount"]) * dec(rate["rate"]), 2)
    with ThreadPoolExecutor(max_workers=1) as executor:
        actual = executor.submit(
            totals, [holding], [rate], "CNY", "2026-09-01"
        ).result()
    assert actual["assets"] == expected and actual["net"] == expected


def test_admin_roles_first_password_and_revocation(users):
    admin, other = users
    actor = admin.get("/auth/me").json()["id"]
    with transaction() as s:
        user = s.get(User, actor)
        assert user.username.startswith("py_migration_")
        user.role = "admin"
    username = "py_migration_role_" + uuid.uuid4().hex[:12]
    password = "MigrationRole!23456"
    user_id = None
    client = httpx.Client(
        base_url=ROOT_URL + "/api",
        headers={"Origin": "http://localhost:5173"},
        timeout=20,
    )
    try:
        created = admin.post(
            "/admin/users", json=dict(username=username, password=password, role="user")
        )
        assert created.status_code == 201, created.text
        user_id = created.json()["id"]
        assert (
            client.post(
                "/auth/login", json=dict(username=username, password=password)
            ).status_code
            == 201
        )
        assert client.get("/positions").status_code == 403
        changed = client.patch(
            "/auth/credentials",
            json=dict(currentPassword=password, newPassword="MigrationRoleNew!23456"),
        )
        assert changed.status_code == 200, changed.text
        token = client.post(
            "/agent/tokens",
            json=dict(
                name="role regression",
                scopes=["read", "write"],
                days=1,
                password="MigrationRoleNew!23456",
            ),
        )
        assert token.status_code == 201, token.text
        assert (
            admin.patch(
                "/admin/users/" + user_id, json={"role": "readonly"}
            ).status_code
            == 200
        )
        assert client.get("/positions").status_code == 401
        assert (
            httpx.post(
                ROOT_URL + "/mcp",
                headers={"Authorization": "Bearer " + token.json()["token"]},
                json={},
            ).status_code
            == 401
        )
        assert (
            client.post(
                "/auth/login",
                json=dict(username=username, password="MigrationRoleNew!23456"),
            ).status_code
            == 201
        )
        assert client.post("/positions", json={}).status_code == 403
        assert (
            admin.patch("/admin/users/" + user_id, json={"banned": True}).status_code
            == 200
        )
        assert client.get("/auth/me").status_code == 401
        assert (
            admin.patch("/admin/users/" + actor, json={"banned": True}).status_code
            == 403
        )
    finally:
        client.close()
        if user_id:
            with transaction() as s:
                s.execute(
                    delete(User).where(User.id == user_id, User.username == username)
                )
