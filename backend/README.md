# 后端

本目录为独立 FastAPI 项目，不依赖前端、Node.js、pnpm 或原 NestJS 项目。

```powershell
cd E:\py_worthpath\backend
uv sync --frozen
# 已迁移的本地 .env 不要覆盖
uv run python scripts/database.py check
uv run python scripts/run.py
```

默认端口 3100，OpenAPI 文档位于 /api/docs，MCP 位于 /mcp。环境配置由本目录 .env 读取。安装、数据库接管、空库初始化和后续迁移步骤见上级 README。

目录：app 为 HTTP、认证、业务服务和 MCP/OAuth；alembic 为唯一结构迁移工具；assets 为内置图标；scripts 为启动、数据库备份与图标初始化；tests 为必要的真实 MySQL 回归。金额使用 Decimal，数据库保留 UTC，业务日期使用 UTC+8。

测试前启动 API；使用 uv run pytest -q，必要时通过 TEST_API_URL 指向临时验收端口。默认管理员只在数据库没有管理员且显式配置强凭据时初始化，绝不覆盖现有用户。

整库恢复仅允许明确准备的空 MySQL：先核实本地 .env 的目标连接，再运行下列命令。程序拒绝对有任何表的数据库恢复，不提供强制覆盖开关。

```powershell
uv run python scripts/database.py verify .\backups\YOUR_BACKUP.sql.gz
uv run python scripts/database.py restore-empty .\backups\YOUR_BACKUP.sql.gz
uv run python scripts/database.py check
uv run python scripts/database.py adopt
```

失败时保留现场及原备份，不自动删表。恢复到不同操作系统的 MySQL 前，需人工核对 lower_case_table_names 及原备份表名大小写策略。
