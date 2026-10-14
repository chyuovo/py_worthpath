```shell
# 首次登录，建议使用有包写入权限的访问令牌
docker login git.chyuovo.top
# 版本号
# docker build -t git.chyuovo.top/chyuovo/py_worthpath:v1.0.1 .
# docker push git.chyuovo.top/chyuovo/py_worthpath:v1.0.1
# 只推送最新
docker build -t git.chyuovo.top/chyuovo/py_worthpath:latest .
docker push git.chyuovo.top/chyuovo/py_worthpath:latest
```

### 数据库检查
```shell
cd /opt/docker/py_worthpath
# 查看当前版本和结构；日常更新无需重复接管。
docker compose run --rm app alembic current
docker compose run --rm app python scripts/database.py check
```

已停用表的手动清理见 [DATABASE.md](DATABASE.md)，先部署更新并备份，保留 alembic_version。

### docker
```shell
docker login git.chyuovo.top
# 检查 Compose 配置；成功时不输出内容，失败时显示错误。
docker compose config --quiet
# 下载 app 服务配置的镜像，例如最新的 latest。
docker compose pull app
# 启动临时容器，核对数据库表结构；不修改数据库，结束后删除临时容器。
docker compose run --rm app python scripts/database.py check
# 使用已有镜像在后台启动或更新应用，不在服务器上构建镜像。
docker compose up -d --no-build app
# 查看容器状态、端口及健康状态。
docker compose ps
# 查看应用最近 100 行日志，用于排查启动错误。
docker compose logs --tail 100 app
```