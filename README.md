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

## 生产部署顺序

推荐顺序：

```text
1. 推送代码到 GitHub
2. 部署 Render 后端
3. 部署 Cloudflare Pages 前端
4. 验证 CORS 和登录增删改查
```

Render 不是 VPS，不需要 SSH 上去 `git pull`。第一次连好 GitHub 仓库后，后续推送 `main` 分支会触发自动部署。

## 1. 部署后端到 Render

### 1.1 推送代码

```powershell
git add .
git commit -m "deploy"
git push
```

仓库：

```text
https://github.com/1019500461/utools_main
```

### 1.2 创建 Render Web Service

可以用仓库里的 `render.yaml` 创建 Blueprint，也可以手动创建 Web Service。

手动创建时填：

```text
Root Directory: 留空
Build Command: uv sync --frozen --no-dev
Start Command: uv run --frozen --no-dev uvicorn app.main:app --host 0.0.0.0 --port $PORT
Health Check Path: /health
```

注意：

- `Root Directory` 留空，因为 `pyproject.toml`、`uv.lock`、`app/` 都在仓库根目录。
- `$PORT` 必须保留，Render 会自动注入端口。
- Render 输入框左侧灰色 `$` 是提示符，不是命令内容。
- 不要用 `python run.py` 作为线上启动命令。

### 1.3 配置 Render 环境变量

Render 后端至少配置：

```text
DATABASE_URL=postgres://USER:URL_ENCODED_PASSWORD@HOST:5432/postgres?sslmode=verify-full
DATABASE_SSL_ROOT_CERT=Supabase Root CA 证书内容
SECRET_KEY=生产随机密钥
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=10080
CORS_ORIGINS=["https://utools-main-web.pages.dev","http://localhost:5173","http://127.0.0.1:5173"]
PYTHON_VERSION=3.14.5
```

数据库密码必须 URL 编码。常见字符：

```text
@ -> %40
# -> %23
% -> %25
空格 -> %20
```

PowerShell 生成编码后的连接串：

```powershell
$pwd = Read-Host "DB password"
$encoded = [uri]::EscapeDataString($pwd)
"postgres://postgres.PROJECT_REF:$encoded@POOLER_HOST:5432/postgres?sslmode=verify-full"
```

Supabase CA 证书下载位置：

```text
Supabase Project -> Database -> Settings -> SSL Configuration
```

下载 Root CA 后，把证书完整内容粘贴到 Render 的 `DATABASE_SSL_ROOT_CERT`：

```text
-----BEGIN CERTIFICATE-----
...
-----END CERTIFICATE-----
```

### 1.4 部署并验证后端

Render 控制台执行：

```text
Manual Deploy -> Clear build cache & deploy
```

验证：

```powershell
uv run python -c "import httpx; r=httpx.get('https://utools-main.onrender.com/health', timeout=30, trust_env=False); print(r.status_code); print(r.text)"
```

期望返回：

```text
200
{"code":200,"msg":"OK","data":{"status":"ok"}}
```

访问后端根路径 `/` 返回 `404 Not Found` 是正常的，当前后端只提供 API 和 `/health`。

## 2. 部署前端到 Cloudflare Pages

前端目录是 `web/`，构建产物是 `web/dist/`。

### 2.1 确认 Wrangler 登录

```powershell
wrangler.cmd --version
wrangler.cmd whoami
```

如果 PowerShell 拦截 `wrangler.ps1`，直接用 `wrangler.cmd`。

### 2.2 构建前端

生产前端必须指定后端 API 地址：

```powershell
cd web
Remove-Item -Recurse -Force .\dist -ErrorAction SilentlyContinue
$env:VITE_API_BASE_URL="https://utools-main.onrender.com/api/v1"
corepack pnpm build
```

检查构建产物是否包含后端地址：

```powershell
Select-String -Path .\dist\assets\*.js -Pattern "utools-main.onrender.com"
```

如果没有输出，说明 `VITE_API_BASE_URL` 没生效，需要重新设置环境变量再构建。

### 2.3 创建 Pages 项目

首次部署才需要创建：

```powershell
wrangler.cmd pages project create utools-main-web --production-branch main
```

如果项目已存在，跳过这一步。

### 2.4 部署前端

```powershell
wrangler.cmd pages deploy dist --project-name utools-main-web --branch main --commit-dirty=true
```

成功后会输出：

```text
Deployment complete! Take a peek over at https://<deployment-id>.utools-main-web.pages.dev
```

正式访问地址：

```text
https://utools-main-web.pages.dev
```

## 3. 验证线上功能

### 3.1 验证后端 CORS

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

### 3.2 跑真实线上 E2E

不传 `--mock-api`，会真实请求 Cloudflare 前端和 Render 后端：

```powershell
uv run --group e2e python tests/e2e_login_role_playwright.py --base-url https://utools-main-web.pages.dev --screenshot-dir test-results/screenshots
```

期望返回：

```text
playwright e2e ok
```

这个测试会登录、创建角色、查询角色、编辑角色、保存权限、删除测试角色。

## 4. 常见坑

- 前端能打开但登录失败：检查 `VITE_API_BASE_URL` 是否在构建时设置为 `https://utools-main.onrender.com/api/v1`。
- 浏览器报 CORS：检查 Render 的 `CORS_ORIGINS` 是否包含当前访问的前端 Origin。
- Cloudflare 预览地址跨域：`https://<deployment-id>.utools-main-web.pages.dev` 和 `https://utools-main-web.pages.dev` 是两个 Origin；后端只放行正式域名时，预览地址会被拦截。
- 改了前端环境变量但没变化：必须重新 `corepack pnpm build`，再重新 `wrangler.cmd pages deploy ...`。
- Render 免费后端休眠：先访问 `https://utools-main.onrender.com/health` 手动唤醒。
- Supabase 数据库疑似休眠：先访问 `https://utools-main.onrender.com/health/db`，它会真实执行一次 `SELECT 1`。
- Render 报 `No open ports detected`：通常是应用启动失败，先看上方 Python traceback。
- Render 报数据库证书错误：确认 `DATABASE_URL` 使用 `sslmode=verify-full`，并配置了完整的 `DATABASE_SSL_ROOT_CERT`。
- Render 报密码认证失败：检查数据库密码是否 URL 编码。
- Wrangler 末尾提示无法写日志，但出现 `Deployment complete`：通常部署已完成，继续用线上 URL 验证。

## 5. 本地测试命令

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
