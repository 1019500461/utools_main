from fastapi import APIRouter, Depends, HTTPException, Query

from app.common.dependencies import get_current_user
from app.common.responses import success
from app.modules.role.models import Api, Menu, Role
from app.modules.role.schemas import RoleAuthorizedUpdate, RoleCreate, RoleUpdate
from app.modules.role.service import serialize_api, serialize_menu, serialize_role
from app.modules.user.models import User

router = APIRouter(prefix="/api/v1", tags=["role"])


@router.get("/role/list")
async def list_role(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    role_name: str = "",
    _: User = Depends(get_current_user),
):
    query = Role.all()
    if role_name:
        query = query.filter(name__icontains=role_name)
    total = await query.count()
    roles = await query.order_by("id").offset((page - 1) * page_size).limit(page_size)
    return success([await serialize_role(role) for role in roles], total=total, page=page, page_size=page_size)


@router.post("/role/create")
async def create_role(role_in: RoleCreate, _: User = Depends(get_current_user)):
    if await Role.filter(name=role_in.name).exists():
        raise HTTPException(status_code=400, detail="角色名称已存在")
    role = await Role.create(name=role_in.name, desc=role_in.desc)
    return success(await serialize_role(role), msg="Created Successfully")


@router.post("/role/update")
async def update_role(role_in: RoleUpdate, _: User = Depends(get_current_user)):
    role = await Role.filter(id=role_in.id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    exists = await Role.filter(name=role_in.name).exclude(id=role_in.id).exists()
    if exists:
        raise HTTPException(status_code=400, detail="角色名称已存在")
    role.name = role_in.name
    role.desc = role_in.desc
    await role.save(update_fields=["name", "desc", "updated_at"])
    return success(await serialize_role(role), msg="Updated Successfully")


@router.delete("/role/delete")
async def delete_role(role_id: int = Query(...), _: User = Depends(get_current_user)):
    role = await Role.filter(id=role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    if role.name == "管理员":
        raise HTTPException(status_code=400, detail="管理员角色不能删除")
    await role.delete()
    return success(msg="Deleted Successfully")


@router.get("/role/authorized")
async def get_role_authorized(id: int = Query(...), _: User = Depends(get_current_user)):
    role = await Role.filter(id=id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    menus = await role.menus.all()
    apis = await role.apis.all()
    return success(
        {
            **await serialize_role(role),
            "menus": [await serialize_menu(menu) for menu in menus],
            "apis": [await serialize_api(api) for api in apis],
        }
    )


@router.post("/role/authorized")
async def update_role_authorized(role_in: RoleAuthorizedUpdate, _: User = Depends(get_current_user)):
    role = await Role.filter(id=role_in.id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    menus = await Menu.filter(id__in=role_in.menu_ids)
    api_filters = [(item.get("method", "").upper(), item.get("path", "")) for item in role_in.api_infos]
    apis = []
    for method, path in api_filters:
        api = await Api.filter(method=method, path=path).first()
        if api:
            apis.append(api)

    await role.menus.clear()
    await role.apis.clear()
    if menus:
        await role.menus.add(*menus)
    if apis:
        await role.apis.add(*apis)
    return success(msg="Updated Successfully")


@router.get("/menu/list")
async def list_menu(_: User = Depends(get_current_user)):
    menus = await Menu.all().order_by("order", "id")
    return success([await serialize_menu(menu) for menu in menus], total=len(menus), page=1, page_size=len(menus))


@router.get("/api/list")
async def list_api(_: User = Depends(get_current_user)):
    apis = await Api.all().order_by("tags", "path", "method")
    return success([await serialize_api(api) for api in apis], total=len(apis), page=1, page_size=len(apis))
