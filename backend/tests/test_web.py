"""前端托管契约：不连接 MySQL，临时资源由 pytest 管理。"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.web import install_web


def make_app(directory):
    async def protected(request):
        return JSONResponse({"service": request.url.path}, status_code=401)

    paths = [
        "/api/probe",
        "/mcp",
        "/authorize",
        "/token",
        "/register",
        "/revoke",
        "/.well-known/oauth-authorization-server",
        "/.well-known/oauth-protected-resource/mcp",
    ]
    app = FastAPI(routes=[Route(p, protected, methods=["GET", "POST"]) for p in paths])
    # 使用应用现有错误处理器，确认未知路径和错误方法不会变成 HTML。
    from app.main import routing_error

    app.add_exception_handler(HTTPException, routing_error)
    assert install_web(app, directory)
    return app, paths


def bundle(tmp_path):
    directory = tmp_path / "public"
    (directory / "assets").mkdir(parents=True)
    (directory / "index.html").write_text(
        "<html>WorthPath static test</html>", encoding="utf8"
    )
    (directory / "assets/app.js").write_text(
        "window.worthpath = true;", encoding="utf8"
    )
    return directory


def test_missing_bundle_keeps_api_only(tmp_path):
    app = FastAPI()
    app.add_api_route("/api/probe", lambda: {"ok": True})
    assert not install_web(app, tmp_path / "missing")
    with TestClient(app) as client:
        assert client.get("/").status_code == 404
        assert client.get("/api/probe").json() == {"ok": True}


def test_pages_query_head_and_cache(tmp_path):
    app, _ = make_app(bundle(tmp_path))
    with TestClient(app) as client:
        for path in [
            "/",
            "/?agent_operation=fixture",
            "/agent/authorize?agent_authorization=fixture",
            "/agent/operation",
        ]:
            response = client.get(path)
            assert response.status_code == 200
            assert "text/html" in response.headers["content-type"]
            assert response.headers["cache-control"] == "no-store"
            assert "WorthPath static test" in response.text
        response = client.head("/")
        assert response.status_code == 200 and response.content == b""
        assert client.post("/").status_code == 404
        assert (
            client.get("/agent/operation/", follow_redirects=False).status_code == 404
        )


def test_services_and_missing_paths_never_become_html(tmp_path):
    app, paths = make_app(bundle(tmp_path))
    with TestClient(app) as client:
        for path in paths:
            for method in ["GET", "POST"]:
                response = client.request(method, path)
                assert response.status_code == 401
                assert response.json() == {"service": path}
        for path in [
            "/assets/missing.js",
            "/api/unknown",
            "/unknown",
            "/public/index.html",
        ]:
            response = client.get(path)
            assert response.status_code == 404
            assert "text/html" not in response.headers.get("content-type", "")


def test_assets_and_traversal_do_not_expose_private_files(tmp_path):
    directory = bundle(tmp_path)
    (tmp_path / "private.txt").write_text("private-static-fixture", encoding="utf8")
    app, _ = make_app(directory)
    with TestClient(app) as client:
        response = client.get("/assets/app.js")
        assert (
            response.status_code == 200 and response.text == "window.worthpath = true;"
        )
        assert client.head("/assets/app.js").content == b""
        for path in ["/assets/%2e%2e/%2e%2e/private.txt", "/.env", "/assets/"]:
            response = client.get(path)
            assert response.status_code == 404
            assert "private-static-fixture" not in response.text
