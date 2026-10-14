# syntax=docker/dockerfile:1
# Node 仅用于构建，最终镜像只有 Python、生产依赖和静态文件。
FROM node:24.21.0-alpine3.23@sha256:9ec4a2e289874ed0d722e1772ec2de45d2801541db8612f3638b26f128c69ac2 AS web
WORKDIR /build/web
RUN npm install --global pnpm@11.19.0
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN --mount=type=cache,target=/pnpm/store pnpm install --frozen-lockfile --store-dir /pnpm/store
COPY frontend/ ./
RUN pnpm build && test -s dist/index.html

FROM python:3.14.7-slim-bookworm@sha256:82bc3c539b8813ada9d68c63b40158fa002f7f33de9bf3312a3dfdc0620dff56 AS dependencies
COPY --from=ghcr.io/astral-sh/uv:0.12.13@sha256:b485bd65cc2cf1c9a93b3554012c9c3778cf7b1b5fd3d3096ce9e1226c97e1e6 /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --python /usr/local/bin/python --frozen --no-dev --no-install-project --no-editable

FROM python:3.14.7-slim-bookworm@sha256:82bc3c539b8813ada9d68c63b40158fa002f7f33de9bf3312a3dfdc0620dff56 AS runtime
ENV PATH="/app/.venv/bin:${PATH}" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    WEB_DIST_DIR=/app/public ICON_STORAGE_DIR=/app/data/icons
WORKDIR /app
# 沿用原项目 UID/GID 1000，兼容已有图标绑定目录的权限。
RUN groupadd --gid 1000 worthpath \
    && useradd --uid 1000 --gid worthpath --no-create-home --shell /usr/sbin/nologin worthpath \
    && mkdir -p runtime data/icons backups \
    && chown -R worthpath:worthpath runtime data backups
COPY --from=dependencies /app/.venv /app/.venv
COPY backend/app ./app
COPY backend/assets ./assets
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./
COPY backend/scripts/database.py backend/scripts/seed_icons.py backend/scripts/run.py ./scripts/
COPY --from=web /build/web/dist ./public
USER 1000:1000
EXPOSE 3100
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:3100/api/health', timeout=3)"]
# 单进程保留 MCP 文件票据与后台任务的原有语义。
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3100", "--proxy-headers", "--forwarded-allow-ips", "*"]
