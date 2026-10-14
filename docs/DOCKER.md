# 单镜像打包与部署

一个 Python Slim 镜像内置前端 dist，FastAPI 在 3100 端口提供网页、API、MCP/OAuth。Node 仅在构建阶段使用；不再单独部署前端或让 Nginx 读取 dist。

## 1. 本地配置与打包（PowerShell）

```powershell
cd E:\py_worthpath
if (!(Test-Path backend/.env.docker)) { Copy-Item backend/docker.env.example backend/.env.docker }
notepad backend/.env.docker
docker compose config --quiet
docker compose build --pull app
New-Item -ItemType Directory -Force exports | Out-Null
docker save -o exports/py-worthpath.tar py-worthpath:0.1.0
```

域名固定为 https://worthpath.chyuovo.top，MCP 为 https://worthpath.chyuovo.top/mcp。本地真实配置已保留原数据库凭据；模板中的占位值需要填写。构建机与服务器 CPU 架构应一致。

## 2. 沿用原项目的服务器设置

已只读核对 E:\WorthPath 的实际 compose.yaml：

- 外部网络 worthpath；原文档为 172.30.50.0/24，网关 172.30.50.1，网桥 br-worthpath。新配置引用已有网络，不重建它。
- host.docker.internal:host-gateway 访问宿主机 MySQL；业务库、账号和密码不自动更换。MySQL 必须监听容器可达接口，并保留原防火墙及账号来源授权。
- 宿主机图标目录 /opt/docker/worthpath/data/icons；沿用 UID/GID 1000，不递归修改既有文件。
- 端口 127.0.0.1:3100:3100；内存 768m、CPU 0.5、30 秒停止宽限及日志轮转。
- 原服务器环境文件 /opt/docker/worthpath/.env.production 可继续使用，不覆盖其凭据。

## 3. 服务器准备与启动（Linux）

传输镜像包和 compose.yaml 到目标项目目录。切换前由你停止旧应用，避免端口冲突及重复后台任务。

```sh
export WORTHPATH_ENV_FILE=/opt/docker/worthpath/.env.production
docker network inspect worthpath
sudo install -d -m 750 -o 1000 -g 1000 /opt/docker/worthpath/data/icons
docker load -i py-worthpath.tar
docker compose config --quiet
docker compose run --rm app python scripts/database.py check
docker compose up -d --no-build app
docker compose ps
```

已有图标目录不需要重设权限。本地 backend/.env.docker 沿用迁移测试连接；正式部署使用上述原生产文件。若没有生产配置，从 backend/docker.env.example 创建新文件并填写正式数据库凭据，不用开发或测试配置覆盖生产。

若网络不存在，先确认该子网未被占用，再按原规划创建一次：

```sh
docker network create --driver bridge --subnet 172.30.50.0/24 --gateway 172.30.50.1 --opt com.docker.network.bridge.name=br-worthpath worthpath
```

已有库尚未接管 Alembic 时，先执行 `docker compose run --rm app python scripts/database.py adopt`；它先核对结构并备份，才标记明确基线。已接管的库不重复初始化；空库流程见 README。

## 4. HTTPS 代理

沿用现有 HTTPS 站点，所有路径均反向代理到 127.0.0.1:3100，不再用 root/alias/try_files 托管前端。保留外部 Host 和 X-Forwarded-Proto，关闭代理缓冲，上传上限设为 513m。若已有 Nginx 本身是容器，接入 worthpath 网络并将上游改为 app:3100，保留外部 Host。

```sh
nginx -t && nginx -s reload
curl -f https://worthpath.chyuovo.top/api/health
curl -I https://worthpath.chyuovo.top/
docker compose logs --tail 100 app
```

## 5. 更新与停止

```sh
docker load -i py-worthpath.tar
docker compose up -d --no-build --force-recreate app
docker compose stop app
```

前后端更新都重新构建这一个镜像；不再传输独立 dist 包。不要加 down -v 删除数据卷，不自动执行旧 Prisma 工具，也不推送原项目镜像标签。

本机 Docker 引擎未启动：Compose、前端构建及静态托管测试可本地验证；镜像构建、服务器网络/MySQL监听、目录权限和真实 HTTPS/MCP 仍需在目标环境核验。
