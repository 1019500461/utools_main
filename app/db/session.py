from tortoise import Tortoise

from app.core.config import settings
from app.core.security import hash_password
from app.modules.etf.schema_maintenance import ensure_etf_schema
from app.modules.role.models import Api, Menu, Role
from app.modules.user.models import User

MENU_DEFINITIONS = [
    {
        "name": "用户管理",
        "path": "/system/user",
        "component": "/system/user",
        "icon": "user",
        "parent_id": 0,
        "order": 1,
    },
    {
        "name": "角色管理",
        "path": "/system/role",
        "component": "/system/role",
        "icon": "users",
        "parent_id": 0,
        "order": 2,
    },
    {
        "name": "基金/ETF 监控",
        "path": "/fund/etf",
        "component": "/fund/etf",
        "icon": "chart",
        "parent_id": 0,
        "order": 3,
    },
    {
        "name": "个人中心",
        "path": "/account/profile",
        "component": "/account/profile",
        "icon": "profile",
        "parent_id": 0,
        "order": 4,
    },
]

API_DEFINITIONS = [
    ("POST", "/api/v1/base/access_token", "获取 token", "基础模块"),
    ("GET", "/api/v1/base/userinfo", "查看用户信息", "基础模块"),
    ("GET", "/api/v1/base/usermenu", "查看用户菜单", "基础模块"),
    ("GET", "/api/v1/base/userapi", "查看用户 API", "基础模块"),
    ("POST", "/api/v1/base/profile", "更新个人资料", "基础模块"),
    ("POST", "/api/v1/base/update_password", "修改用户密码", "基础模块"),
    ("GET", "/api/v1/user/list", "查看用户列表", "用户模块"),
    ("GET", "/api/v1/user/get", "查看用户", "用户模块"),
    ("POST", "/api/v1/user/create", "创建用户", "用户模块"),
    ("POST", "/api/v1/user/update", "更新用户", "用户模块"),
    ("DELETE", "/api/v1/user/delete", "删除用户", "用户模块"),
    ("POST", "/api/v1/user/reset_password", "重置用户密码", "用户模块"),
    ("GET", "/api/v1/role/list", "查看角色列表", "角色模块"),
    ("POST", "/api/v1/role/create", "创建角色", "角色模块"),
    ("POST", "/api/v1/role/update", "更新角色", "角色模块"),
    ("DELETE", "/api/v1/role/delete", "删除角色", "角色模块"),
    ("GET", "/api/v1/role/authorized", "查看角色权限", "角色模块"),
    ("POST", "/api/v1/role/authorized", "更新角色权限", "角色模块"),
    ("GET", "/api/v1/menu/list", "查看菜单列表", "菜单模块"),
    ("GET", "/api/v1/api/list", "查看接口列表", "接口模块"),
    ("GET", "/api/v1/etf/list", "查看 ETF 列表", "ETF 模块"),
    ("POST", "/api/v1/etf/create", "创建 ETF 监控", "ETF 模块"),
    ("POST", "/api/v1/etf/update", "更新 ETF 监控", "ETF 模块"),
    ("DELETE", "/api/v1/etf/delete", "删除 ETF 监控", "ETF 模块"),
    ("GET", "/api/v1/etf/detail", "查看 ETF 详情", "ETF 模块"),
    ("POST", "/api/v1/etf/sync", "同步 ETF 数据", "ETF 模块"),
    ("POST", "/api/v1/etf/monitor/run", "运行 ETF 监控", "ETF 模块"),
]


async def init_database() -> None:
    await Tortoise.init(config=settings.tortoise_orm)
    connection = Tortoise.get_connection("default")
    should_prepare_existing_etf_schema = False
    if connection.capabilities.dialect == "postgres":
        existing_table = await connection.execute_query_dict(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = current_schema()
                  AND table_name = 'etf_monitor'
            ) AS exists;
            """
        )
        should_prepare_existing_etf_schema = bool(existing_table[0]["exists"])

    if should_prepare_existing_etf_schema:
        await ensure_etf_schema()

    await Tortoise.generate_schemas(safe=True)

    if not should_prepare_existing_etf_schema:
        await ensure_etf_schema()

    await init_seed_data()


async def close_database() -> None:
    await Tortoise.close_connections()


async def upsert_menu(definition: dict) -> Menu:
    menu, _ = await Menu.get_or_create(path=definition["path"], defaults=definition)
    changed = False
    for field, value in definition.items():
        if getattr(menu, field) != value:
            setattr(menu, field, value)
            changed = True
    if changed:
        await menu.save(update_fields=["name", "component", "icon", "parent_id", "order", "updated_at"])
    return menu


async def upsert_api(method: str, path: str, summary: str, tags: str) -> Api:
    api, _ = await Api.get_or_create(method=method, path=path, defaults={"summary": summary, "tags": tags})
    if api.summary != summary or api.tags != tags:
        api.summary = summary
        api.tags = tags
        await api.save(update_fields=["summary", "tags", "updated_at"])
    return api


async def upsert_role(name: str, desc: str) -> Role:
    role, _ = await Role.get_or_create(name=name, defaults={"desc": desc})
    if role.desc != desc:
        role.desc = desc
        await role.save(update_fields=["desc", "updated_at"])
    return role


async def init_seed_data() -> None:
    menus = [await upsert_menu(definition) for definition in MENU_DEFINITIONS]
    apis = [await upsert_api(method, path, summary, tags) for method, path, summary, tags in API_DEFINITIONS]

    # Repair old mojibake seed rows from earlier builds without risking unique-key conflicts.
    if not await Role.filter(name="管理员").exists():
        await Role.filter(name__contains="\u7ee0").update(name="管理员", desc="系统管理员角色")
    if not await Role.filter(name="普通用户").exists():
        await Role.filter(name__contains="\u93c5").update(name="普通用户", desc="普通用户角色")

    admin_role = await upsert_role("管理员", "系统管理员角色")
    user_role = await upsert_role("普通用户", "普通用户角色")
    await admin_role.menus.add(*menus)
    await admin_role.apis.add(*apis)
    await user_role.menus.add(*menus)
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
