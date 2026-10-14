# Docker 打包与部署

前端 Nginx、后端 Python Slim 两个独立镜像，连接现有 MySQL。需要 Docker Engine 和 Compose v2+；以下构建命令在 PowerShell 中执行。

## 1. 准备配置

```powershell
cd E:\py_worthpath
if (!(Test-Path deploy/.env)) { Copy-Item deploy/.env.example deploy/.env }
if (!(Test-Path backend/.env.docker)) { Copy-Item backend/.env backend/.env.docker }
notepad deploy/.env
notepad backend/.env.docker
```

- `deploy/.env`：填写实际的 `PUBLIC_ORIGIN` 和 `PUBLIC_HOST`。默认通过已有 HTTPS 反向代理转发整个站点到 `127.0.0.1:8080`，保留 Host 和 X-Forwarded-Proto；外层 MCP 代理关闭缓冲。
- `backend/.env.docker`：沿用业务配置和 MySQL 凭据，只把数据库主机改为容器可访问的地址。容器中的 localhost 是容器自身；Windows 宿主机 MySQL 可用 `host.docker.internal`，NAS/独立数据库使用其可达地址。不修改原 `backend/.env`。
- 局域网 HTTP 验证：例如地址 `http://NAS_IP:8080`、Host `NAS_IP:8080`，同时设 `WEB_BIND=0.0.0.0`、`ALLOW_HTTP=true`、`COOKIE_SECURE=false`。远程反代访问时也需调整 WEB_BIND。
- 两个真实环境文件只在本地保存，不放进镜像或 Git。

## 2. 构建镜像

```powershell
docker compose --env-file deploy/.env config --quiet
docker compose --env-file deploy/.env build --pull
docker image ls py-worthpath-backend
docker image ls py-worthpath-frontend
```

只安装生产依赖，运行镜像不带 Node 构建工具、uv、测试、缓存或本地虚拟环境。基础镜像已固定版本和摘要。

## 3. 数据库检查与启动

```powershell
docker compose --env-file deploy/.env run --rm --no-deps backend python scripts/database.py check
docker compose --env-file deploy/.env up -d
docker compose --env-file deploy/.env ps
```

本次已接管的数据库不重复迁移。其他旧库接管和空库初始化见 [README](../README.md)；容器中用 `docker compose --env-file deploy/.env run --rm --no-deps backend` 替代 `uv run`。切换前由你停止旧后端，避免两套后台任务同时写库。

## 4. 打包给 NAS / 服务器

```powershell
New-Item -ItemType Directory -Force exports | Out-Null
docker save -o exports/worthpath-images.tar py-worthpath-backend:0.1.0 py-worthpath-frontend:0.1.0
```

将镜像包、`compose.yaml`、`deploy/.env`、`backend/.env.docker` 安全传到目标机器，保持目录结构，按目标地址调整配置。构建机和目标机 CPU 架构应一致（amd64/arm64）。

在目标机器的项目目录执行：

```sh
docker load -i worthpath-images.tar
docker compose --env-file deploy/.env up -d --no-build
docker compose --env-file deploy/.env ps
```

## 5. 日常维护

```powershell
docker compose --env-file deploy/.env logs --tail 100 -f
docker system df -v
docker compose --env-file deploy/.env down
```

更新时重新构建或导入镜像，再执行 `up -d --no-build`。停止时不要加 `-v`，以保留图标、临时运行目录和备份卷；业务数据始终在外部 MySQL。

本机 Docker 引擎未运行：已核实基础镜像仓库及配置，实际构建、启动和最终镜像体积需在引擎启动后验证。
