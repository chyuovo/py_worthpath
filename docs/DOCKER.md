# 单镜像构建、推送与部署

镜像内置前端 dist，FastAPI 在 3100 端口提供网页、API、MCP/OAuth；域名为 https://worthpath.chyuovo.top。

## 1. 本地构建和上传（PowerShell）

```powershell
cd E:\py_worthpath
docker login git.chyuovo.top
docker build -t git.chyuovo.top/chyuovo/py_worthpath:latest .
docker push git.chyuovo.top/chyuovo/py_worthpath:latest
```

Node 只在构建阶段使用，运行镜像只保留 Python、生产依赖和 dist。构建机与服务器 CPU 架构应一致。Compose 只拉取和启动镜像，不负责构建。

## 2. 服务器固定目录

```sh
sudo install -d -m 750 -o 1000 -g 1000 /opt/docker/py_worthpath /opt/docker/py_worthpath/data/icons /opt/docker/py_worthpath/runtime /opt/docker/py_worthpath/backups
cd /opt/docker/py_worthpath
```

将 compose.yaml 放在该目录；生产配置保存为 /opt/docker/py_worthpath/.env.docker。使用已部署的生产 MySQL 配置，不用本地测试配置覆盖。

```sh
chmod 600 /opt/docker/py_worthpath/.env.docker
docker network inspect worthpath
```

所有宿主机挂载均使用绝对路径：

- /opt/docker/py_worthpath/data/icons → /app/data/icons
- /opt/docker/py_worthpath/runtime → /app/runtime
- /opt/docker/py_worthpath/backups → /app/backups

容器沿用 UID/GID 1000、外部网络 worthpath、host.docker.internal:host-gateway、127.0.0.1:3100、768m 内存和 0.5 CPU。MySQL 仍需监听容器可达接口，并允许该网络来源。

外部网络 worthpath 保持现有配置，不重新创建。

## 3. 拉取、检查与启动

```sh
cd /opt/docker/py_worthpath
docker login git.chyuovo.top
docker compose config --quiet
docker compose pull app
docker compose run --rm app python scripts/database.py backup
docker compose run --rm app alembic upgrade head
docker compose run --rm app python scripts/database.py check
docker compose up -d --no-build app
docker compose ps
docker compose logs --tail 100 app
```

日常更新无需接管或重新初始化数据库。仅有新结构版本时，先备份并审查，再执行 Alembic upgrade。

## 4. HTTPS 与日常更新

现有 HTTPS Nginx 将所有路径代理到 http://127.0.0.1:3100，保留 Host 和 X-Forwarded-Proto、关闭缓冲、上传上限设为 513m；不再使用 root/alias/try_files 托管前端。

```sh
nginx -t && nginx -s reload
curl -f https://worthpath.chyuovo.top/api/health
curl -I https://worthpath.chyuovo.top/
docker compose pull app
docker compose run --rm app python scripts/database.py backup
docker compose run --rm app alembic upgrade head
docker compose run --rm app python scripts/database.py check
docker compose up -d --no-build app
```

停止使用 `docker compose stop app`。latest 会被覆盖，更新前可给旧镜像另加回退标签；不执行 Git push。

共享图标管理：电脑端主菜单进入“管理员后台”，可搜索、按状态筛选、软删除和恢复。下架不删除图片，不影响已有账户显示，普通用户无法管理。手机端保留设置分类中的入口。

本次版本 `0002_icon_soft_delete` 仅为 Icon 表新增可空的 deletedAt 字段与查询索引；首次使用新镜像前必须按上面命令备份并执行 upgrade，不能用 stamp 跳过。备份命令会自动验证 gzip、摘要与表数据条数；失败时停止更新。
