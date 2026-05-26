# utools-main

FastAPI 后端 + Vue 管理端。

## 当前线上地址

- 前端：https://utools-main-web.pages.dev
- 后端：https://utools-main.onrender.com
- 后端健康检查：https://utools-main.onrender.com/health
- 默认账号：`admin`
- 默认密码：`123456`

## 手动唤醒后端

Render 免费后端长时间没人访问会休眠。页面登录失败或第一次请求很慢时，先打开后端唤醒地址：

```text
https://utools-main.onrender.com/health
```

看到下面结果，说明后端已唤醒：

```json
{"code":200,"msg":"OK","data":{"status":"ok"}}
```

然后再访问前端：

```text
https://utools-main-web.pages.dev
```

如果怀疑数据库也休眠，打开数据库唤醒地址：

```text
https://utools-main.onrender.com/health/db
```

看到下面结果，说明后端和数据库都可用：

```json
{"code":200,"msg":"OK","data":{"status":"ok","database":"ok"}}
```

仓库已配置 GitHub Actions 自动保活：

```text
.github/workflows/keep-awake.yml
```

它会每 4 天访问一次 `/health/db`，也可以在 GitHub Actions 页面手动运行。

不要把数据库密码、`SECRET_KEY`、Cloudflare Token、Render Token 写进代码、README 或提交记录。

## 本地运行

### 后端

```powershell
Copy-Item .env.example .env
uv venv --python 3.14
uv sync
uv run python run.py
```

本地后端默认地址：

```text
http://127.0.0.1:8000
```

### 前端

```powershell
cd web
corepack pnpm install
corepack pnpm dev
```

本地前端默认地址：

```text
http://127.0.0.1:5173
```

开发环境下，Vite 会把 `/api` 代理到 `http://127.0.0.1:8000`。

## 生产部署

当前项目已接入 GitHub、Render、Cloudflare Pages 和 Supabase。正常情况下，生产部署只需要：

```powershell
git add .
git commit -m "deploy"
git push
```

推送 `main` 后：

- Render 根据仓库根目录的 `render.yaml` 自动部署后端。
- Cloudflare Pages 根据 Git 集成自动构建并部署前端。
- Supabase 作为外部 PostgreSQL 数据库，不随代码部署。

不要把数据库密码、`SECRET_KEY`、Cloudflare Token、Render Token、Supabase 密钥写进代码、README 或提交记录。

## 1. 一次性平台配置

这些配置只需要首次接入或换项目时处理。日常改代码不需要重复配置。

### 1.1 Render 后端

用仓库里的 `render.yaml` 创建 Render Blueprint。

`render.yaml` 已定义：

- 服务名：`utools-main-api`
- 构建命令：`uv sync --frozen --no-dev`
- 启动命令：`uv run --frozen --no-dev uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- 健康检查：`/health`
- Python 版本：`3.14.5`

Render 里需要配置的环境变量：

```text
DATABASE_URL=postgres://USER:URL_ENCODED_PASSWORD@HOST:5432/postgres?sslmode=verify-full
DATABASE_SSL_ROOT_CERT=Supabase Root CA 证书内容
```

`SECRET_KEY`、`JWT_ACCESS_TOKEN_EXPIRE_MINUTES`、`CORS_ORIGINS`、`PYTHON_VERSION` 已在 `render.yaml` 中配置。`SECRET_KEY` 使用 Render Blueprint 自动生成，不要手写进仓库。

基金/ETF 邮件提醒还需要 SMTP 发件配置：

```text
SMTP_HOST=smtp.xxx.com
SMTP_USER=your-sender@example.com
SMTP_PASSWORD=邮箱 SMTP 授权码或密码
SMTP_FROM=your-sender@example.com
SMTP_TO=fallback-recipient@example.com
```

`SMTP_PORT=587` 和 `SMTP_TLS=true` 已在 `render.yaml` 中配置，一般不用改。

说明：

- `SMTP_USER` / `SMTP_FROM` 是发件邮箱。
- `SMTP_PASSWORD` 通常不是邮箱登录密码，而是邮箱服务商生成的 SMTP 授权码。
- 页面「个人中心」填写的是接收通知邮箱。
- `SMTP_TO` 是兜底接收邮箱；当系统里没有可用用户邮箱时才会使用。
- Render 不是 VPS，不需要 SSH 上去 `git pull`。
- 访问后端根路径 `/` 返回 `404 Not Found` 是正常的，当前后端只提供 API 和 `/health`。

如果使用 Render MCP 或 API 批量设置环境变量，仍然不要把真实密钥写入命令历史、README 或提交记录。当前仓库的简化方式是：变量名和默认值写在 `render.yaml`，敏感值只在 Render Dashboard 填。

### 1.2 Supabase 数据库

Render 的 `DATABASE_URL` 使用 Supabase PostgreSQL 连接串。

数据库密码必须 URL 编码。常见字符：

```text
@ -> %40
# -> %23
% -> %25
空格 -> %20
```

PowerShell 生成编码后的密码：

```powershell
$pwd = Read-Host "DB password"
[uri]::EscapeDataString($pwd)
```

`DATABASE_SSL_ROOT_CERT` 使用 Supabase Root CA 证书内容。位置：

```text
Supabase Project -> Database -> Settings -> SSL Configuration
```

证书需要完整粘贴到 Render 环境变量：

```text
-----BEGIN CERTIFICATE-----
...
-----END CERTIFICATE-----
```

不要为了省事把 `sslmode=verify-full` 改成弱校验。

### 1.3 Cloudflare Pages 前端

Cloudflare Pages 连接 GitHub 仓库后，配置：

```text
Project name: utools-main-web
Production branch: main
Root directory: web
Build command: corepack pnpm install --frozen-lockfile && corepack pnpm build
Build output directory: dist
```

生产环境变量：

```text
VITE_API_BASE_URL=https://utools-main.onrender.com/api/v1
```

正式访问地址：

```text
https://utools-main-web.pages.dev
```

如果没有配置 `VITE_API_BASE_URL`，前端会打开，但登录和 API 请求会失败。

## 2. 线上验证

### 2.1 验证后端健康检查

```powershell
uv run python -c "import httpx; r=httpx.get('https://utools-main.onrender.com/health', timeout=30, trust_env=False); print(r.status_code); print(r.text)"
```

期望返回：

```text
200
{"code":200,"msg":"OK","data":{"status":"ok"}}
```

如果怀疑数据库连接有问题：

```powershell
uv run python -c "import httpx; r=httpx.get('https://utools-main.onrender.com/health/db', timeout=30, trust_env=False); print(r.status_code); print(r.text)"
```

### 2.2 验证后端 CORS

```powershell
@'
import httpx

r = httpx.options(
    "https://utools-main.onrender.com/api/v1/base/access_token",
    headers={
        "Origin": "https://utools-main-web.pages.dev",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    },
    timeout=30,
    trust_env=False,
)
print(r.status_code)
print(r.headers.get("access-control-allow-origin"))
'@ | uv run --frozen --no-dev python -
```

期望返回：

```text
200
https://utools-main-web.pages.dev
```

### 2.3 跑真实线上 E2E

不传 `--mock-api`，会真实请求 Cloudflare 前端和 Render 后端：

```powershell
uv run --group e2e python tests/e2e_login_role_playwright.py --base-url https://utools-main-web.pages.dev --screenshot-dir test-results/screenshots
```

期望返回：

```text
playwright e2e ok
```

这个测试会登录、创建角色、查询角色、编辑角色、保存权限、删除测试角色。

## 3. 常见坑

- 前端能打开但登录失败：检查 `VITE_API_BASE_URL` 是否在构建时设置为 `https://utools-main.onrender.com/api/v1`。
- 浏览器报 CORS：检查 Render 的 `CORS_ORIGINS` 是否包含当前访问的前端 Origin。
- Cloudflare 预览地址跨域：`https://<deployment-id>.utools-main-web.pages.dev` 和 `https://utools-main-web.pages.dev` 是两个 Origin；后端只放行正式域名时，预览地址会被拦截。
- 改了 Cloudflare Pages 环境变量但没变化：需要在 Cloudflare Pages 重新部署一次生产环境。
- Render 免费后端休眠：先访问 `https://utools-main.onrender.com/health` 手动唤醒。
- Supabase 数据库疑似休眠：先访问 `https://utools-main.onrender.com/health/db`，它会真实执行一次 `SELECT 1`。
- 自动保活失败：到 GitHub 仓库的 Actions 页面，手动运行 `Keep Awake`。
- Render 报 `No open ports detected`：通常是应用启动失败，先看上方 Python traceback。
- Render 报数据库证书错误：确认 `DATABASE_URL` 使用 `sslmode=verify-full`，并配置了完整的 `DATABASE_SSL_ROOT_CERT`。
- Render 报密码认证失败：检查数据库密码是否 URL 编码。

## 4. 本地测试命令

后端 API 冒烟测试：

```powershell
uv run python tests/api_smoke.py
```

本地浏览器 E2E：

```powershell
uv run --group e2e python tests/e2e_login_role_playwright.py --screenshot-dir test-results/screenshots
```

测试用例清单：

```text
tests/acceptance_cases.md
```
