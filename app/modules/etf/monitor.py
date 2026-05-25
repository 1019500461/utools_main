from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

from loguru import logger

from app.modules.etf.market_data import fetch_realtime_quote
from app.modules.etf.notification import send_strategy_notification
from app.modules.etf.service import get_peak_info, is_market_check_time, monitors_for_runtime


_scheduler_task: asyncio.Task | None = None
_last_scheduler_run: datetime | None = None


async def run_monitor_once(code: str | None = None, force: bool = False) -> list[dict[str, Any]]:
    if not force and not is_market_check_time():
        return [{"skipped": True, "reason": "outside_market_time"}]

    results: list[dict[str, Any]] = []
    monitors = await monitors_for_runtime(code)
    for monitor in monitors:
        result: dict[str, Any] = {"code": monitor.code, "triggered": False}
        try:
            peak_info = await get_peak_info(monitor.code, monitor.time_range)
            peak_price = peak_info["peak"]
            quote = await fetch_realtime_quote(monitor.code)
            current_price = quote.current_price
            if not peak_price or not current_price:
                result.update({"skipped": True, "reason": "missing_price"})
                results.append(result)
                continue

            retract = (peak_price - current_price) / peak_price
            monitor.last_checked_at = datetime.now()

            if retract <= 0:
                monitor.current_stage = 0
                await monitor.save(update_fields=["current_stage", "last_checked_at", "updated_at"])
                result.update({"retract": retract, "current_stage": 0, "reset": True})
                results.append(result)
                continue

            next_stage = None
            if monitor.current_stage == 0 and retract >= monitor.x_drop:
                next_stage = 1
            elif monitor.current_stage > 0:
                next_trigger_line = monitor.x_drop + (monitor.current_stage * monitor.y_step)
                if retract >= next_trigger_line:
                    next_stage = monitor.current_stage + 1

            if next_stage is not None:
                await send_strategy_notification(monitor.code, next_stage, current_price, retract)
                monitor.current_stage = next_stage
                monitor.last_alert_at = datetime.now()
                result.update({"triggered": True, "stage": next_stage, "retract": retract})

            await monitor.save(update_fields=["current_stage", "last_checked_at", "last_alert_at", "updated_at"])
        except Exception as exc:
            logger.exception("ETF monitor failed for {}", monitor.code)
            result.update({"error": str(exc)})
        results.append(result)
    return results


async def _scheduler_loop() -> None:
    global _last_scheduler_run
    while True:
        try:
            now = datetime.now()
            should_run = is_market_check_time(now) and (
                _last_scheduler_run is None
                or now - _last_scheduler_run >= timedelta(minutes=29)
                or (now.hour == 15 and now.minute == 1)
            )
            if should_run:
                _last_scheduler_run = now
                await run_monitor_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("ETF scheduler loop failed")
        await asyncio.sleep(60)


def start_scheduler() -> None:
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        return
    _scheduler_task = asyncio.create_task(_scheduler_loop())


async def stop_scheduler() -> None:
    global _scheduler_task
    if not _scheduler_task:
        return
    _scheduler_task.cancel()
    try:
        await _scheduler_task
    except asyncio.CancelledError:
        pass
    _scheduler_task = None
