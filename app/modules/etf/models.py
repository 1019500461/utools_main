from __future__ import annotations

from typing import TYPE_CHECKING

from tortoise import fields
from tortoise.models import Model

from app.modules.role.models import TimestampMixin

if TYPE_CHECKING:
    from app.modules.user.models import User


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
    holding_cost = fields.FloatField(null=True)
    holding_shares = fields.FloatField(default=0)
    take_profit_enabled = fields.BooleanField(default=False, index=True)
    take_profit_first_rise = fields.FloatField(default=0.15)
    take_profit_step = fields.FloatField(default=0.05)
    take_profit_stage = fields.IntField(default=0)
    take_profit_last_alert_at = fields.DatetimeField(null=True)
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
