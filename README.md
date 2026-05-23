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

后端部署到 Render 的推荐链路：

```text
本地代码 -> git push -> GitHub -> Render 自动构建和部署
```

Render 不是传统 VPS，通常不需要 SSH 到服务器执行 `git pull`。第一次在 Render 控制台连接 GitHub 仓库并配置环境变量后，后续只要推送 `main` 分支，Render 会自动部署。

### 0. 最短可执行流程

第一次部署按这个顺序执行：

```text
1. 推送代码到 GitHub
2. 在 Render 创建 Web Service，Root Directory 留空
3. 填 Build Command / Start Command / Health Check Path
4. 在 Render 填 DATABASE_URL、DATABASE_SSL_ROOT_CERT、SECRET_KEY、CORS_ORIGINS
5. Manual Deploy -> Clear build cache & deploy
6. 访问 /health 验证
```

当前后端线上地址：

```text
https://utools-main.onrender.com
```

### 1. GitHub 仓库

先把代码推到 GitHub：

```powershell
git add .
git commit -m "prepare render deployment"
git push
```

当前仓库地址：

```text
https://github.com/1019500461/utools_main
```

### 2. 创建 Render Web Service

在 Render 创建 `Web Service`，选择 GitHub 仓库 `1019500461/utools_main`。

关键配置：

```text
Root Directory: 留空
Build Command: uv sync --frozen --no-dev
Start Command: uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT
Health Check Path: /health
```

注意：

- `Root Directory` 必须留空，因为 `pyproject.toml`、`uv.lock`、`app/` 都在仓库根目录。
- `Start Command` 里的 `$PORT` 必须保留，Render 会自动替换成真实端口。
- Render 输入框左侧灰色 `$` 是提示符，不是命令内容，不要手动输入。
- 不要用 `python run.py` 作为线上启动命令。
- 不要用默认示例 `gunicorn your_application.wsgi`，FastAPI 应使用 `uvicorn`。

仓库根目录也提供了 `render.yaml`，可以用 Blueprint 创建同等配置。

### 3. 环境变量

Render 后端至少需要：

```text
DATABASE_URL=postgres://USER:PASSWORD@HOST:5432/postgres?sslmode=verify-full
DATABASE_SSL_ROOT_CERT=Supabase Root CA 证书内容
SECRET_KEY=生产环境随机长密钥
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=10080
CORS_ORIGINS=["https://你的前端域名"]
PYTHON_VERSION=3.14.5
```

`SECRET_KEY` 必须是生产随机值，不要提交到代码或文档。

如果前端还没有线上域名，`CORS_ORIGINS` 可以先填本地开发地址：

```text
["http://localhost:5173","http://127.0.0.1:5173"]
```

前端上线后再改成真实前端域名，例如：

```text
["https://你的前端域名"]
```

### 4. Supabase Pooler 连接串

连接串格式：

```text
postgres://用户名:URL编码后的密码@主机:端口/数据库?sslmode=verify-full
```

如果密码里有特殊字符，必须 URL 编码。例如 `@` 要写成 `%40`。

PowerShell 生成连接串示例：

```powershell
$pwd = Read-Host "DB password"
$encoded = [uri]::EscapeDataString($pwd)
"postgres://postgres.PROJECT_REF:$encoded@POOLER_HOST:5432/postgres?sslmode=verify-full"
```

不要把数据库密码写进 README、提交记录或聊天记录。

### 5. Supabase CA 证书

本项目使用 Supabase Pooler + SSL。Render 上 Python 3.14 对证书校验更严格，如果只配置 `DATABASE_URL`，可能启动失败：

```text
ssl.SSLCertVerificationError: certificate verify failed
```

正确做法是把 Supabase CA 证书填到 Render 环境变量 `DATABASE_SSL_ROOT_CERT`。

可以在 Supabase 控制台下载 CA 证书：

```text
Supabase Project -> Database -> Settings -> SSL Configuration
```

Supabase 官方文档推荐从项目控制台下载 CA 证书。不要依赖非官方固定下载链接，因为证书和下载路径可能随项目区域、连接方式或 Supabase 更新而变化。

也可以从 Pooler TLS 握手抓取证书链。以下脚本不会登录数据库，不需要数据库密码，只读取服务端证书链：

```powershell
@'
import socket, ssl, struct
from pathlib import Path
from ssl import DER_cert_to_PEM_cert

host = "aws-1-ap-southeast-1.pooler.supabase.com"
port = 5432
out = Path("C:/tmp/supabase-certs")
out.mkdir(parents=True, exist_ok=True)

sock = socket.create_connection((host, port), timeout=20)
sock.sendall(struct.pack("!II", 8, 80877103))
response = sock.recv(1)
if response != b"S":
    raise RuntimeError(f"Postgres server rejected SSL request: {response!r}")

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
ssock = ctx.wrap_socket(sock, server_hostname=host)

certs = [ssock.getpeercert(binary_form=True)]
if hasattr(ssock, "get_unverified_chain"):
    certs = [
        cert.public_bytes() if hasattr(cert, "public_bytes") else cert
        for cert in ssock.get_unverified_chain()
    ]

for index, der in enumerate(certs, start=1):
    pem = DER_cert_to_PEM_cert(der)
    path = out / f"cert-{index}.pem"
    path.write_text(pem, encoding="ascii")
    print(path)

ssock.close()
'@ | uv run python -
```

把根证书文件内容完整复制到 Render：

```text
DATABASE_SSL_ROOT_CERT=-----BEGIN CERTIFICATE-----
...
-----END CERTIFICATE-----
```

当前 Supabase Pooler 证书链中通常：

```text
cert-1.pem: 服务端证书
cert-2.pem: Supabase Intermediate CA
cert-3.pem: Supabase Root CA
```

本项目已经验证过：Render + Python 3.14.5 + Supabase Pooler 使用 `cert-3.pem` 写入 `DATABASE_SSL_ROOT_CERT` 后可以启动成功。

### 6. Render CLI

Render CLI 可用于查看服务、日志、触发部署和更新环境变量。安装示例：

```powershell
$dir = "C:\tmp\render-cli"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
Invoke-WebRequest `
  -Uri "https://github.com/render-oss/cli/releases/download/v2.18.0/cli_2.18.0_windows_amd64.zip" `
  -OutFile "$dir\render-cli.zip"
Expand-Archive -Force -Path "$dir\render-cli.zip" -DestinationPath $dir
C:\tmp\render-cli\cli_v2.18.0.exe --version
```

登录和选择 workspace：

```powershell
C:\tmp\render-cli\cli_v2.18.0.exe login
C:\tmp\render-cli\cli_v2.18.0.exe workspaces --output json
C:\tmp\render-cli\cli_v2.18.0.exe workspace set <workspace_id>
```

查看服务和日志：

```powershell
C:\tmp\render-cli\cli_v2.18.0.exe services --output json
C:\tmp\render-cli\cli_v2.18.0.exe logs --resources <service_id> --limit 120 --output text
```

从 `services --output json` 输出中取：

```text
service.id          -> <service_id>
service.serviceDetails.url -> 后端 URL
```

触发部署：

```powershell
C:\tmp\render-cli\cli_v2.18.0.exe deploys create <service_id> --confirm
```

### 7. 用 Render API 写入 Supabase CA 证书

如果不想在网页里粘贴多行证书，可以使用 Render CLI 登录后的 API token。下面脚本会保留现有环境变量，并新增或更新 `DATABASE_SSL_ROOT_CERT`，不会打印任何变量值：

```powershell
@'
import json
import re
from pathlib import Path

import httpx

service_id = "<service_id>"
cert_path = Path("C:/tmp/supabase-certs/cert-3.pem")

cfg = Path.home().joinpath(".render", "cli.yaml").read_text(encoding="utf-8")
token = re.search(r"(?m)^\s+key:\s*(.+)$", cfg).group(1).strip()
headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
cert = cert_path.read_text(encoding="ascii")

with httpx.Client(base_url="https://api.render.com/v1", headers=headers, timeout=30, trust_env=False) as client:
    current = client.get(f"/services/{service_id}/env-vars")
    current.raise_for_status()

    vars_by_key = {
        item["envVar"]["key"]: item["envVar"]["value"]
        for item in current.json()
    }
    vars_by_key["DATABASE_SSL_ROOT_CERT"] = cert

    payload = [{"key": key, "value": value} for key, value in vars_by_key.items()]
    response = client.put(
        f"/services/{service_id}/env-vars",
        headers={"Content-Type": "application/json"},
        content=json.dumps(payload),
    )
    response.raise_for_status()
    print("DATABASE_SSL_ROOT_CERT updated")
'@ | uv run python -
```

写入后触发部署：

```powershell
C:\tmp\render-cli\cli_v2.18.0.exe deploys create <service_id> --confirm
```

### 8. 验证部署

部署成功后，Render 日志应出现：

```text
Application startup complete.
Uvicorn running on http://0.0.0.0:<PORT>
Your service is live
```

健康检查：

```powershell
uv run python -c "import httpx; r=httpx.get('https://utools-main.onrender.com/health', timeout=30, trust_env=False); print(r.status_code); print(r.text)"
```

期望返回：

```json
{"code":200,"msg":"OK","data":{"status":"ok"}}
```

访问根路径 `/` 返回 `404 Not Found` 是正常的，因为当前后端只提供 API 和 `/health`，没有后端首页。

### 9. 常见错误

端口错误：

```text
No open ports detected
```

通常不是端口本身，而是应用启动失败。先看它上面真正的 Python traceback。

数据库证书错误：

```text
ssl.SSLCertVerificationError: certificate verify failed
```

检查：

- `DATABASE_URL` 是否使用 `sslmode=verify-full`
- 是否配置 `DATABASE_SSL_ROOT_CERT`
- 证书内容是否完整包含 `BEGIN CERTIFICATE` 和 `END CERTIFICATE`
- 如果是在 Render 页面手动粘贴证书，确认多行内容没有丢失换行
- 如果使用 API 写入证书，确认脚本中的 `<service_id>` 已替换为真实服务 ID

Python 3.14 严格证书扩展错误：

```text
CA cert does not include key usage extension
```

项目代码已处理该兼容问题：保留证书链和主机名校验，只关闭 Python SSL 的 `VERIFY_X509_STRICT` 扩展检查。

数据库密码解析错误：

```text
password authentication failed
```

检查 `DATABASE_URL` 里的密码是否做了 URL 编码。常见字符：

```text
@ -> %40
# -> %23
% -> %25
空格 -> %20
```

构建命令错误：

```text
ModuleNotFoundError
```

检查 `Build Command` 是否是：

```text
uv sync --frozen --no-dev
```

不要改成 `pip install -r requirements.txt`。本项目依赖以 `pyproject.toml` 和 `uv.lock` 为准。

如果前端作为独立 Static Site 部署，前端环境变量需要设置：

```text
VITE_API_BASE_URL=https://你的后端域名/api/v1
```
