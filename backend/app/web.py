# 与原项目 web.ts 对齐：仅托管明确页面及 Vite assets，不吞掉服务请求。
import os
from pathlib import Path

from fastapi import FastAPI
from starlette.responses import FileResponse
from starlette.routing import Mount, Route, Router
from starlette.staticfiles import StaticFiles


def install_web(app: FastAPI, directory: Path | None = None) -> bool:
    directory = Path(
        directory
        or os.getenv("WEB_DIST_DIR")
        or Path(__file__).resolve().parents[1] / "public"
    )
    index = directory / "index.html"
    if not index.is_file():
        # 分开开发时没有打包目录，仍保持原有纯 API 启动方式。
        return False

    async def page(request):
        return FileResponse(
            index, media_type="text/html", headers={"Cache-Control": "no-store"}
        )

    routes = [
        Route(path, page, methods=["GET", "HEAD"])
        for path in ("/", "/agent/authorize", "/agent/operation")
    ]
    if (directory / "assets").is_dir():
        routes.append(
            Mount("/assets", StaticFiles(directory=directory / "assets", html=False))
        )
    # 在所有 API/OAuth/MCP 路由之后挂载；未知路径、缺失资源均返回 404。
    app.mount("/", Router(routes=routes, redirect_slashes=False), name="frontend")
    return True
