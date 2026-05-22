from __future__ import annotations

from typing import TYPE_CHECKING

from tortoise import fields
from tortoise.models import Model

from app.modules.role.models import TimestampMixin

if TYPE_CHECKING:
    from app.modules.role.models import Role


class User(Model, TimestampMixin):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=32, unique=True, index=True)
    email = fields.CharField(max_length=255, unique=True, index=True)
    password = fields.CharField(max_length=255)
    is_active = fields.BooleanField(default=True)
    is_superuser = fields.BooleanField(default=False)
    last_login = fields.DatetimeField(null=True)
    roles: fields.ManyToManyRelation["Role"] = fields.ManyToManyField("models.Role", related_name="users")

    class Meta:
        table = "admin_user"
