from tortoise import Tortoise

from app.core.config import settings
from app.core.security import hash_password
from app.modules.role.models import Api, Menu, Role
from app.modules.user.models import User

ROLE_API_DEFINITIONS = [
    ("GET", "/api/v1/role/list", "查看角色列表", "角色模块"),
    ("POST", "/api/v1/role/create", "创建角色", "角色模块"),
    ("POST", "/api/v1/role/update", "更新角色", "角色模块"),
    ("DELETE", "/api/v1/role/delete", "删除角色", "角色模块"),
    ("GET", "/api/v1/role/authorized", "查看角色权限", "角色模块"),
    ("POST", "/api/v1/role/authorized", "更新角色权限", "角色模块"),
    ("GET", "/api/v1/menu/list", "查看菜单列表", "菜单模块"),
    ("GET", "/api/v1/api/list", "查看接口列表", "接口模块"),
]


async def init_database() -> None:
    await Tortoise.init(config=settings.tortoise_orm)
    await Tortoise.generate_schemas(safe=True)
    await init_seed_data()


async def close_database() -> None:
    await Tortoise.close_connections()


async def init_seed_data() -> None:
    menu, _ = await Menu.get_or_create(
        path="/system/role",
        defaults={
            "name": "角色管理",
            "component": "/system/role",
            "icon": "users",
            "parent_id": 0,
            "order": 1,
        },
    )

    apis: list[Api] = []
    for method, path, summary, tags in ROLE_API_DEFINITIONS:
        api, _ = await Api.get_or_create(
            method=method,
            path=path,
            defaults={"summary": summary, "tags": tags},
        )
        apis.append(api)

    admin_role, _ = await Role.get_or_create(name="管理员", defaults={"desc": "系统管理员角色"})
    user_role, _ = await Role.get_or_create(name="普通用户", defaults={"desc": "普通用户角色"})
    await admin_role.menus.add(menu)
    await admin_role.apis.add(*apis)
    await user_role.menus.add(menu)
    await user_role.apis.add(*[api for api in apis if api.method == "GET"])

    admin, created = await User.get_or_create(
        username="admin",
        defaults={
            "email": "admin@example.com",
            "password": hash_password("123456"),
            "is_active": True,
            "is_superuser": True,
        },
    )
    if created:
        await admin.roles.add(admin_role)
