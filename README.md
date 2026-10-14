# py_worthpath

WorthPath 后端已迁移为 Python FastAPI、SQLAlchemy 和 Alembic，继续使用原测试 MySQL。React 前端及资源保留。所有迁移内容均在本目录，源目录 E:\WorthPath 保持只读。

## 两个独立项目

- `frontend/`：React 19、Vite 7，独立 package.json、pnpm-lock.yaml 和 .env。
- `backend/`：FastAPI、SQLAlchemy 2、Alembic，独立 pyproject.toml、uv.lock 和 .env。
- 两端只通过 HTTP 通信；前端不读取后端 .env，后端不需要 Node.js、pnpm 或前端源码。
- `docs/MIGRATION.md`：页面、组件、68 个 HTTP 路由、16 个模型、历史迁移和集成清单。
- Docker 打包与部署命令见 [docs/DOCKER.md](docs/DOCKER.md)，单镜像内置前端 dist，由 FastAPI 统一托管，宿主机 Nginx 只做 HTTPS 代理，MySQL 外置。

已验证环境：Windows PowerShell，Python 3.14.7、Node.js 24.21.0、pnpm 11.19.0、MySQL 8.0.45。后端要求 Python 3.12+，前端要求 Node.js 22.12+。

## 首次安装

后端：

```powershell
cd E:\py_worthpath\backend
uv sync --frozen
# 已有本地 .env 时不要覆盖
if (!(Test-Path .env)) { Copy-Item .env.example .env }
uv run python scripts/database.py check
```

本次迁移已在 backend/.env 中保留原测试连接，未显示或提交凭据。新安装请自行填写真实测试 MySQL 连接及管理员配置；不要将示例占位值作为真实凭据。现有管理员、密码哈希、会话、项目 UUID 和历史均兼容。

前端：

```powershell
cd E:\py_worthpath\frontend
pnpm install --frozen-lockfile
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

## 日常启动

分别使用两个 PowerShell 窗口。

```powershell
cd E:\py_worthpath\backend
uv run python scripts/run.py
# 开发时可使用：uv run python scripts/run.py --reload
```

```powershell
cd E:\py_worthpath\frontend
pnpm dev
```

网页默认 http://localhost:5173，API 默认 http://localhost:3100/api，接口文档 http://localhost:3100/api/docs，MCP 默认 http://localhost:3100/mcp。端口、Host、Origin、Cookie、MCP_PUBLIC_URL 和 MCP_WEB_URL 沿用原配置。前端只需将自己的 WEB_API_PROXY 指向后端地址。

验收曾使用 API 3101、迁移前端 5174、原前端只读副本 5175，避免与正常服务冲突。这些临时端口不是默认启动配置。

## 已有 MySQL 如何接管

本次已经完成接管到明确 revision `0001_existing_schema`，不要重复执行原 Prisma 工具。既有业务表没有结构修改，仅新增 Alembic 的版本表 `alembic_version`。

在其他现有且结构匹配的数据库上接管：

```powershell
cd E:\py_worthpath\backend
uv run python scripts/database.py check
uv run python scripts/database.py adopt
uv run alembic current
uv run alembic check
```

adopt 先比对冻结的完整结构，再生成一致性备份、校验压缩内容和摘要及逐表条数，重新核对结构，最后只 stamp 到明确基线。结构不匹配或备份失败时停止。不要把未执行的 head 直接标记完成，不要对现有表运行基线建表。

## 空数据库初始化

先由数据库管理员明确准备空 MySQL 数据库，并在本地 .env 填写该连接；程序不会自动创建、切换或删除数据库。

```powershell
cd E:\py_worthpath\backend
uv run python scripts/database.py backup
uv run alembic upgrade head
uv run python scripts/seed_icons.py
uv run python scripts/run.py
```

基线可创建全部 16 张业务表及索引、外键、中文注释和默认值。首次启动仅在不存在管理员时初始化，要求显式配置 ADMIN_USERNAME 和强 ADMIN_PASSWORD，并保留首次登录必须改密流程；不会回退到公开默认密码，也不会覆盖已有账号。空库实际建表和数据库整库恢复的验证边界见 docs/VALIDATION.md。

## 后续修改字段

```powershell
cd E:\py_worthpath\backend
uv run python scripts/database.py backup
# 修改 app/models.py 后生成候选迁移
uv run alembic revision --autogenerate -m "describe schema change"
# 人工审查 alembic/versions 中的脚本，特别是删除、重命名、精度和类型转换
uv run alembic upgrade head
uv run alembic check
```

Windows MySQL 的小写表名比较已处理；原 Prisma 迁移历史保留在库中作审计，Alembic 不会将它生成为删除目标。不可变基线位于 backend/alembic/baseline_schema.py，后续修改模型不会改变旧基线。

## 备份、恢复和故障处理

```powershell
cd E:\py_worthpath\backend
uv run python scripts/database.py backup
uv run python scripts/database.py verify .\backups\YOUR_BACKUP.sql.gz
```

整库备份和对应清单只保存在忽略的 backend/backups 中，包含敏感数据，不提交 Git。验证会解压校验、核对摘要、CREATE 表数量和逐表 INSERT 数量。数据库恢复只面向明确准备的空库，避免覆盖既有业务数据；具体命令见后端 README。

普通用户的数据迁移使用网页 ZIP v9 备份：上传预览、本人确认、事务追加，保留原有项目，不覆盖历史；图标恢复为私有。清空数据必须先下载当前备份且账目指纹仍一致。密码、会话和令牌不进入网页备份。

连接失败时检查 MySQL 服务及原隧道、.env、网络白名单和端口，不创建替代数据库。出现状态冲突时重新读取，不修改旧请求的幂等参数。恢复、迁移或自动生成结果不明确时先停止结构写入，保留备份。

## 测试

先启动后端，然后在另一个后端终端执行：

```powershell
cd E:\py_worthpath\backend
uv run pytest -q
uv run alembic check
```

对临时端口的后端测试时设置 TEST_API_URL，例如 `$env:TEST_API_URL = 'http://127.0.0.1:3101/api'`。测试使用真实 MySQL，只创建和清理专用临时用户及其数据。

前端：

```powershell
cd E:\py_worthpath\frontend
pnpm test
pnpm typecheck
pnpm build
```

Git 提交前：

```powershell
cd E:\py_worthpath
python scripts/check_staged.py
git diff --cached --stat
```

具体验收结果、临时配置和未验证内容见 docs/VALIDATION.md。自动公共行情默认开启；回归过程可仅在当前后端进程设置 `$env:WORTHPATH_ENABLE_QUOTES = 'false'`，避免对既有用户执行行情刷新。未永久修改系统 PATH。
