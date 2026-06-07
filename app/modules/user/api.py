from datetime import datetime
from email.utils import parseaddr

from fastapi import APIRouter, Depends, HTTPException
from tortoise.exceptions import IntegrityError

from app.common.dependencies import get_current_user
from app.common.responses import success
from app.core.security import create_access_token, hash_password, verify_password
from app.modules.etf.notification import send_test_notification_email
from app.modules.role.models import Api, Menu
from app.modules.role.service import serialize_menu, serialize_role
from app.modules.user.models import User
from app.modules.user.schemas import CredentialsSchema, PasswordUpdateSchema, ProfileUpdateSchema, TokenOut

router = APIRouter(prefix="/api/v1/base", tags=["base"])


def validate_email(email: str) -> str:
    value = email.strip()
    parsed_name, parsed_email = parseaddr(value)
    if parsed_name or parsed_email.lower() != value.lower() or "@" not in parsed_email:
        raise HTTPException(status_code=400, detail="邮箱格式不正确")
    return value


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
            "avatar": "",
            "is_active": current_user.is_active,
            "is_superuser": current_user.is_superuser,
            "roles": [await serialize_role(role) for role in roles],
        }
    )


@router.post("/profile")
async def update_profile(payload: ProfileUpdateSchema, current_user: User = Depends(get_current_user)):
    username = payload.username.strip()
    email = validate_email(payload.email)
    current_user.username = username
    current_user.email = email
    try:
        await current_user.save(update_fields=["username", "email", "updated_at"])
    except IntegrityError as exc:
        raise HTTPException(status_code=400, detail="用户名或邮箱已存在") from exc

    return success(
        {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "is_active": current_user.is_active,
            "is_superuser": current_user.is_superuser,
        }
    )


@router.post("/update_password")
async def update_password(payload: PasswordUpdateSchema, current_user: User = Depends(get_current_user)):
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="两次输入的新密码不一致")
    if not verify_password(payload.old_password, current_user.password):
        raise HTTPException(status_code=400, detail="旧密码验证错误")

    current_user.password = hash_password(payload.new_password)
    await current_user.save(update_fields=["password", "updated_at"])
    return success(msg="密码修改成功")


@router.post("/profile/test-email")
async def send_profile_test_email(current_user: User = Depends(get_current_user)):
    try:
        result = await send_test_notification_email(current_user)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="邮件发送失败") from exc

    return success({"recipient": result.recipient, "subject": result.subject})


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
