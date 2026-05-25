from __future__ import annotations

from tortoise import fields
from tortoise.models import Model

from app.modules.role.models import TimestampMixin


class ETFHistory(Model):
    id = fields.IntField(pk=True)
    code = fields.CharField(max_length=20, index=True)
    date = fields.CharField(max_length=10, index=True)
    open = fields.FloatField()
    close = fields.FloatField()
    high = fields.FloatField()
    low = fields.FloatField()

    class Meta:
        table = "etf_history"
        unique_together = (("code", "date"),)


class ETFMonitor(Model, TimestampMixin):
    id = fields.IntField(pk=True)
    code = fields.CharField(max_length=20, unique=True, index=True)
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
