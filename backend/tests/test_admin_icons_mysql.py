"""真实 MySQL 回归：仅创建、清理本测试的 UUID 标记账号和图标。"""

import io
import secrets
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import delete

from app import main
from app.auth import hash_password
from app.common import today
from app.database import transaction
from app.models import Icon, User


@pytest.fixture
def icon_clients(monkeypatch, tmp_path):
    monkeypatch.setenv("API_ALLOWED_HOSTS", "testserver")
    monkeypatch.setenv("ICON_STORAGE_DIR", str(tmp_path / "icons"))
    monkeypatch.setattr(main, "origins", ["http://localhost:5173"])
    clients, users, icon_ids = [], [], []
    try:
        for role in ("admin", "user", "readonly"):
            username, password = (
                "icon_test_" + uuid4().hex[:16],
                secrets.token_urlsafe(24),
            )
            with transaction(write=True) as s:
                user = User(
                    username=username,
                    passwordHash=hash_password(password),
                    role=role,
                    mustChangePassword=False,
                )
                s.add(user)
                s.flush()
                users.append(user.id)
            # 不进入 lifespan，不启动行情、清理或其他后台任务；认证和接口使用真实数据库。
            client = TestClient(main.app, headers={"Origin": "http://localhost:5173"})
            clients.append(client)
            assert (
                client.post(
                    "/api/auth/login", json={"username": username, "password": password}
                ).status_code
                == 201
            )
        yield clients, icon_ids
    finally:
        for client in clients:
            client.close()
        with transaction(write=True) as s:
            s.execute(delete(User).where(User.id.in_(users)))
            s.execute(delete(Icon).where(Icon.id.in_(icon_ids)))


def upload(client, ids, shared=True):
    image = io.BytesIO()
    Image.new("RGB", (20, 20), (13, 150, 91)).save(image, format="PNG")
    name = "测试共享图标_" + uuid4().hex
    response = client.post(
        "/api/icons/upload",
        data={"name": name, "shared": str(shared).lower(), "confirmed": "true"},
        files={"file": ("icon.png", image.getvalue(), "image/png")},
    )
    assert response.status_code == 201
    ids.append(response.json()["id"])
    return response.json(), image.getvalue()


def position(icon_id):
    return {
        "name": "专用图标测试账户",
        "kind": "account",
        "side": "asset",
        "category": "other",
        "currency": "CNY",
        "amount": "1.23",
        "date": today(),
        "iconId": icon_id,
    }


def test_shared_icon_delete_restore_and_existing_reference(icon_clients):
    (admin, owner, readonly), ids = icon_clients
    icon, raw = upload(owner, ids)
    icon_id = icon["id"]
    path = "/api/admin/icons/" + icon_id
    created = owner.post("/api/positions", json=position(icon_id))
    assert created.status_code == 201
    image = owner.get("/api/icons/" + icon_id + "/image").content
    assert admin.request("DELETE", path, json={"confirmed": False}).status_code == 400
    assert owner.request("DELETE", path, json={"confirmed": True}).status_code == 403
    assert readonly.get("/api/admin/icons").status_code == 403
    assert (
        admin.request(
            "DELETE",
            path,
            json={"confirmed": True},
            headers={"Origin": "https://untrusted.invalid"},
        ).status_code
        == 403
    )
    deleted = admin.request("DELETE", path, json={"confirmed": True})
    assert deleted.status_code == 200 and deleted.json()["deletedAt"]
    assert (
        admin.request("DELETE", path, json={"confirmed": True}).json()["deletedAt"]
        == deleted.json()["deletedAt"]
    )
    assert owner.get("/api/icons", params={"q": icon["name"]}).json()["total"] == 0
    assert (
        admin.get(
            "/api/admin/icons", params={"q": icon["name"], "status": "deleted"}
        ).json()["items"][0]["id"]
        == icon_id
    )
    assert owner.get("/api/icons/" + icon_id + "/image").content == image
    assert readonly.get("/api/icons/" + icon_id + "/image").content == image
    assert owner.post("/api/positions", json=position(icon_id)).status_code == 400
    assert (
        owner.patch(
            "/api/positions/" + created.json()["id"],
            json={"name": "保留旧图标", "category": "other", "iconId": icon_id},
        ).status_code
        == 200
    )
    duplicate = owner.post(
        "/api/icons/upload",
        data={"name": icon["name"], "shared": "true", "confirmed": "true"},
        files={"file": ("icon.png", raw, "image/png")},
    )
    assert duplicate.status_code == 409
    assert owner.post(path + "/restore", json={"confirmed": True}).status_code == 403
    restored = admin.post(path + "/restore", json={"confirmed": True})
    assert restored.status_code == 201 and restored.json()["deletedAt"] is None
    assert owner.get("/api/icons", params={"q": icon["name"]}).json()["total"] == 1
    assert owner.post("/api/positions", json=position(icon_id)).status_code == 201


def test_private_icons_and_invalid_queries_are_protected(icon_clients):
    (admin, owner, _readonly), ids = icon_clients
    icon, _ = upload(owner, ids, shared=False)
    path = "/api/admin/icons/" + icon["id"]
    assert admin.request("DELETE", path, json={"confirmed": True}).status_code == 404
    assert admin.post(path + "/restore", json={"confirmed": True}).status_code == 404
    assert admin.get("/api/icons/" + icon["id"] + "/image").status_code == 404
    assert (
        admin.get("/api/admin/icons", params={"status": "invalid"}).status_code == 400
    )
    assert admin.get("/api/admin/icons", params={"limit": 101}).status_code == 400
    assert admin.get("/api/admin/icons", params={"offset": -1}).status_code == 400
    assert (
        admin.get(
            "/api/admin/icons", params={"q": icon["name"], "status": "all"}
        ).json()["total"]
        == 0
    )
