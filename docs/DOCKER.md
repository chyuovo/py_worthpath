# 前端交给现有 Nginx，仅后端使用 Docker

需要 Node.js 22.12+、pnpm 11.19.0、Docker Engine 和 Compose v2+。MySQL 继续使用现有服务。

## 1. 配置

```powershell
cd E:\py_worthpath
if (!(Test-Path deploy/.env)) { Copy-Item deploy/.env.example deploy/.env }
if (!(Test-Path backend/.env.docker)) { Copy-Item backend/.env backend/.env.docker }
notepad deploy/.env
notepad backend/.env.docker
```

`deploy/.env` 填实际的 PUBLIC_ORIGIN 和 PUBLIC_HOST；后端默认映射到宿主机 `127.0.0.1:3100`。已有配置若包含 WEB_BIND/WEB_PORT，请按示例改用 BACKEND_BIND/BACKEND_PORT。

`backend/.env.docker` 沿用业务及 MySQL 凭据，将数据库主机改为容器可达地址：Windows 宿主机可用 `host.docker.internal`，NAS/独立 MySQL 填可达地址。两个真实环境文件都不进入 Git 或镜像。

## 2. 构建与打包（PowerShell）

```powershell
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend build
docker compose --env-file deploy/.env config --quiet
docker compose --env-file deploy/.env build --pull
New-Item -ItemType Directory -Force exports | Out-Null
tar -czf exports/worthpath-frontend.tar.gz -C frontend dist
docker save -o exports/worthpath-backend.tar py-worthpath-backend:0.1.0
```

只生成一个后端镜像；前端交付 dist 压缩包。后端不带 uv、开发依赖、测试或构建缓存。构建机与目标机器 CPU 架构应一致（amd64/arm64）。

## 3. 服务器 / NAS 上启动

安全传输两个包、`compose.yaml`、`deploy/nginx-worthpath.conf`、`deploy/.env`、`backend/.env.docker`，保持配置目录结构，按服务器地址调整环境变量。在目标项目目录运行：

```sh
mkdir -p /srv/worthpath
tar -xzf worthpath-frontend.tar.gz -C /srv/worthpath
docker load -i worthpath-backend.tar
docker compose --env-file deploy/.env run --rm --no-deps backend python scripts/database.py check
docker compose --env-file deploy/.env up -d --no-build
```

已有数据库不重复迁移；其他旧库接管或空库初始化见 [README](../README.md)，容器中用上述 run 前缀替代 uv run。切换前停止旧后端，避免重复后台任务。

## 4. 接入现有 Nginx

用 [nginx-worthpath.conf](../deploy/nginx-worthpath.conf) 替换现有 HTTPS 站点的 root/index/location 部分，保留 listen、server_name 和证书配置。目录为 `/srv/worthpath/dist`，后端为 `http://127.0.0.1:3100`；修改端口时同步调整这两处配置。

```sh
nginx -t && nginx -s reload
curl -f https://你的域名/api/health
```

如果已有 Nginx 本身是容器：将 dist 挂载到其站点目录，代理地址改为可达的宿主机 IP，并将 BACKEND_BIND 改为该 IP；127.0.0.1 在 Nginx 容器内指向它自身。HTTP 验证时设 ALLOW_HTTP=true、COOKIE_SECURE=false，并同步修改 PUBLIC_ORIGIN/PUBLIC_HOST。

## 5. 查看与更新

```sh
docker compose --env-file deploy/.env ps
docker compose --env-file deploy/.env logs --tail 100 -f
docker image ls py-worthpath-backend
```

曾用双容器版本时，首次 up 增加 `--remove-orphans` 清理旧前端容器。更新前端只需重新构建并替换 dist；更新后端重新导入镜像后执行 up -d --no-build。停止用 compose down，不加 -v，保留数据卷。

本机 Docker 引擎未启动：已校验 Compose 和路由配置；容器构建、现有 Nginx 配置测试及端到端访问需在目标环境执行。
