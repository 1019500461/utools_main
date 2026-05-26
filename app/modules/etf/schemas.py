from __future__ import annotations

from pydantic import BaseModel, Field


class ETFHistoryBar(BaseModel):
    code: str
    date: str
    open: float
    close: float
    high: float
    low: float


class ETFQuote(BaseModel):
    code: str
    name: str = ""
    current_price: float
    open: float | None = None
    high: float | None = None
    low: float | None = None
    pre_close: float | None = None
    change_percent: float | None = None
    trade_date: str | None = None


class ETFMonitorCreate(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(default="", max_length=100)
    time_range: str = Field(default="3y", pattern="^(3y|5y|all)$")
    x_drop: float = Field(default=0.15, ge=0, le=1)
    y_step: float = Field(default=0.05, ge=0, le=1)
    holding_cost: float | None = Field(default=None, ge=0)
    holding_shares: float = Field(default=0, ge=0)
    take_profit_enabled: bool = False
    take_profit_first_rise: float = Field(default=0.15, ge=0, le=10)
    take_profit_step: float = Field(default=0.05, ge=0, le=10)
    is_active: bool = True


class ETFMonitorUpdate(BaseModel):
    id: int | None = None
    code: str = Field(min_length=1, max_length=20)
    name: str | None = Field(default=None, max_length=100)
    time_range: str | None = Field(default=None, pattern="^(3y|5y|all)$")
    x_drop: float | None = Field(default=None, ge=0, le=1)
    y_step: float | None = Field(default=None, ge=0, le=1)
    holding_cost: float | None = Field(default=None, ge=0)
    holding_shares: float | None = Field(default=None, ge=0)
    take_profit_enabled: bool | None = None
    take_profit_first_rise: float | None = Field(default=None, ge=0, le=10)
    take_profit_step: float | None = Field(default=None, ge=0, le=10)
    is_active: bool | None = None


class ETFSyncIn(BaseModel):
    code: str | None = Field(default=None, max_length=20)


class ETFSyncResult(BaseModel):
    code: str
    requested_start: str
    requested_end: str
    fetched: int
    inserted: int
    skipped: bool = False
    message: str = ""
    error: str | None = None
