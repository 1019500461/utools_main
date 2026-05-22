from datetime import datetime

from pydantic import BaseModel, Field


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=32)
    desc: str = ""


class RoleUpdate(RoleCreate):
    id: int


class RoleAuthorizedUpdate(BaseModel):
    id: int
    menu_ids: list[int] = []
    api_infos: list[dict] = []


class RoleOut(BaseModel):
    id: int
    name: str
    desc: str | None = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
