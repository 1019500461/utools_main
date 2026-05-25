from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime, time, timedelta

from tortoise.expressions import Q
from tortoise.functions import Max

from app.modules.etf.market_data import HistoryBar, RealtimeQuote, fetch_qfq_history, fetch_realtime_quote, normalize_code
from app.modules.etf.models import ETFHistory, ETFMonitor


SUPPORTED_TIME_RANGES = {"3y", "5y", "all"}
ALL_HISTORY_START = date(1990, 1, 1)


def today_local() -> date:
    return date.today()


def is_weekend(day: date) -> bool:
    return day.weekday() >= 5


def history_start_for_range(time_range: str, today: date | None = None) -> date:
    if time_range not in SUPPORTED_TIME_RANGES:
        raise ValueError(f"unsupported time_range: {time_range}")

    current = today or today_local()
    if time_range == "3y":
        return current - timedelta(days=365 * 3)
    if time_range == "5y":
        return current - timedelta(days=365 * 5)
    return ALL_HISTORY_START


async def bulk_insert_history(bars: list[HistoryBar]) -> int:
    if not bars:
        return 0

    normalized_codes = {normalize_code(bar.code) for bar in bars}
    dates = {bar.date for bar in bars}
    before_count = await ETFHistory.filter(code__in=normalized_codes, date__in=dates).count()
    instances = [
        ETFHistory(
            code=normalize_code(bar.code),
            date=bar.date,
            open=bar.open,
            close=bar.close,
            high=bar.high,
            low=bar.low,
        )
        for bar in bars
    ]
    await ETFHistory.bulk_create(instances, batch_size=500, ignore_conflicts=True)
    after_count = await ETFHistory.filter(code__in=normalized_codes, date__in=dates).count()
    return max(after_count - before_count, 0)


async def seed_history_for_monitor(monitor: ETFMonitor, end_date: date | None = None) -> dict:
    current = end_date or today_local()
    start = history_start_for_range(monitor.time_range, current)
    bars = await fetch_qfq_history(monitor.code, start, current)
    inserted = await bulk_insert_history(bars)
    return {
        "code": normalize_code(monitor.code),
        "requested_start": start.isoformat(),
        "requested_end": current.isoformat(),
        "fetched": len(bars),
        "inserted": inserted,
        "skipped": False,
        "message": "OK" if bars else "接口未返回历史行情，可能为休市或代码无数据",
    }


async def sync_history_incremental(monitor: ETFMonitor, end_date: date | None = None) -> dict:
    current = end_date or today_local()
    normalized = normalize_code(monitor.code)
    if is_weekend(current):
        return {
            "code": normalized,
            "requested_start": current.isoformat(),
            "requested_end": current.isoformat(),
            "fetched": 0,
            "inserted": 0,
            "skipped": True,
            "message": "周末跳过同步",
        }

    latest = await ETFHistory.filter(code=normalized).order_by("-date").first()
    if not latest:
        return await seed_history_for_monitor(monitor, current)

    latest_date = date.fromisoformat(latest.date)
    gap_days = max((current - latest_date).days, 0)
    if gap_days == 0:
        return {
            "code": normalized,
            "requested_start": latest.date,
            "requested_end": current.isoformat(),
            "fetched": 0,
            "inserted": 0,
            "skipped": True,
            "message": "本地已是最新日期",
        }

    start = max(latest_date - timedelta(days=3), current - timedelta(days=gap_days + 3))
    bars = await fetch_qfq_history(normalized, start, current)
    inserted = await bulk_insert_history(bars)
    return {
        "code": normalized,
        "requested_start": start.isoformat(),
        "requested_end": current.isoformat(),
        "fetched": len(bars),
        "inserted": inserted,
        "skipped": False,
        "message": "OK" if bars else "接口未返回增量行情，可能为法定节假日或代码无数据",
    }


async def ensure_monitor_history(monitor: ETFMonitor) -> dict | None:
    exists = await ETFHistory.filter(code=normalize_code(monitor.code)).exists()
    if exists:
        return None
    return await seed_history_for_monitor(monitor)


async def sync_all_active_monitors() -> list[dict]:
    monitors = await ETFMonitor.filter(is_active=True).order_by("code")
    results = []
    for monitor in monitors:
        results.append(await sync_history_incremental(monitor))
    return results


async def sync_monitors(code: str | None = None) -> list[dict]:
    query = ETFMonitor.all().order_by("code")
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


async def get_history_bars(code: str, time_range: str = "all") -> list[dict]:
    normalized = normalize_code(code)
    query = ETFHistory.filter(code=normalized)
    if time_range != "all":
        query = query.filter(date__gte=history_start_for_range(time_range).isoformat())
    bars = await query.order_by("date")
    return [
        {
            "code": bar.code,
            "date": bar.date,
            "open": bar.open,
            "close": bar.close,
            "high": bar.high,
            "low": bar.low,
        }
        for bar in bars
    ]


async def calculate_peak(code: str, time_range: str) -> dict:
    normalized = normalize_code(code)
    if time_range not in SUPPORTED_TIME_RANGES:
        raise ValueError(f"unsupported time_range: {time_range}")

    first_bar = await ETFHistory.filter(code=normalized).order_by("date").first()
    if not first_bar:
        return {"peak_price": None, "start_date": None, "fallback_to_all": False, "message": "暂无历史行情"}

    expected_start = history_start_for_range(time_range)
    fallback_to_all = time_range != "all" and date.fromisoformat(first_bar.date) > expected_start
    start_date = first_bar.date if fallback_to_all else expected_start.isoformat()
    result = await ETFHistory.filter(code=normalized, date__gte=start_date).annotate(peak_price=Max("high")).values(
        "peak_price"
    )
    peak_price = result[0]["peak_price"] if result else None
    return {
        "peak_price": peak_price,
        "start_date": start_date,
        "fallback_to_all": fallback_to_all,
        "message": f"该标的不足{time_range[:-1]}年，已自动按成立以来计算" if fallback_to_all else "",
    }


async def calculate_retract(code: str, time_range: str, current_price: float | None = None) -> dict:
    peak_info = await calculate_peak(code, time_range)
    peak_price = peak_info["peak_price"]
    if peak_price is None or peak_price <= 0:
        return {**peak_info, "current_price": current_price, "retract": None}

    if current_price is None:
        quote = await fetch_realtime_quote(code)
        current_price = quote.current_price

    retract = (peak_price - current_price) / peak_price
    return {**peak_info, "current_price": current_price, "retract": retract}


async def serialize_monitor_snapshot(monitor: ETFMonitor) -> dict:
    quote: RealtimeQuote | None = None
    try:
        quote = await fetch_realtime_quote(monitor.code)
        current_price = quote.current_price
    except Exception:
        latest = await ETFHistory.filter(code=normalize_code(monitor.code)).order_by("-date").first()
        current_price = latest.close if latest else None

    retract_info = await calculate_retract(monitor.code, monitor.time_range, current_price) if current_price else {}
    return {
        "id": monitor.id,
        "code": normalize_code(monitor.code),
        "name": monitor.name or (quote.name if quote else ""),
        "is_active": monitor.is_active,
        "time_range": monitor.time_range,
        "x_drop": monitor.x_drop,
        "y_step": monitor.y_step,
        "current_stage": monitor.current_stage,
        "created_at": monitor.created_at.isoformat() if monitor.created_at else None,
        "updated_at": monitor.updated_at.isoformat() if monitor.updated_at else None,
        "last_checked_at": monitor.last_checked_at.isoformat() if monitor.last_checked_at else None,
        "last_alert_at": monitor.last_alert_at.isoformat() if monitor.last_alert_at else None,
        "quote": asdict(quote) if quote else None,
        "current_price": retract_info.get("current_price", current_price),
        "change_percent": quote.change_percent if quote else None,
        "peak_price": retract_info.get("peak_price"),
        "current_retract": retract_info.get("retract"),
        "range_notice": retract_info.get("message"),
        **retract_info,
    }


async def serialize_monitor_list_item(monitor: ETFMonitor) -> dict:
    latest_bars = await ETFHistory.filter(code=normalize_code(monitor.code)).order_by("-date").limit(2)
    latest = latest_bars[0] if latest_bars else None
    previous = latest_bars[1] if len(latest_bars) > 1 else None
    current_price = latest.close if latest else None
    change_percent = None
    if latest and previous and previous.close:
        change_percent = (latest.close - previous.close) / previous.close
    retract_info = await calculate_retract(monitor.code, monitor.time_range, current_price) if current_price else {}
    return {
        "id": monitor.id,
        "code": normalize_code(monitor.code),
        "name": monitor.name,
        "is_active": monitor.is_active,
        "time_range": monitor.time_range,
        "x_drop": monitor.x_drop,
        "y_step": monitor.y_step,
        "current_stage": monitor.current_stage,
        "created_at": monitor.created_at.isoformat() if monitor.created_at else None,
        "updated_at": monitor.updated_at.isoformat() if monitor.updated_at else None,
        "last_checked_at": monitor.last_checked_at.isoformat() if monitor.last_checked_at else None,
        "last_alert_at": monitor.last_alert_at.isoformat() if monitor.last_alert_at else None,
        "current_price": current_price,
        "change_percent": change_percent,
        "peak_price": retract_info.get("peak_price"),
        "current_retract": retract_info.get("retract"),
        "range_notice": retract_info.get("message"),
    }


async def list_monitor_snapshots(active_only: bool = False) -> list[dict]:
    query = ETFMonitor.all()
    if active_only:
        query = query.filter(Q(is_active=True))
    monitors = await query.order_by("code")
    return [await serialize_monitor_list_item(monitor) for monitor in monitors]


async def get_monitor_or_none(code: str) -> ETFMonitor | None:
    return await ETFMonitor.filter(code=normalize_code(code)).first()


async def get_detail(code: str) -> dict:
    monitor = await get_monitor_or_none(code)
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


async def list_monitors() -> list[dict]:
    return await list_monitor_snapshots()


async def ensure_seed_history(monitor: ETFMonitor) -> dict | None:
    try:
        return await ensure_monitor_history(monitor)
    except Exception as exc:
        return {
            "code": normalize_code(monitor.code),
            "requested_start": "",
            "requested_end": today_local().isoformat(),
            "fetched": 0,
            "inserted": 0,
            "skipped": False,
            "error": str(exc),
            "message": "seed history failed",
        }


async def monitors_for_runtime(code: str | None = None) -> list[ETFMonitor]:
    query = ETFMonitor.filter(is_active=True).order_by("code")
    if code:
        query = query.filter(code=normalize_code(code))
    return await query


async def get_peak_info(code: str, time_range: str) -> dict:
    peak = await calculate_peak(code, time_range)
    return {"peak": peak["peak_price"], **peak}


def is_market_check_time(moment: datetime | None = None) -> bool:
    current = moment or datetime.now()
    if current.weekday() >= 5:
        return False
    current_time = current.time()
    return time(9, 35) <= current_time <= time(11, 30) or time(13, 0) <= current_time <= time(15, 1)
