# 数据库维护

旧项目迁移已结束，`database.py adopt`、旧结构对照和旧模型参考已删除。保留正常业务、网页备份导入、整库备份恢复及 Alembic 版本管理。

## 手动删除已停用表

可清理的表只有：

- `_prisma_migrations`：旧 Prisma 迁移历史，不再被执行或读取。
- `AgentPolicy`：停用的旧授权策略，当前 MCP/OAuth 权限使用 AgentGrant 等表，不读取该表。

先构建并部署本次代码，然后备份当前生产数据库：

```sh
cd /opt/docker/py_worthpath
docker compose run --rm app python scripts/database.py backup
# 将输出的备份文件名替换到下面的命令；备份清单需与 gzip 一起保留。
docker compose run --rm app python scripts/database.py verify /app/backups/YOUR_BACKUP.sql.gz
```

备份校验通过后，在生产 MySQL 客户端中手动执行。先核对选中的数据库和实际表名：

```sql
SELECT DATABASE();
SHOW TABLES;
SELECT TABLE_NAME, CONSTRAINT_NAME, REFERENCED_TABLE_NAME
FROM information_schema.KEY_COLUMN_USAGE
WHERE REFERENCED_TABLE_SCHEMA = DATABASE()
  AND LOWER(REFERENCED_TABLE_NAME) IN ('agentpolicy', '_prisma_migrations');
```

上述外键查询应为空；有引用时不要继续。下面采用本地 MySQL 的小写表名，生产若显示 `AgentPolicy`，必须把 `agentpolicy` 替换为实际大小写。删表将永久删除旧策略和旧迁移记录，请保留完整备份。

```sql
DROP TABLE `_prisma_migrations`;
DROP TABLE `agentpolicy`;
```

不要删除 `alembic_version`，不要禁用外键检查，也不要删除其他表。其余 15 张业务表均有运行时用途，空表也可能用于会话、授权、幂等、待确认操作或审计。

清理后只读检查：

```sh
docker compose run --rm app python scripts/database.py check
docker compose run --rm app alembic current
```

已执行的 `0001_existing_schema` 和冻结基线保持不变；不得重新 stamp、重建业务表或修改历史版本。自动生成仅比较模型管理的表，不会自动删除模型外的表。后续真正需要删除其他表时，必须人工审查删除脚本。

本次仅只读核对了本地配置对应数据库，确认以上两表没有入向外键；没有访问生产数据库，也没有执行删表或结构修改。生产仍需执行上述核对。
