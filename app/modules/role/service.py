from app.modules.role.models import Api, Menu, Role


async def serialize_role(role: Role) -> dict:
    return {
        "id": role.id,
        "name": role.name,
        "desc": role.desc or "",
        "created_at": role.created_at.isoformat() if role.created_at else None,
        "updated_at": role.updated_at.isoformat() if role.updated_at else None,
    }


async def serialize_menu(menu: Menu) -> dict:
    return {
        "id": menu.id,
        "name": menu.name,
        "path": menu.path,
        "component": menu.component,
        "icon": menu.icon,
        "parent_id": menu.parent_id,
        "order": menu.order,
        "is_hidden": menu.is_hidden,
    }


async def serialize_api(api: Api) -> dict:
    return {
        "id": api.id,
        "path": api.path,
        "method": api.method,
        "summary": api.summary,
        "tags": api.tags,
        "unique_id": f"{api.method.lower()}{api.path}",
    }
