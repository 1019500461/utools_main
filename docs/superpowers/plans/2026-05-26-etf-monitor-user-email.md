# ETF Monitor User Email Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make ETF monitors user-scoped, send alerts to the owning user's email, add SMTP test sending, and persist alert send records.

**Architecture:** Keep the existing ETF module boundaries. Add ownership and alert log models, add a small idempotent schema maintenance helper because the project currently relies on `Tortoise.generate_schemas(safe=True)` and has no migration system, then pass the current user through API/service calls. Notification sending returns a structured result so monitor code can persist success and failure without hiding errors.

**Tech Stack:** FastAPI, Tortoise ORM, PostgreSQL on Render, Vue 3, Naive UI, Axios, Python Playwright.

---

## File Structure

- Modify `app/modules/etf/models.py`: add `ETFMonitor.user` relation, replace global `code` uniqueness with `(user, code)`, add `ETFAlertLog`.
- Create `app/modules/etf/schema_maintenance.py`: idempotently alter existing PostgreSQL tables because `generate_schemas(safe=True)` does not migrate existing tables.
- Modify `app/db/session.py`: run ETF schema maintenance after base schema creation and before seed data depends on the schema.
- Modify `app/modules/etf/service.py`: scope monitor queries by current user; keep runtime monitor query global for scheduler.
- Modify `app/modules/etf/api.py`: pass `current_user` into list/create/update/delete/detail/sync/manual monitor endpoints.
- Modify `app/modules/etf/notification.py`: resolve recipient from monitor owner or current user, return structured send result, add test email sender.
- Modify `app/modules/etf/monitor.py`: persist `ETFAlertLog`, improve skipped reasons and logging.
- Modify `app/modules/etf/schemas.py`: add response/input model for test email if needed by endpoint.
- Modify `web/src/api/index.ts`: add `testNotificationEmail`.
- Modify `web/src/views/ProfileView.vue`: add a test-send button beside save.
- Modify `tests/e2e_etf_playwright.py`: mock `/base/profile/test-email` and assert the button works.

---

### Task 1: Add Models And Idempotent Schema Maintenance

**Files:**
- Modify: `app/modules/etf/models.py`
- Create: `app/modules/etf/schema_maintenance.py`
- Modify: `app/db/session.py`

- [ ] **Step 1: Update ETF models**

In `app/modules/etf/models.py`, replace the `ETFMonitor.code` definition and add user ownership plus alert log.

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.user.models import User


class ETFMonitor(Model, TimestampMixin):
    id = fields.IntField(pk=True)
    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField(
        "models.User",
        related_name="etf_monitors",
        on_delete=fields.CASCADE,
        index=True,
    )
    code = fields.CharField(max_length=20, index=True)
    name = fields.CharField(max_length=100, default="")
    is_active = fields.BooleanField(default=True, index=True)
    time_range = fields.CharField(max_length=10, default="3y")
    x_drop = fields.FloatField(default=0.15)
    y_step = fields.FloatField(default=0.05)
    current_stage = fields.IntField(default=0)
    last_checked_at = fields.DatetimeField(null=True)
    last_alert_at = fields.DatetimeField(null=True)

    class Meta:
        table = "etf_monitor"
        unique_together = (("user", "code"),)


class ETFAlertLog(Model, TimestampMixin):
    id = fields.IntField(pk=True)
    monitor: fields.ForeignKeyRelation[ETFMonitor] = fields.ForeignKeyField(
        "models.ETFMonitor",
        related_name="alert_logs",
        on_delete=fields.CASCADE,
        index=True,
    )
    user: fields.ForeignKeyRelation["User"] = fields.ForeignKeyField(
        "models.User",
        related_name="etf_alert_logs",
        on_delete=fields.CASCADE,
        index=True,
    )
    code = fields.CharField(max_length=20, index=True)
    recipient = fields.CharField(max_length=255, default="")
    stage = fields.IntField()
    price = fields.FloatField()
    retract = fields.FloatField()
    status = fields.CharField(max_length=20, index=True)
    error_message = fields.TextField(default="")
    sent_at = fields.DatetimeField(null=True)

    class Meta:
        table = "etf_alert_log"
```

- [ ] **Step 2: Create schema maintenance helper**

Create `app/modules/etf/schema_maintenance.py` with PostgreSQL-safe, idempotent SQL. This preserves existing monitors by assigning them to the first active superuser, falling back to the first active user.

```python
from __future__ import annotations

from loguru import logger
from tortoise import connections


async def ensure_etf_schema() -> None:
    connection = connections.get("default")
    if connection.capabilities.dialect != "postgres":
        return

    await connection.execute_script(
        """
        ALTER TABLE etf_monitor
            ADD COLUMN IF NOT EXISTS user_id INTEGER;

        UPDATE etf_monitor
        SET user_id = (
            SELECT id
            FROM admin_user
            WHERE is_active = TRUE
            ORDER BY is_superuser DESC, id ASC
            LIMIT 1
        )
        WHERE user_id IS NULL;

        DO $$
        DECLARE
            constraint_name text;
        BEGIN
            FOR constraint_name IN
                SELECT c.conname
                FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                WHERE t.relname = 'etf_monitor'
                  AND c.contype = 'u'
                  AND pg_get_constraintdef(c.oid) = 'UNIQUE (code)'
            LOOP
                EXECUTE format('ALTER TABLE etf_monitor DROP CONSTRAINT %I', constraint_name);
            END LOOP;
        END $$;

        DROP INDEX IF EXISTS etf_monitor_code_key;
        DROP INDEX IF EXISTS idx_etf_monitor_code_unique;

        ALTER TABLE etf_monitor
            ALTER COLUMN user_id SET NOT NULL;

        ALTER TABLE etf_monitor
            ADD CONSTRAINT fk_etf_monitor_user
            FOREIGN KEY (user_id) REFERENCES admin_user(id)
            ON DELETE CASCADE;

        CREATE UNIQUE INDEX IF NOT EXISTS idx_etf_monitor_user_code
            ON etf_monitor(user_id, code);

        CREATE TABLE IF NOT EXISTS etf_alert_log (
            id SERIAL PRIMARY KEY,
            monitor_id INTEGER NOT NULL REFERENCES etf_monitor(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES admin_user(id) ON DELETE CASCADE,
            code VARCHAR(20) NOT NULL,
            recipient VARCHAR(255) NOT NULL DEFAULT '',
            stage INTEGER NOT NULL,
            price DOUBLE PRECISION NOT NULL,
            retract DOUBLE PRECISION NOT NULL,
            status VARCHAR(20) NOT NULL,
            error_message TEXT NOT NULL DEFAULT '',
            sent_at TIMESTAMP NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_etf_alert_log_user_id ON etf_alert_log(user_id);
        CREATE INDEX IF NOT EXISTS idx_etf_alert_log_monitor_id ON etf_alert_log(monitor_id);
        CREATE INDEX IF NOT EXISTS idx_etf_alert_log_code ON etf_alert_log(code);
        CREATE INDEX IF NOT EXISTS idx_etf_alert_log_status ON etf_alert_log(status);
        """
    )
    logger.info("ETF schema maintenance finished")
```

- [ ] **Step 3: Run schema maintenance during database init**

In `app/db/session.py`, import and call the helper after `generate_schemas`.

```python
from app.modules.etf.schema_maintenance import ensure_etf_schema


async def init_database() -> None:
    await Tortoise.init(config=settings.tortoise_orm)
    await Tortoise.generate_schemas(safe=True)
    await ensure_etf_schema()
    await init_seed_data()
```

- [ ] **Step 4: Compile backend**

Run: `python -m compileall app/modules/etf app/db`

Expected: command exits with code 0.

---

### Task 2: Scope ETF APIs By Current User

**Files:**
- Modify: `app/modules/etf/service.py`
- Modify: `app/modules/etf/api.py`

- [ ] **Step 1: Change service query signatures**

In `app/modules/etf/service.py`, add `User` import and update user-scoped functions.

```python
from app.modules.user.models import User


async def get_monitor_or_none(code: str, user: User) -> ETFMonitor | None:
    return await ETFMonitor.filter(code=normalize_code(code), user_id=user.id).first()


async def list_monitor_snapshots(user: User, active_only: bool = False) -> list[dict]:
    query = ETFMonitor.filter(user_id=user.id)
    if active_only:
        query = query.filter(Q(is_active=True))
    monitors = await query.order_by("code")
    return [await serialize_monitor_list_item(monitor) for monitor in monitors]


async def get_detail(code: str, user: User) -> dict:
    monitor = await get_monitor_or_none(code, user)
    if not monitor:
        return {}

    snapshot = await serialize_monitor_snapshot(monitor)
    peak_price = snapshot.get("peak_price")
    trigger_price = peak_price * (1 - monitor.x_drop) if isinstance(peak_price, (int, float)) else None
    return {
        **snapshot,
        "trigger_price": trigger_price,
        "klines": await get_history_bars(monitor.code, monitor.time_range),
        "fundamentals": {"aum": None, "valuation": None, "holdings": []},
    }


async def list_monitors(user: User) -> list[dict]:
    return await list_monitor_snapshots(user)
```

- [ ] **Step 2: Scope sync to current user**

In `app/modules/etf/service.py`, update `sync_monitors`.

```python
async def sync_monitors(user: User, code: str | None = None) -> list[dict]:
    query = ETFMonitor.filter(user_id=user.id).order_by("code")
    if code:
        query = query.filter(code=normalize_code(code))
    monitors = await query
    results = []
    for monitor in monitors:
        try:
            results.append(await sync_history_incremental(monitor))
        except Exception as exc:
            results.append(
                {
                    "code": normalize_code(monitor.code),
                    "requested_start": "",
                    "requested_end": today_local().isoformat(),
                    "fetched": 0,
                    "inserted": 0,
                    "skipped": False,
                    "error": str(exc),
                    "message": "sync failed",
                }
            )
    return results
```

- [ ] **Step 3: Keep runtime monitor query global**

Do not user-scope `monitors_for_runtime`; the scheduler needs all active monitors.

```python
async def monitors_for_runtime(code: str | None = None) -> list[ETFMonitor]:
    query = ETFMonitor.filter(is_active=True).order_by("code")
    if code:
        query = query.filter(code=normalize_code(code))
    return await query.prefetch_related("user")
```

- [ ] **Step 4: Update API dependency usage**

In `app/modules/etf/api.py`, bind `current_user` and pass it through.

```python
@router.get("/list")
async def list_etf(current_user: User = Depends(get_current_user)):
    return success(await list_monitors(current_user))


@router.post("/create")
async def create_etf(payload: ETFMonitorCreate, current_user: User = Depends(get_current_user)):
    code = normalize_code(payload.code)
    if await ETFMonitor.filter(code=code, user_id=current_user.id).exists():
        raise HTTPException(status_code=400, detail="标的代码已存在")
    monitor = await ETFMonitor.create(
        user=current_user,
        code=code,
        name=payload.name.strip(),
        is_active=payload.is_active,
        time_range=payload.time_range,
        x_drop=payload.x_drop,
        y_step=payload.y_step,
    )
    sync_result = await ensure_seed_history(monitor)
    return success({"monitor": await get_detail(code, current_user), "sync": sync_result}, msg="Created Successfully")
```

- [ ] **Step 5: Update remaining API handlers**

In `app/modules/etf/api.py`, update update/delete/detail/sync/monitor-run handlers.

```python
@router.post("/update")
async def update_etf(payload: ETFMonitorUpdate, current_user: User = Depends(get_current_user)):
    monitor = await get_monitor_or_none(payload.code, current_user)
    if not monitor:
        raise HTTPException(status_code=404, detail="标的不存在")
    ...
    return success(await get_detail(monitor.code, current_user), msg="Updated Successfully")


@router.delete("/delete")
async def delete_etf(code: str = Query(...), current_user: User = Depends(get_current_user)):
    monitor = await get_monitor_or_none(code, current_user)
    if not monitor:
        raise HTTPException(status_code=404, detail="标的不存在")
    await monitor.delete()
    return success(msg="Deleted Successfully")


@router.get("/detail")
async def detail_etf(code: str = Query(...), current_user: User = Depends(get_current_user)):
    detail = await get_detail(code, current_user)
    if not detail:
        raise HTTPException(status_code=404, detail="标的不存在")
    return success(detail)


@router.post("/sync")
async def sync_etf(payload: ETFSyncIn, current_user: User = Depends(get_current_user)):
    if payload.code and not await get_monitor_or_none(payload.code, current_user):
        raise HTTPException(status_code=404, detail="标的不存在")
    return success(await sync_monitors(current_user, payload.code), msg="Synced Successfully")


@router.post("/monitor/run")
async def run_etf_monitor(payload: ETFSyncIn, current_user: User = Depends(get_current_user)):
    if payload.code and not await get_monitor_or_none(payload.code, current_user):
        raise HTTPException(status_code=404, detail="标的不存在")
    return success(await run_monitor_once(payload.code, force=True, user=current_user), msg="Monitor Checked")
```

- [ ] **Step 6: Compile backend**

Run: `python -m compileall app/modules/etf`

Expected: command exits with code 0.

---

### Task 3: Add Structured Notification Sending And Test Email API

**Files:**
- Modify: `app/modules/etf/notification.py`
- Modify: `app/modules/user/api.py`
- Modify: `app/modules/user/schemas.py`

- [ ] **Step 1: Add notification result type**

In `app/modules/etf/notification.py`, add a dataclass.

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class EmailSendResult:
    recipient: str
    subject: str
```

- [ ] **Step 2: Resolve recipient from a provided user**

Replace `_resolve_recipient_email` with a function that accepts a preferred user.

```python
async def _resolve_recipient_email(preferred_user: User | None = None) -> str:
    if preferred_user and preferred_user.email:
        return preferred_user.email

    user = await User.filter(is_active=True, is_superuser=True).exclude(email="").order_by("id").first()
    if not user:
        user = await User.filter(is_active=True).exclude(email="").order_by("id").first()
    return user.email if user and user.email else settings.smtp_to
```

- [ ] **Step 3: Return recipient and subject from strategy notification**

Change `send_strategy_notification`.

```python
async def send_strategy_notification(
    code: str,
    stage: int,
    price: float,
    retract: float,
    user: User | None = None,
) -> EmailSendResult:
    subject, body = build_strategy_email(code, stage, price, retract)
    recipient = await _resolve_recipient_email(user)
    await asyncio.to_thread(_send_email, subject, body, recipient)
    return EmailSendResult(recipient=recipient, subject=subject)
```

- [ ] **Step 4: Add test email builder and sender**

In `app/modules/etf/notification.py`, add a neutral test email.

```python
def build_test_email(username: str) -> tuple[str, str]:
    safe_username = html.escape(username)
    subject = "【系统通知】邮件配置测试"
    body = f"""
<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8" /></head>
<body>
  <p>{safe_username}，这是一封邮件配置测试。</p>
  <p>如果你收到这封邮件，说明当前 SMTP 发件配置和通知邮箱可以正常使用。</p>
</body>
</html>
"""
    return subject, body


async def send_test_notification_email(user: User) -> EmailSendResult:
    subject, body = build_test_email(user.username)
    recipient = await _resolve_recipient_email(user)
    await asyncio.to_thread(_send_email, subject, body, recipient)
    return EmailSendResult(recipient=recipient, subject=subject)
```

- [ ] **Step 5: Add user API endpoint**

In `app/modules/user/api.py`, import `send_test_notification_email` and add endpoint.

```python
from app.modules.etf.notification import send_test_notification_email


@router.post("/profile/test-email")
async def test_profile_email(current_user: User = Depends(get_current_user)):
    try:
        result = await send_test_notification_email(current_user)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"邮件发送失败：{exc}") from exc

    return success(
        {
            "recipient": result.recipient,
            "subject": result.subject,
        },
        msg="Test Email Sent",
    )
```

- [ ] **Step 6: Compile backend**

Run: `python -m compileall app/modules/user app/modules/etf`

Expected: command exits with code 0.

---

### Task 4: Persist Monitor Alert Logs And Improve Runtime Logging

**Files:**
- Modify: `app/modules/etf/monitor.py`

- [ ] **Step 1: Update imports and function signature**

In `app/modules/etf/monitor.py`, import `ETFAlertLog` and `User`, then allow manual run to filter by user.

```python
from app.modules.etf.models import ETFAlertLog
from app.modules.user.models import User


async def run_monitor_once(
    code: str | None = None,
    force: bool = False,
    user: User | None = None,
) -> list[dict[str, Any]]:
```

- [ ] **Step 2: Filter manual monitor run by user**

After loading monitors, filter by `user.id` for manual calls.

```python
monitors = await monitors_for_runtime(code)
if user:
    monitors = [monitor for monitor in monitors if monitor.user_id == user.id]
```

- [ ] **Step 3: Add explicit skip logs**

Add logs for outside market time, missing peak, and missing price.

```python
if not force and not is_market_check_time():
    logger.info("ETF monitor skipped: outside market time")
    return [{"skipped": True, "reason": "outside_market_time"}]

if not peak_price:
    result.update({"skipped": True, "reason": "missing_peak"})
    logger.info("ETF monitor skipped for {}: missing peak price", monitor.code)
    results.append(result)
    continue

if not current_price:
    result.update({"skipped": True, "reason": "missing_current_price"})
    logger.info("ETF monitor skipped for {}: missing current price", monitor.code)
    results.append(result)
    continue
```

- [ ] **Step 4: Persist success and failure alert logs**

Wrap notification send in its own try/except so alert attempts are always recorded.

```python
if next_stage is not None:
    recipient = ""
    try:
        send_result = await send_strategy_notification(monitor.code, next_stage, current_price, retract, monitor.user)
        recipient = send_result.recipient
        monitor.current_stage = next_stage
        monitor.last_alert_at = datetime.now()
        await ETFAlertLog.create(
            monitor=monitor,
            user=monitor.user,
            code=monitor.code,
            recipient=recipient,
            stage=next_stage,
            price=current_price,
            retract=retract,
            status="success",
            error_message="",
            sent_at=monitor.last_alert_at,
        )
        result.update({"triggered": True, "stage": next_stage, "retract": retract, "recipient": recipient})
        logger.info("ETF alert sent for {} stage {} to {}", monitor.code, next_stage, recipient)
    except Exception as exc:
        await ETFAlertLog.create(
            monitor=monitor,
            user=monitor.user,
            code=monitor.code,
            recipient=recipient,
            stage=next_stage,
            price=current_price,
            retract=retract,
            status="failed",
            error_message=str(exc),
            sent_at=None,
        )
        logger.exception("ETF alert send failed for {} stage {}", monitor.code, next_stage)
        result.update({"triggered": False, "stage": next_stage, "retract": retract, "error": str(exc)})
```

- [ ] **Step 5: Run compile check**

Run: `python -m compileall app/modules/etf`

Expected: command exits with code 0.

---

### Task 5: Add Frontend Test Email Button

**Files:**
- Modify: `web/src/api/index.ts`
- Modify: `web/src/views/ProfileView.vue`

- [ ] **Step 1: Add API client method**

In `web/src/api/index.ts`, add a response type and method.

```typescript
export interface TestEmailResult {
  recipient: string
  subject: string
}

export const api = {
  ...
  updateProfile: (data: { email: string }) => http.post<unknown, ApiResponse<UserInfo>>('/base/profile', data),
  testNotificationEmail: () => http.post<unknown, ApiResponse<TestEmailResult>>('/base/profile/test-email'),
  ...
}
```

- [ ] **Step 2: Add loading state**

In `web/src/views/ProfileView.vue`, add state.

```typescript
const testingEmail = ref(false)
```

- [ ] **Step 3: Add button beside save**

Replace the existing footer button container with two buttons.

```vue
<div class="mt-4 flex justify-end gap-2">
  <n-button :loading="testingEmail" @click="testEmail">测试发送邮件</n-button>
  <n-button type="primary" :loading="saving" @click="saveProfile">保存</n-button>
</div>
```

- [ ] **Step 4: Add click handler**

In `web/src/views/ProfileView.vue`, add the handler.

```typescript
async function testEmail() {
  testingEmail.value = true
  try {
    const res = await api.testNotificationEmail()
    message.success(`测试邮件已发送到 ${res.data.recipient}`)
  } finally {
    testingEmail.value = false
  }
}
```

- [ ] **Step 5: Build frontend**

Run: `npm.cmd --prefix web run build`

Expected: Vite build exits with code 0. The existing ECharts chunk-size warning may appear and is not a failure.

---

### Task 6: Update Playwright E2E Mock And Verify

**Files:**
- Modify: `tests/e2e_etf_playwright.py`

- [ ] **Step 1: Mock userinfo email**

In `install_mock_api`, return email for `/base/userinfo`.

```python
if path == "/base/userinfo":
    return route.fulfill(json=ok({"username": "admin", "email": "admin@example.com"}))
```

- [ ] **Step 2: Mock profile update and test email**

Add these route handlers.

```python
if path == "/base/profile" and request.method == "POST":
    return route.fulfill(json=ok({"username": "admin", "email": body.get("email", "admin@example.com")}))

if path == "/base/profile/test-email" and request.method == "POST":
    return route.fulfill(json=ok({"recipient": "admin@example.com", "subject": "【系统通知】邮件配置测试"}))
```

- [ ] **Step 3: Add profile page assertion**

After existing ETF assertions, navigate to profile and click the test-send button.

```python
page.goto(f"{args.base_url}/account/profile", wait_until="networkidle")
expect(page).to_have_url(f"{args.base_url}/account/profile")
profile_section = page.locator("section").first
expect(profile_section.get_by_text("admin")).to_be_visible(timeout=15000)
with page.expect_response(
    lambda response: "/api/v1/base/profile/test-email" in response.url and response.request.method == "POST"
):
    profile_section.get_by_role("button", name="测试发送邮件").click()
expect(page.get_by_text(re.compile("测试邮件已发送到"))).to_be_visible(timeout=15000)
screenshot(page, screenshot_dir, "05-profile-test-email")
```

- [ ] **Step 4: Run backend compile checks**

Run: `python -m compileall app/modules/user app/modules/etf app/db`

Expected: command exits with code 0.

- [ ] **Step 5: Run frontend build**

Run: `npm.cmd --prefix web run build`

Expected: command exits with code 0.

- [ ] **Step 6: Run Playwright with non-project Python**

Start Vite in a background job before this step if no dev server is running.

Run: `D:\Soft\python3.14\python.exe tests\e2e_etf_playwright.py --base-url http://127.0.0.1:5173 --screenshot-dir test-results/screenshots`

Expected: output contains `playwright etf e2e ok`.

---

## Self-Review

- Spec coverage: user-scoped monitors are covered by Tasks 1 and 2; user email alert delivery and test-send are covered by Task 3; alert records are covered by Tasks 1 and 4; clearer monitor skip handling and logs are covered by Task 4; frontend interaction and E2E verification are covered by Tasks 5 and 6.
- Placeholder scan: no deferred implementation markers remain.
- Type consistency: `run_monitor_once(code, force, user)`, `send_strategy_notification(..., user)`, `ETFAlertLog`, and `testNotificationEmail` names are consistent across tasks.

