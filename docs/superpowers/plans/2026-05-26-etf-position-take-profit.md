# ETF 持仓与上涨分批止盈实施计划

> **给执行代理的要求：** 实施本计划时必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans`，按任务逐项执行。步骤使用 checkbox（`- [ ]`）跟踪状态。

**目标：** 为 ETF 监控增加持仓成本、持仓份数维护，并增加基于每份持仓成本价的上涨分批止盈提醒。

**架构：** 在现有 ETF 监控记录上扩展字段，不新增独立业务模块。现有回撤提醒继续使用 `is_active/current_stage`；上涨分批止盈使用独立开关和独立阶段字段；调度器在一次行情检查中同时评估两类策略。

**技术栈：** FastAPI、Pydantic、Tortoise ORM、PostgreSQL 结构维护 SQL、Vue 3、Naive UI、ECharts、Axios、Python Playwright。

---

## 文件结构

- 修改 `app/modules/etf/models.py`：给 `ETFMonitor` 增加持仓字段和止盈策略字段。
- 修改 `app/modules/etf/schema_maintenance.py`：为 PostgreSQL 增加幂等补字段 SQL。
- 修改 `app/modules/etf/schemas.py`：创建和更新接口支持持仓成本、持仓份数、止盈开关、首次涨幅、后续步长。
- 修改 `app/modules/etf/api.py`：创建和更新时保存新字段；相关参数变化时重置止盈阶段。
- 修改 `app/modules/etf/service.py`：列表和详情返回持仓市值、浮动盈亏、收益率、止盈状态。
- 修改 `app/modules/etf/monitor.py`：独立评估上涨分批止盈触发逻辑。
- 修改 `app/modules/etf/notification.py`：区分回撤提醒和止盈提醒邮件。
- 修改 `web/src/api/index.ts`：补充前端请求和响应类型。
- 修改 `web/src/views/EtfMonitorView.vue`：增加列表列、新增弹窗输入、详情里的止盈配置区。
- 修改 `tests/e2e_etf_playwright.py`：更新 Mock API 数据并验证页面交互。
- 修改 `tests/api_smoke.py`：创建/更新 ETF 时覆盖新字段。

---

### 任务 1：增加后端数据字段

**文件：**
- 修改：`app/modules/etf/models.py`
- 修改：`app/modules/etf/schema_maintenance.py`
- 修改：`app/modules/etf/schemas.py`

- [ ] **步骤 1：增加 ORM 字段**

在 `app/modules/etf/models.py` 的 `ETFMonitor` 中，把这些字段加到 `y_step` 后、`current_stage` 前。

```python
    holding_cost = fields.FloatField(null=True)
    holding_shares = fields.FloatField(default=0)
    take_profit_enabled = fields.BooleanField(default=False, index=True)
    take_profit_first_rise = fields.FloatField(default=0.15)
    take_profit_step = fields.FloatField(default=0.05)
    take_profit_stage = fields.IntField(default=0)
    take_profit_last_alert_at = fields.DatetimeField(null=True)
```

- [ ] **步骤 2：增加 PostgreSQL 补字段 SQL**

在 `app/modules/etf/schema_maintenance.py` 中追加对 `etf_monitor` 的幂等字段维护。若现有文件已有独立 `ALTER TABLE etf_monitor`，优先新增一个独立语句，不重写无关 SQL。

```sql
        ALTER TABLE etf_monitor
            ADD COLUMN IF NOT EXISTS holding_cost DOUBLE PRECISION NULL,
            ADD COLUMN IF NOT EXISTS holding_shares DOUBLE PRECISION NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS take_profit_enabled BOOLEAN NOT NULL DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS take_profit_first_rise DOUBLE PRECISION NOT NULL DEFAULT 0.15,
            ADD COLUMN IF NOT EXISTS take_profit_step DOUBLE PRECISION NOT NULL DEFAULT 0.05,
            ADD COLUMN IF NOT EXISTS take_profit_stage INTEGER NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS take_profit_last_alert_at TIMESTAMP NULL;

        CREATE INDEX IF NOT EXISTS idx_etf_monitor_take_profit_enabled
            ON etf_monitor(take_profit_enabled);
```

- [ ] **步骤 3：创建接口增加字段**

在 `app/modules/etf/schemas.py` 的 `ETFMonitorCreate` 中增加：

```python
    holding_cost: float | None = Field(default=None, ge=0)
    holding_shares: float = Field(default=0, ge=0)
    take_profit_enabled: bool = False
    take_profit_first_rise: float = Field(default=0.15, ge=0, le=10)
    take_profit_step: float = Field(default=0.05, ge=0, le=10)
```

- [ ] **步骤 4：更新接口增加字段**

在 `app/modules/etf/schemas.py` 的 `ETFMonitorUpdate` 中增加：

```python
    holding_cost: float | None = Field(default=None, ge=0)
    holding_shares: float | None = Field(default=None, ge=0)
    take_profit_enabled: bool | None = None
    take_profit_first_rise: float | None = Field(default=None, ge=0, le=10)
    take_profit_step: float | None = Field(default=None, ge=0, le=10)
```

- [ ] **步骤 5：编译后端**

运行：`python -m compileall app/modules/etf`

预期：命令退出码为 0。

---

### 任务 2：保存创建和更新配置

**文件：**
- 修改：`app/modules/etf/api.py`
- 修改：`tests/api_smoke.py`

- [ ] **步骤 1：创建 ETF 时保存新字段**

在 `app/modules/etf/api.py` 的 `ETFMonitor.create` 中增加：

```python
        holding_cost=payload.holding_cost,
        holding_shares=payload.holding_shares,
        take_profit_enabled=payload.take_profit_enabled,
        take_profit_first_rise=payload.take_profit_first_rise,
        take_profit_step=payload.take_profit_step,
```

- [ ] **步骤 2：更新 ETF 时计算新值**

在 `update_etf` 中，现有回撤参数计算后增加：

```python
    next_holding_cost = payload.holding_cost if payload.holding_cost is not None else monitor.holding_cost
    next_holding_shares = payload.holding_shares if payload.holding_shares is not None else monitor.holding_shares
    next_take_profit_first_rise = (
        payload.take_profit_first_rise
        if payload.take_profit_first_rise is not None
        else monitor.take_profit_first_rise
    )
    next_take_profit_step = payload.take_profit_step if payload.take_profit_step is not None else monitor.take_profit_step
    should_reset_take_profit_stage = (
        monitor.holding_cost != next_holding_cost
        or monitor.take_profit_first_rise != next_take_profit_first_rise
        or monitor.take_profit_step != next_take_profit_step
    )
```

- [ ] **步骤 3：更新 ETF 时赋值**

在 `update_etf` 保存前增加：

```python
    monitor.holding_cost = next_holding_cost
    monitor.holding_shares = next_holding_shares
    if payload.take_profit_enabled is not None:
        monitor.take_profit_enabled = payload.take_profit_enabled
    monitor.take_profit_first_rise = next_take_profit_first_rise
    monitor.take_profit_step = next_take_profit_step
    if should_reset_take_profit_stage:
        monitor.take_profit_stage = 0
```

- [ ] **步骤 4：扩展保存字段列表**

在 `monitor.save(update_fields=[...])` 中增加：

```python
        "holding_cost",
        "holding_shares",
        "take_profit_enabled",
        "take_profit_first_rise",
        "take_profit_step",
        "take_profit_stage",
```

- [ ] **步骤 5：更新 API smoke 创建入参**

在 `tests/api_smoke.py` 的 ETF create payload 中增加：

```python
                "holding_cost": 1.0,
                "holding_shares": 1000,
                "take_profit_enabled": True,
                "take_profit_first_rise": 0.15,
                "take_profit_step": 0.05,
```

- [ ] **步骤 6：更新 API smoke 断言**

创建断言后增加：

```python
    assert created["data"]["monitor"]["holding_cost"] == 1.0, created
    assert created["data"]["monitor"]["holding_shares"] == 1000, created
    assert created["data"]["monitor"]["take_profit_enabled"] is True, created
```

更新 payload 中增加：

```python
                "holding_cost": 1.2,
                "holding_shares": 1200,
                "take_profit_enabled": False,
```

更新断言后增加：

```python
    assert updated["data"]["holding_cost"] == 1.2, updated
    assert updated["data"]["holding_shares"] == 1200, updated
    assert updated["data"]["take_profit_enabled"] is False, updated
```

- [ ] **步骤 7：运行后端检查**

运行：`python -m compileall app/modules/etf tests`

预期：命令退出码为 0。

---

### 任务 3：返回持仓计算指标

**文件：**
- 修改：`app/modules/etf/service.py`

- [ ] **步骤 1：增加持仓指标计算函数**

在 `app/modules/etf/service.py` 的计算类辅助函数附近增加：

```python
def build_position_metrics(monitor: ETFMonitor, current_price: float | None) -> dict:
    holding_cost = monitor.holding_cost
    holding_shares = monitor.holding_shares or 0
    market_value = None
    floating_profit = None
    profit_rate = None
    take_profit_rise = None
    next_take_profit_rise = None

    if isinstance(current_price, (int, float)) and holding_shares > 0:
        market_value = current_price * holding_shares

    if isinstance(current_price, (int, float)) and isinstance(holding_cost, (int, float)) and holding_cost > 0:
        floating_profit = (current_price - holding_cost) * holding_shares
        profit_rate = (current_price - holding_cost) / holding_cost
        take_profit_rise = profit_rate
        next_take_profit_rise = monitor.take_profit_first_rise + (monitor.take_profit_stage * monitor.take_profit_step)

    return {
        "holding_cost": holding_cost,
        "holding_shares": holding_shares,
        "market_value": market_value,
        "floating_profit": floating_profit,
        "profit_rate": profit_rate,
        "take_profit_enabled": monitor.take_profit_enabled,
        "take_profit_first_rise": monitor.take_profit_first_rise,
        "take_profit_step": monitor.take_profit_step,
        "take_profit_stage": monitor.take_profit_stage,
        "take_profit_last_alert_at": (
            monitor.take_profit_last_alert_at.isoformat() if monitor.take_profit_last_alert_at else None
        ),
        "take_profit_rise": take_profit_rise,
        "next_take_profit_rise": next_take_profit_rise,
    }
```

- [ ] **步骤 2：详情快照返回指标**

在 `serialize_monitor_snapshot` 中，计算完 `retract_info` 后增加：

```python
    position_info = build_position_metrics(monitor, current_price)
```

返回 dict 中增加：

```python
        **position_info,
```

- [ ] **步骤 3：列表项返回指标**

在 `serialize_monitor_list_item` 中，计算完 `retract_info` 后增加：

```python
    position_info = build_position_metrics(monitor, current_price)
```

返回 dict 中增加：

```python
        **position_info,
```

- [ ] **步骤 4：编译后端**

运行：`python -m compileall app/modules/etf`

预期：命令退出码为 0。

---

### 任务 4：增加止盈监控逻辑

**文件：**
- 修改：`app/modules/etf/notification.py`
- 修改：`app/modules/etf/monitor.py`

- [ ] **步骤 1：增加止盈邮件构造函数**

在 `app/modules/etf/notification.py` 中增加：

```python
def build_take_profit_email(code: str, stage: int, price: float, rise: float, holding_cost: float) -> tuple[str, str]:
    subject = "上涨分批止盈提醒"
    safe_code = html.escape(code)
    body = f"""
<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8" /></head>
<body>
  <p>ETF {safe_code} 已达到第 {stage} 次上涨分批止盈提醒。</p>
  <p>当前价格：{price:.4f}</p>
  <p>每份持仓成本：{holding_cost:.4f}</p>
  <p>相对成本涨幅：{rise:.2%}</p>
</body>
</html>
"""
    return subject, body
```

- [ ] **步骤 2：增加止盈邮件发送函数**

在 `app/modules/etf/notification.py` 中增加：

```python
async def send_take_profit_notification(
    code: str,
    stage: int,
    price: float,
    rise: float,
    holding_cost: float,
    user: User | None = None,
) -> EmailSendResult:
    subject, body = build_take_profit_email(code, stage, price, rise, holding_cost)
    recipient = await _resolve_recipient_email(user)
    await asyncio.to_thread(_send_email, subject, body, recipient)
    return EmailSendResult(recipient=recipient, subject=subject)
```

- [ ] **步骤 3：监控模块导入止盈发送函数**

在 `app/modules/etf/monitor.py` 中更新导入：

```python
from app.modules.etf.notification import send_strategy_notification, send_take_profit_notification
```

- [ ] **步骤 4：增加止盈阶段判断**

在监控循环内，拿到 `current_price` 后、回撤逻辑执行后，增加：

```python
            if (
                monitor.take_profit_enabled
                and isinstance(monitor.holding_cost, (int, float))
                and monitor.holding_cost > 0
                and current_price > 0
            ):
                rise = (current_price - monitor.holding_cost) / monitor.holding_cost
                next_take_profit_line = monitor.take_profit_first_rise + (
                    monitor.take_profit_stage * monitor.take_profit_step
                )
                if rise >= next_take_profit_line:
                    take_profit_stage = monitor.take_profit_stage + 1
                    send_result = await send_take_profit_notification(
                        monitor.code,
                        take_profit_stage,
                        current_price,
                        rise,
                        monitor.holding_cost,
                        monitor.user,
                    )
                    monitor.take_profit_stage = take_profit_stage
                    monitor.take_profit_last_alert_at = datetime.now()
                    result.update(
                        {
                            "take_profit_triggered": True,
                            "take_profit_stage": take_profit_stage,
                            "take_profit_rise": rise,
                            "take_profit_recipient": send_result.recipient,
                        }
                    )
```

- [ ] **步骤 5：保存止盈状态字段**

扩展最终的 `monitor.save(update_fields=[...])` 字段列表：

```python
                "take_profit_stage",
                "take_profit_last_alert_at",
```

- [ ] **步骤 6：编译后端**

运行：`python -m compileall app/modules/etf`

预期：命令退出码为 0。

---

### 任务 5：更新前端类型和接口入参

**文件：**
- 修改：`web/src/api/index.ts`

- [ ] **步骤 1：扩展列表记录类型**

在 `EtfMonitorRecord` 中增加：

```typescript
  holding_cost?: number | null
  holding_shares?: number | null
  market_value?: number | null
  floating_profit?: number | null
  profit_rate?: number | null
  take_profit_enabled?: boolean
  take_profit_first_rise?: number
  take_profit_step?: number
  take_profit_stage?: number
  take_profit_rise?: number | null
  next_take_profit_rise?: number | null
  take_profit_last_alert_at?: string | null
```

- [ ] **步骤 2：扩展详情记录类型**

在 `EtfDetailRecord` 中增加同样字段：

```typescript
  holding_cost?: number | null
  holding_shares?: number | null
  market_value?: number | null
  floating_profit?: number | null
  profit_rate?: number | null
  take_profit_enabled?: boolean
  take_profit_first_rise?: number
  take_profit_step?: number
  take_profit_stage?: number
  take_profit_rise?: number | null
  next_take_profit_rise?: number | null
  take_profit_last_alert_at?: string | null
```

- [ ] **步骤 3：扩展创建入参类型**

在 `createEtf` 的 data 类型中增加：

```typescript
    holding_cost?: number | null
    holding_shares?: number
    take_profit_enabled?: boolean
    take_profit_first_rise?: number
    take_profit_step?: number
```

- [ ] **步骤 4：扩展更新入参类型**

在 `updateEtf` 的 data 类型中增加：

```typescript
    holding_cost?: number | null
    holding_shares?: number
    take_profit_enabled?: boolean
    take_profit_first_rise?: number
    take_profit_step?: number
```

- [ ] **步骤 5：构建前端**

运行：`npm.cmd --prefix web run build`

预期：命令退出码为 0。

---

### 任务 6：更新 ETF 监控页面

**文件：**
- 修改：`web/src/views/EtfMonitorView.vue`

- [ ] **步骤 1：新增弹窗增加持仓字段**

在 `createForm` 中增加：

```typescript
  holding_cost: null as number | null,
  holding_shares: 0,
```

在 `openCreate` 中重置：

```typescript
  Object.assign(createForm, { code: '', name: '', time_range: '3y', holding_cost: null, holding_shares: 0 })
```

在新增弹窗表单中增加：

```vue
        <n-form-item label="持仓成本" path="holding_cost">
          <n-input-number v-model:value="createForm.holding_cost" :min="0" :precision="4" class="w-full" />
        </n-form-item>
        <n-form-item label="持仓份数" path="holding_shares">
          <n-input-number v-model:value="createForm.holding_shares" :min="0" :precision="2" class="w-full" />
        </n-form-item>
```

- [ ] **步骤 2：创建请求发送持仓字段**

在 `saveCreate` 的 `api.createEtf` 入参中增加：

```typescript
      holding_cost: createForm.holding_cost,
      holding_shares: createForm.holding_shares,
      take_profit_enabled: false,
      take_profit_first_rise: 0.15,
      take_profit_step: 0.05,
```

- [ ] **步骤 3：详情表单增加字段**

在 `detailForm` 中增加：

```typescript
  holding_cost: null as number | null,
  holding_shares: 0,
  take_profit_enabled: false,
  take_profit_first_rise_percent: 15,
  take_profit_step_percent: 5,
```

在 `fillDetailForm` 中增加：

```typescript
    holding_cost: data.holding_cost ?? null,
    holding_shares: data.holding_shares ?? 0,
    take_profit_enabled: data.take_profit_enabled ?? false,
    take_profit_first_rise_percent: ratioToPercent(data.take_profit_first_rise),
    take_profit_step_percent: ratioToPercent(data.take_profit_step),
```

- [ ] **步骤 4：列表增加持仓列**

在 `columns` 中，现价列后增加：

```typescript
  { title: '持仓成本', key: 'holding_cost', width: 120, render: (row) => formatPrice(row.holding_cost) },
  { title: '持仓份数', key: 'holding_shares', width: 120, render: (row) => formatNumber(row.holding_shares) },
  {
    title: '收益率',
    key: 'profit_rate',
    width: 120,
    render(row) {
      return h(NTag, { size: 'small', type: getChangeTagType(row.profit_rate), bordered: false }, { default: () => formatPercent(row.profit_rate) })
    },
  },
  { title: '浮动盈亏', key: 'floating_profit', width: 130, render: (row) => formatMoney(row.floating_profit) },
```

增加格式化函数：

```typescript
function formatNumber(value?: number | null) {
  return typeof value === 'number' ? value.toFixed(2) : '-'
}

function formatMoney(value?: number | null) {
  return typeof value === 'number' ? value.toFixed(2) : '-'
}
```

- [ ] **步骤 5：详情增加上涨分批止盈配置区**

在详情弹窗中，现有回撤参数卡片下方增加：

```vue
                <n-card size="small" title="上涨分批止盈" :bordered="false">
                  <div class="mb-4 flex items-center justify-between gap-4">
                    <div>
                      <p class="font-medium text-slate-900">止盈提醒</p>
                      <p class="mt-1 text-sm text-slate-500">以每份持仓成本为基准，达到首次涨幅后提醒，之后每上涨一个步长再次提醒。</p>
                    </div>
                    <n-switch v-model:value="detailForm.take_profit_enabled" />
                  </div>
                  <n-form :model="detailForm" label-placement="left" :label-width="116">
                    <div class="grid gap-3 lg:grid-cols-4">
                      <n-form-item label="持仓成本">
                        <n-input-number v-model:value="detailForm.holding_cost" :min="0" :precision="4" class="w-full" />
                      </n-form-item>
                      <n-form-item label="持仓份数">
                        <n-input-number v-model:value="detailForm.holding_shares" :min="0" :precision="2" class="w-full" />
                      </n-form-item>
                      <n-form-item label="首次涨幅">
                        <n-input-number v-model:value="detailForm.take_profit_first_rise_percent" :min="0" :max="1000" :precision="2" class="w-full">
                          <template #suffix>%</template>
                        </n-input-number>
                      </n-form-item>
                      <n-form-item label="后续步长">
                        <n-input-number v-model:value="detailForm.take_profit_step_percent" :min="0" :max="1000" :precision="2" class="w-full">
                          <template #suffix>%</template>
                        </n-input-number>
                      </n-form-item>
                    </div>
                  </n-form>
                  <div class="mt-2 grid gap-3 text-sm md:grid-cols-4">
                    <InfoRow label="持仓市值" :value="formatMoney(detail?.market_value)" />
                    <InfoRow label="浮动盈亏" :value="formatMoney(detail?.floating_profit)" />
                    <InfoRow label="收益率" :value="formatPercent(detail?.profit_rate)" />
                    <InfoRow label="下次止盈线" :value="formatPercent(detail?.next_take_profit_rise)" />
                  </div>
                </n-card>
```

- [ ] **步骤 6：更新请求发送止盈字段**

在 `saveDetailSettings` 的 `api.updateEtf` 入参中增加：

```typescript
      holding_cost: detailForm.holding_cost,
      holding_shares: detailForm.holding_shares,
      take_profit_enabled: detailForm.take_profit_enabled,
      take_profit_first_rise: percentToRatio(detailForm.take_profit_first_rise_percent),
      take_profit_step: percentToRatio(detailForm.take_profit_step_percent),
```

- [ ] **步骤 7：构建前端**

运行：`npm.cmd --prefix web run build`

预期：命令退出码为 0。

---

### 任务 7：更新 Playwright E2E

**文件：**
- 修改：`tests/e2e_etf_playwright.py`

- [ ] **步骤 1：扩展 Mock ETF 数据**

在 `make_monitor` 返回值中增加：

```python
        "holding_cost": 3.800,
        "holding_shares": 1000,
        "market_value": round(price * 1000, 2),
        "floating_profit": round((price - 3.800) * 1000, 2),
        "profit_rate": (price - 3.800) / 3.800,
        "take_profit_enabled": True,
        "take_profit_first_rise": 0.15,
        "take_profit_step": 0.05,
        "take_profit_stage": 0,
        "take_profit_rise": (price - 3.800) / 3.800,
        "next_take_profit_rise": 0.15,
        "take_profit_last_alert_at": None,
```

- [ ] **步骤 2：Mock 创建接口保存新字段**

在 `/etf/create` handler 中增加：

```python
            record["holding_cost"] = body.get("holding_cost")
            record["holding_shares"] = body.get("holding_shares", 0)
            record["take_profit_enabled"] = body.get("take_profit_enabled", False)
            record["take_profit_first_rise"] = body.get("take_profit_first_rise", 0.15)
            record["take_profit_step"] = body.get("take_profit_step", 0.05)
```

- [ ] **步骤 3：新增弹窗填写持仓输入**

在现有新增弹窗名称输入后增加：

```python
        create_dialog.locator("input").nth(2).fill("1.2340")
        create_dialog.locator("input").nth(3).fill("2000")
```

如果 Naive UI input 顺序变化，定位必须限定在 dialog 内，按表单项文本重新选择，不能使用全页面 placeholder 模糊定位。

- [ ] **步骤 4：断言列表展示持仓字段**

在表格可见断言后增加：

```python
        expect(table.get_by_text("持仓成本")).to_be_visible()
        expect(table.get_by_text("收益率")).to_be_visible()
```

- [ ] **步骤 5：断言详情展示止盈配置**

打开详情弹窗后增加：

```python
        expect(detail_dialog.get_by_text("上涨分批止盈")).to_be_visible(timeout=15000)
        expect(detail_dialog.get_by_text("止盈提醒")).to_be_visible(timeout=15000)
        expect(detail_dialog.get_by_text("下次止盈线")).to_be_visible(timeout=15000)
```

- [ ] **步骤 6：使用非项目 Python 运行 Playwright**

如无 Vite dev server，先用后台任务启动。

运行：`D:\Soft\python3.14\python.exe tests\e2e_etf_playwright.py --base-url http://127.0.0.1:5173 --screenshot-dir test-results/screenshots`

预期：输出包含 `playwright etf e2e ok`。

---

### 任务 8：最终验证

**文件：**
- 不修改源文件。

- [ ] **步骤 1：编译后端**

运行：`python -m compileall app tests`

预期：命令退出码为 0。

- [ ] **步骤 2：构建前端**

运行：`npm.cmd --prefix web run build`

预期：命令退出码为 0。

- [ ] **步骤 3：后端可用时运行 API smoke**

运行：`python tests/api_smoke.py --api-url http://127.0.0.1:8000/api/v1`

预期：输出包含 `api smoke ok`。

- [ ] **步骤 4：运行项目要求的 Playwright 校验**

必须使用项目虚拟环境之外的本地 Python。

运行：`D:\Soft\python3.14\python.exe tests\e2e_etf_playwright.py --base-url http://127.0.0.1:5173 --screenshot-dir test-results/screenshots`

预期：输出包含 `playwright etf e2e ok`。

---

## 完成标准

- ETF 列表展示持仓成本、持仓份数、现价、持仓市值、浮动盈亏、收益率。
- 新增和详情编辑都能保存并回显持仓成本和持仓份数。
- 上涨分批止盈提醒有独立开关，不影响现有回撤提醒开关。
- 止盈涨幅按 `(current_price - holding_cost) / holding_cost` 计算。
- 首次提醒按 `take_profit_first_rise` 触发；后续提醒按 `take_profit_step` 递增触发。
- 同一止盈阶段不会重复提醒。
- 现有回撤提醒功能仍可使用。
- 后端编译、前端构建、API smoke、非项目 Python Playwright 校验通过。

## 自检

- 覆盖范围：持仓维护由任务 1、2、3、5、6、7 覆盖；止盈配置和运行时提醒由任务 1、2、4、5、6、7 覆盖；最终验证由任务 8 覆盖。
- 占位符检查：没有待补充的 TBD/TODO，也没有延后实现项。
- 类型一致性：后端、前端、测试中使用同一组字段名：`holding_cost`、`holding_shares`、`take_profit_enabled`、`take_profit_first_rise`、`take_profit_step`、`take_profit_stage`。
