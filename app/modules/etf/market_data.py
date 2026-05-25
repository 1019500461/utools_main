from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx


EASTMONEY_HISTORY_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
EASTMONEY_QUOTE_URL = "https://push2.eastmoney.com/api/qt/stock/get"
EASTMONEY_HISTORY_FALLBACK_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"
EASTMONEY_QUOTE_FALLBACK_URL = "http://push2.eastmoney.com/api/qt/stock/get"
TENCENT_HISTORY_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
TENCENT_HISTORY_FALLBACK_URL = "http://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
TENCENT_QUOTE_URL = "https://qt.gtimg.cn/q={symbol}"
TENCENT_QUOTE_FALLBACK_URL = "http://qt.gtimg.cn/q={symbol}"
REQUEST_TIMEOUT_SECONDS = 8.0
EASTMONEY_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Connection": "close",
    "Referer": "https://quote.eastmoney.com/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
}


class MarketDataError(RuntimeError):
    pass


@dataclass(slots=True)
class HistoryBar:
    code: str
    date: str
    open: float
    close: float
    high: float
    low: float


@dataclass(slots=True)
class RealtimeQuote:
    code: str
    name: str
    current_price: float
    open: float | None = None
    high: float | None = None
    low: float | None = None
    pre_close: float | None = None
    change_percent: float | None = None
    trade_date: str | None = None


def normalize_code(code: str) -> str:
    return code.strip().upper()


def infer_eastmoney_secid(code: str) -> str:
    normalized = normalize_code(code)
    digits = "".join(ch for ch in normalized if ch.isdigit())
    if len(digits) != 6:
        raise MarketDataError(f"无法识别标的代码: {code}")

    if digits.startswith(("5", "6", "9")):
        return f"1.{digits}"
    if digits.startswith(("0", "1", "2", "3")):
        return f"0.{digits}"
    raise MarketDataError(f"无法推断东方财富市场前缀: {code}")


def infer_tencent_symbol(code: str) -> str:
    normalized = normalize_code(code)
    digits = "".join(ch for ch in normalized if ch.isdigit())
    if len(digits) != 6:
        raise MarketDataError(f"无法识别标的代码: {code}")
    if digits.startswith(("5", "6", "9")):
        return f"sh{digits}"
    if digits.startswith(("0", "1", "2", "3")):
        return f"sz{digits}"
    raise MarketDataError(f"无法推断腾讯市场前缀: {code}")


def _format_yyyymmdd(value: date) -> str:
    return value.strftime("%Y%m%d")


def _safe_float(value: str) -> float:
    if value in {"", "-", "None", "null"}:
        raise ValueError("empty market value")
    return float(value)


def _eastmoney_scaled_number(data: dict[str, Any], field: str) -> float | None:
    value = data.get(field)
    if value in {None, "-", ""}:
        return None
    decimal_places = data.get("f59")
    if isinstance(decimal_places, int) and decimal_places >= 0:
        return float(value) / (10**decimal_places)
    return float(value) / 100


async def _fetch_eastmoney_json(urls: tuple[str, ...], params: dict[str, str]) -> dict[str, Any]:
    last_error: Exception | None = None
    for url in urls:
        for _ in range(2):
            try:
                async with httpx.AsyncClient(
                    timeout=REQUEST_TIMEOUT_SECONDS,
                    headers=EASTMONEY_HEADERS,
                    follow_redirects=True,
                    trust_env=False,
                ) as client:
                    response = await client.get(url, params=params)
                    response.raise_for_status()
                    return response.json()
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
    raise MarketDataError(f"东方财富接口请求失败: {last_error}") from last_error


async def _fetch_json(urls: tuple[str, ...], params: dict[str, str] | None = None) -> dict[str, Any]:
    last_error: Exception | None = None
    for url in urls:
        try:
            async with httpx.AsyncClient(
                timeout=REQUEST_TIMEOUT_SECONDS,
                headers=EASTMONEY_HEADERS,
                follow_redirects=True,
                trust_env=False,
            ) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            last_error = exc
    raise MarketDataError(f"备用行情接口请求失败: {last_error}") from last_error


async def fetch_tencent_qfq_history(code: str, start_date: date, end_date: date) -> list[HistoryBar]:
    normalized = normalize_code(code)
    symbol = infer_tencent_symbol(normalized)
    days = max((end_date - start_date).days + 10, 10)
    params = {"param": f"{symbol},day,,,{days},qfq"}
    payload = await _fetch_json((TENCENT_HISTORY_URL, TENCENT_HISTORY_FALLBACK_URL), params)
    data = ((payload.get("data") or {}).get(symbol) or {}).get("qfqday") or []
    bars: list[HistoryBar] = []
    for item in data:
        if len(item) < 5:
            continue
        item_date = date.fromisoformat(item[0])
        if item_date < start_date or item_date > end_date:
            continue
        bars.append(
            HistoryBar(
                code=normalized,
                date=item[0],
                open=float(item[1]),
                close=float(item[2]),
                high=float(item[3]),
                low=float(item[4]),
            )
        )
    return bars


async def fetch_tencent_realtime_quote(code: str) -> RealtimeQuote:
    normalized = normalize_code(code)
    symbol = infer_tencent_symbol(normalized)
    last_error: Exception | None = None
    for template in (TENCENT_QUOTE_URL, TENCENT_QUOTE_FALLBACK_URL):
        try:
            async with httpx.AsyncClient(
                timeout=REQUEST_TIMEOUT_SECONDS,
                headers=EASTMONEY_HEADERS,
                follow_redirects=True,
                trust_env=False,
            ) as client:
                response = await client.get(template.format(symbol=symbol))
                response.raise_for_status()
                text = response.text
            raw = text.split('="', 1)[1].rsplit('";', 1)[0]
            parts = raw.split("~")
            return RealtimeQuote(
                code=normalized,
                name=parts[1],
                current_price=float(parts[3]),
                open=float(parts[5]) if parts[5] else None,
                high=float(parts[33]) if len(parts) > 33 and parts[33] else None,
                low=float(parts[34]) if len(parts) > 34 and parts[34] else None,
                pre_close=float(parts[4]) if parts[4] else None,
                change_percent=float(parts[32]) / 100 if len(parts) > 32 and parts[32] else None,
                trade_date=parts[30] if len(parts) > 30 else None,
            )
        except (httpx.HTTPError, ValueError, IndexError) as exc:
            last_error = exc
    raise MarketDataError(f"腾讯实时行情接口请求失败: {last_error}") from last_error


async def fetch_qfq_history(code: str, start_date: date, end_date: date) -> list[HistoryBar]:
    normalized = normalize_code(code)
    params = {
        "secid": infer_eastmoney_secid(normalized),
        "klt": "101",
        "fqt": "1",
        "beg": _format_yyyymmdd(start_date),
        "end": _format_yyyymmdd(end_date),
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55",
    }

    try:
        return await fetch_tencent_qfq_history(normalized, start_date, end_date)
    except MarketDataError:
        payload = await _fetch_eastmoney_json((EASTMONEY_HISTORY_URL, EASTMONEY_HISTORY_FALLBACK_URL), params)
    data = payload.get("data")
    if not data:
        return []

    bars: list[HistoryBar] = []
    for item in data.get("klines") or []:
        parts = item.split(",")
        if len(parts) < 5:
            continue
        try:
            bars.append(
                HistoryBar(
                    code=normalized,
                    date=parts[0],
                    open=_safe_float(parts[1]),
                    close=_safe_float(parts[2]),
                    high=_safe_float(parts[3]),
                    low=_safe_float(parts[4]),
                )
            )
        except ValueError:
            continue
    return bars


async def fetch_realtime_quote(code: str) -> RealtimeQuote:
    normalized = normalize_code(code)
    params = {
        "secid": infer_eastmoney_secid(normalized),
        "fields": "f43,f44,f45,f46,f58,f59,f60,f170,f292",
    }

    try:
        return await fetch_tencent_realtime_quote(normalized)
    except MarketDataError:
        payload = await _fetch_eastmoney_json((EASTMONEY_QUOTE_URL, EASTMONEY_QUOTE_FALLBACK_URL), params)
    data = payload.get("data")
    if not data:
        raise MarketDataError(f"未获取到实时行情: {normalized}")

    current_price = _eastmoney_scaled_number(data, "f43")
    if current_price is None:
        raise MarketDataError(f"实时行情缺少最新价: {normalized}")

    change_percent_value = data.get("f170")
    change_percent = None if change_percent_value in {None, "-", ""} else float(change_percent_value) / 100
    return RealtimeQuote(
        code=normalized,
        name=str(data.get("f58") or ""),
        current_price=current_price,
        open=_eastmoney_scaled_number(data, "f46"),
        high=_eastmoney_scaled_number(data, "f44"),
        low=_eastmoney_scaled_number(data, "f45"),
        pre_close=_eastmoney_scaled_number(data, "f60"),
        change_percent=change_percent,
        trade_date=str(data.get("f292") or "") or None,
    )
