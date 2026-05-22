# utools-main

## 环境要求

- Python 3.14.x
- uv
- Node.js 24.x LTS
- pnpm
- PostgreSQL，当前按 Supabase Pooler + SSL 配置

## 后端

复制环境变量模板，并填写自己的数据库连接和密钥：

```powershell
Copy-Item .env.example .env
uv venv --python 3.14
uv sync
python run.py
```

首次启动会自动创建缺失表，并初始化默认账号：

- 用户名：`admin`
- 密码：`123456`

`.env` 不应提交到仓库。数据库密码、`SECRET_KEY` 等敏感信息只放在本地环境变量文件中。

## 前端

```powershell
cd web
corepack pnpm install
corepack pnpm dev
```

前端使用 Vue 3、Vite 7、Naive UI、Pinia、Vue Router 和 Tailwind CSS。
开发环境下，Vite 会把 `/api` 代理到 `http://127.0.0.1:8000`。

## 测试与验收

测试用例清单见 `tests/acceptance_cases.md`。

后端 API 冒烟测试：

```powershell
uv run python tests/api_smoke.py
```

浏览器端 E2E 测试需要先启动后端和前端：

```powershell
uv run python run.py
cd web
corepack pnpm dev
```

然后在项目根目录运行：

```powershell
uv run python tests/e2e_login_role_playwright.py --screenshot-dir test-results/screenshots
```

## Render 部署

后端可以用仓库根目录的 `render.yaml` 创建 Render Web Service。关键配置：

```text
Build Command: uv sync --frozen --no-dev
Start Command: uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT
Health Check Path: /health
```

Render 环境变量至少需要：

```text
DATABASE_URL=postgres://USER:PASSWORD@HOST:5432/postgres?ssl=true
SECRET_KEY=生产环境随机长密钥
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=10080
CORS_ORIGINS=["https://你的前端域名"]
PYTHON_VERSION=3.14.3
```

如果前端作为独立 Static Site 部署，前端环境变量需要设置：

```text
VITE_API_BASE_URL=https://你的后端域名/api/v1
```
