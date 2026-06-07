from fastapi import APIRouter, Depends, HTTPException, Query
from tortoise.exceptions import IntegrityError

from app.common.dependencies import get_current_user
from app.common.responses import success
from app.core.security import hash_password
from app.modules.role.models import Role
from app.modules.role.service import serialize_role
from app.modules.user.api import validate_email
from app.modules.user.models import User
from app.modules.user.schemas import ResetPasswordSchema, UserCreate, UserUpdate

router = APIRouter(prefix="/api/v1/user", tags=["user"])


async def serialize_user(user: User) -> dict:
    roles = await user.roles.all()
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        "roles": [await serialize_role(role) for role in roles],
    }


async def sync_user_roles(user: User, role_ids: list[int]) -> None:
    roles = await Role.filter(id__in=role_ids)
    await user.roles.clear()
    if roles:
        await user.roles.add(*roles)


@router.get("/list")
async def list_user(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    username: str = "",
    email: str = "",
    _: User = Depends(get_current_user),
):
    query = User.all()
    if username:
        query = query.filter(username__icontains=username)
    if email:
        query = query.filter(email__icontains=email)
    total = await query.count()
    users = await query.order_by("id").offset((page - 1) * page_size).limit(page_size)
    return success([await serialize_user(user) for user in users], total=total, page=page, page_size=page_size)


@router.get("/get")
async def get_user(user_id: int = Query(...), _: User = Depends(get_current_user)):
    user = await User.filter(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return success(await serialize_user(user))


@router.post("/create")
async def create_user(payload: UserCreate, _: User = Depends(get_current_user)):
    user = User(
        username=payload.username.strip(),
        email=validate_email(payload.email),
        password=hash_password(payload.password),
        is_active=payload.is_active,
        is_superuser=payload.is_superuser,
    )
    try:
        await user.save()
    except IntegrityError as exc:
        raise HTTPException(status_code=400, detail="用户名或邮箱已存在") from exc
    await sync_user_roles(user, payload.role_ids)
    return success(await serialize_user(user), msg="Created Successfully")


@router.post("/update")
async def update_user(payload: UserUpdate, current_user: User = Depends(get_current_user)):
    user = await User.filter(id=payload.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == current_user.id and not payload.is_active:
        raise HTTPException(status_code=400, detail="不能禁用当前登录用户")

    user.username = payload.username.strip()
    user.email = validate_email(payload.email)
    user.is_active = payload.is_active
    user.is_superuser = payload.is_superuser
    try:
        await user.save(update_fields=["username", "email", "is_active", "is_superuser", "updated_at"])
    except IntegrityError as exc:
        raise HTTPException(status_code=400, detail="用户名或邮箱已存在") from exc
    await sync_user_roles(user, payload.role_ids)
    return success(await serialize_user(user), msg="Updated Successfully")


@router.delete("/delete")
async def delete_user(user_id: int = Query(...), current_user: User = Depends(get_current_user)):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除当前登录用户")
    user = await User.filter(id=user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    await user.delete()
    return success(msg="Deleted Successfully")


@router.post("/reset_password")
async def reset_password(payload: ResetPasswordSchema, _: User = Depends(get_current_user)):
    user = await User.filter(id=payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.password = hash_password("123456")
    await user.save(update_fields=["password", "updated_at"])
    return success(msg="密码已重置为 123456")
