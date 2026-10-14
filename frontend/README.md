# 前端

本目录为独立 React/Vite 项目，不引用后端源码、虚拟环境或配置文件。

```powershell
cd E:\py_worthpath\frontend
pnpm install --frozen-lockfile
if (!(Test-Path .env)) { Copy-Item .env.example .env }
pnpm dev
```

默认网页端口为 5173；本目录 .env 中的 WEB_API_PROXY 指向后端（默认 http://127.0.0.1:3100）。不需要安装 Python 或后端依赖即可安装、构建前端；业务运行时需可访问 HTTP API。

检查命令：pnpm test、pnpm typecheck、pnpm build。构建产物 dist、node_modules、真实 .env 和日志均不提交。
