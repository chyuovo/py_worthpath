# syntax=docker/dockerfile:1
# 构建与运行使用相同 Python，虚拟环境中的原生扩展保持兼容。
FROM python:3.14.7-slim-bookworm@sha256:82bc3c539b8813ada9d68c63b40158fa002f7f33de9bf3312a3dfdc0620dff56 AS builder
COPY --from=ghcr.io/astral-sh/uv:0.12.13@sha256:b485bd65cc2cf1c9a93b3554012c9c3778cf7b1b5fd3d3096ce9e1226c97e1e6 /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
WORKDIR /app
COPY pyproject.toml uv.lock ./
# 缓存只用于构建；pytest、ruff 和 uv 不进入最终运行镜像。
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --python /usr/local/bin/python --frozen --no-dev --no-install-project --no-editable

FROM python:3.14.7-slim-bookworm@sha256:82bc3c539b8813ada9d68c63b40158fa002f7f33de9bf3312a3dfdc0620dff56 AS runtime
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
RUN groupadd --gid 10001 worthpath \
    && useradd --uid 10001 --gid worthpath --no-create-home --shell /usr/sbin/nologin worthpath \
    && mkdir -p runtime data/icons backups \
    && chown -R worthpath:worthpath runtime data backups
COPY --from=builder /app/.venv /app/.venv
COPY app ./app
COPY assets ./assets
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts/database.py scripts/seed_icons.py scripts/run.py ./scripts/
USER 10001:10001
EXPOSE 3100
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:3100/api/health', timeout=3)"]
# 文件票据在内存中，保持单进程，避免重复行情任务及票据跨进程丢失。
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3100", "--proxy-headers", "--forwarded-allow-ips", "*"]
