from fastapi import APIRouter, Depends, HTTPException, Query

from app.common.dependencies import get_current_user
from app.common.responses import success
from app.modules.etf.models import ETFMonitor
from app.modules.etf.monitor import run_monitor_once
from app.modules.etf.schemas import ETFMonitorCreate, ETFMonitorUpdate, ETFSyncIn
from app.modules.etf.service import (
    ensure_seed_history,
    get_detail,
    get_monitor_or_none,
    list_monitors,
    sync_monitors,
)
from app.modules.etf.market_data import normalize_code
from app.modules.user.models import User

router = APIRouter(prefix="/api/v1/etf", tags=["etf"])


@router.get("/list")
async def list_etf(_: User = Depends(get_current_user)):
    return success(await list_monitors())


@router.post("/create")
async def create_etf(payload: ETFMonitorCreate, _: User = Depends(get_current_user)):
    code = normalize_code(payload.code)
    if await ETFMonitor.filter(code=code).exists():
        raise HTTPException(status_code=400, detail="标的代码已存在")
    monitor = await ETFMonitor.create(
        code=code,
        name=payload.name.strip(),
        is_active=payload.is_active,
        time_range=payload.time_range,
        x_drop=payload.x_drop,
        y_step=payload.y_step,
    )
    sync_result = await ensure_seed_history(monitor)
    return success({"monitor": await get_detail(code), "sync": sync_result}, msg="Created Successfully")


@router.post("/update")
async def update_etf(payload: ETFMonitorUpdate, _: User = Depends(get_current_user)):
    monitor = await get_monitor_or_none(payload.code)
    if not monitor:
        raise HTTPException(status_code=404, detail="标的不存在")
    next_time_range = payload.time_range if payload.time_range is not None else monitor.time_range
    next_x_drop = payload.x_drop if payload.x_drop is not None else monitor.x_drop
    next_y_step = payload.y_step if payload.y_step is not None else monitor.y_step
    should_reset_stage = monitor.time_range != next_time_range or monitor.x_drop != next_x_drop or monitor.y_step != next_y_step
    if payload.name is not None:
        monitor.name = payload.name.strip()
    if payload.is_active is not None:
        monitor.is_active = payload.is_active
    monitor.time_range = next_time_range
    monitor.x_drop = next_x_drop
    monitor.y_step = next_y_step
    if should_reset_stage:
        monitor.current_stage = 0
    await monitor.save(
        update_fields=["name", "is_active", "time_range", "x_drop", "y_step", "current_stage", "updated_at"]
    )
    return success(await get_detail(monitor.code), msg="Updated Successfully")


@router.delete("/delete")
async def delete_etf(code: str = Query(...), _: User = Depends(get_current_user)):
    monitor = await get_monitor_or_none(code)
    if not monitor:
        raise HTTPException(status_code=404, detail="标的不存在")
    await monitor.delete()
    return success(msg="Deleted Successfully")


@router.get("/detail")
async def detail_etf(code: str = Query(...), _: User = Depends(get_current_user)):
    detail = await get_detail(code)
    if not detail:
        raise HTTPException(status_code=404, detail="标的不存在")
    return success(detail)


@router.post("/sync")
async def sync_etf(payload: ETFSyncIn, _: User = Depends(get_current_user)):
    if payload.code and not await get_monitor_or_none(payload.code):
        raise HTTPException(status_code=404, detail="标的不存在")
    return success(await sync_monitors(payload.code), msg="Synced Successfully")


@router.post("/monitor/run")
async def run_etf_monitor(payload: ETFSyncIn, _: User = Depends(get_current_user)):
    if payload.code and not await get_monitor_or_none(payload.code):
        raise HTTPException(status_code=404, detail="标的不存在")
    return success(await run_monitor_once(payload.code, force=True), msg="Monitor Checked")
