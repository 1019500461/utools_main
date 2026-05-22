from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from app.common.dependencies import get_current_user
from app.common.responses import success
from app.core.security import create_access_token, verify_password
from app.modules.role.models import Api, Menu
from app.modules.role.service import serialize_role, serialize_menu
from app.modules.user.models import User
from app.modules.user.schemas import CredentialsSchema, TokenOut

router = APIRouter(prefix="/api/v1/base", tags=["base"])


@router.post("/access_token")
async def login_access_token(credentials: CredentialsSchema):
    user = await User.filter(username=credentials.username, is_active=True).first()
    if not user or not verify_password(credentials.password, user.password):
        raise HTTPException(status_code=400, detail="用户名或密码错误")

    user.last_login = datetime.now()
    await user.save(update_fields=["last_login"])
    token = create_access_token(
        {
            "user_id": user.id,
            "username": user.username,
            "is_superuser": user.is_superuser,
        }
    )
    return success(TokenOut(access_token=token, username=user.username).model_dump())


@router.get("/userinfo")
async def get_userinfo(current_user: User = Depends(get_current_user)):
    roles = await current_user.roles.all()
    return success(
        {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "is_active": current_user.is_active,
            "is_superuser": current_user.is_superuser,
            "roles": [await serialize_role(role) for role in roles],
        }
    )


@router.get("/usermenu")
async def get_user_menu(current_user: User = Depends(get_current_user)):
    if current_user.is_superuser:
        menus = await Menu.all().order_by("order", "id")
    else:
        roles = await current_user.roles.all().prefetch_related("menus")
        menu_map = {}
        for role in roles:
            for menu in await role.menus.all():
                menu_map[menu.id] = menu
        menus = sorted(menu_map.values(), key=lambda item: (item.order, item.id))
    return success([await serialize_menu(menu) for menu in menus])


@router.get("/userapi")
async def get_user_api(current_user: User = Depends(get_current_user)):
    if current_user.is_superuser:
        apis = await Api.all()
    else:
        roles = await current_user.roles.all().prefetch_related("apis")
        api_map = {}
        for role in roles:
            for api in await role.apis.all():
                api_map[api.id] = api
        apis = list(api_map.values())
    return success([f"{api.method.lower()}{api.path}" for api in apis])
