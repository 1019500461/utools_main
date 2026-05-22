from __future__ import annotations

from tortoise import fields
from tortoise.models import Model


class TimestampMixin:
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)


class Role(Model, TimestampMixin):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=32, unique=True, index=True)
    desc = fields.CharField(max_length=500, null=True)
    menus: fields.ManyToManyRelation["Menu"] = fields.ManyToManyField("models.Menu", related_name="roles")
    apis: fields.ManyToManyRelation["Api"] = fields.ManyToManyField("models.Api", related_name="roles")

    class Meta:
        table = "role"


class Menu(Model, TimestampMixin):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=50)
    path = fields.CharField(max_length=100, index=True)
    component = fields.CharField(max_length=100)
    icon = fields.CharField(max_length=100, null=True)
    parent_id = fields.IntField(default=0, index=True)
    order = fields.IntField(default=0)
    is_hidden = fields.BooleanField(default=False)

    class Meta:
        table = "menu"


class Api(Model, TimestampMixin):
    id = fields.IntField(pk=True)
    path = fields.CharField(max_length=120, index=True)
    method = fields.CharField(max_length=10, index=True)
    summary = fields.CharField(max_length=120)
    tags = fields.CharField(max_length=50, index=True)

    class Meta:
        table = "api"
        unique_together = (("path", "method"),)
