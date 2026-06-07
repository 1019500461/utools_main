import argparse
import re
import time
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from uuid import uuid4

import httpx
from playwright.sync_api import Page, expect, sync_playwright


def install_mock_api(page: Page) -> None:
    roles = [
        {"id": 1, "name": "管理员", "desc": "系统管理员角色", "created_at": "2026-05-22T00:00:00"},
        {"id": 2, "name": "普通用户", "desc": "普通用户角色", "created_at": "2026-05-22T00:00:00"},
    ]
    users = [
        {
            "id": 1,
            "username": "admin",
            "email": "admin@example.com",
            "is_active": True,
            "is_superuser": True,
            "last_login": "2026-05-22T00:00:00",
            "roles": [roles[0]],
        }
    ]
    next_role_id = {"value": 3}
    next_user_id = {"value": 2}
    menus = [
        {"id": 1, "name": "用户管理", "path": "/system/user", "component": "/system/user", "parent_id": 0, "order": 1},
        {"id": 2, "name": "角色管理", "path": "/system/role", "component": "/system/role", "parent_id": 0, "order": 2},
        {"id": 3, "name": "基金/ETF 监控", "path": "/fund/etf", "component": "/fund/etf", "parent_id": 0, "order": 3},
        {"id": 4, "name": "个人中心", "path": "/account/profile", "component": "/account/profile", "parent_id": 0, "order": 4},
    ]
    apis = [
        {"id": 1, "path": "/api/v1/base/userinfo", "method": "GET", "summary": "查看用户信息", "tags": "基础模块", "unique_id": "get/api/v1/base/userinfo"},
        {"id": 2, "path": "/api/v1/user/list", "method": "GET", "summary": "查看用户列表", "tags": "用户模块", "unique_id": "get/api/v1/user/list"},
        {"id": 3, "path": "/api/v1/user/create", "method": "POST", "summary": "创建用户", "tags": "用户模块", "unique_id": "post/api/v1/user/create"},
        {"id": 4, "path": "/api/v1/role/list", "method": "GET", "summary": "查看角色列表", "tags": "角色模块", "unique_id": "get/api/v1/role/list"},
        {"id": 5, "path": "/api/v1/role/create", "method": "POST", "summary": "创建角色", "tags": "角色模块", "unique_id": "post/api/v1/role/create"},
        {"id": 6, "path": "/api/v1/role/authorized", "method": "POST", "summary": "更新角色权限", "tags": "角色模块", "unique_id": "post/api/v1/role/authorized"},
    ]
    authorized = {1: {"menu_ids": [1, 2, 3, 4], "api_ids": [1, 2, 3, 4, 5, 6]}, 2: {"menu_ids": [1, 2], "api_ids": [1, 2, 4]}}

    def ok(data=None, **extra):
        payload = {"code": 200, "msg": "OK", "data": data}
        payload.update(extra)
        return payload

    def role_by_ids(role_ids):
        return [role for role in roles if role["id"] in role_ids]

    def respond(route):
        request = route.request
        parsed = urlparse(request.url)
        parsed_path = "/" + parsed.path.split("/api/v1/", 1)[1]
        query = {key: [unquote(value) for value in values] for key, values in parse_qs(parsed.query).items()}
        body = request.post_data_json if request.post_data else {}
        method = request.method

        if parsed_path == "/base/access_token" and method == "POST":
            return route.fulfill(json=ok({"access_token": "mock-token", "username": body.get("username", "admin")}))
        if parsed_path == "/base/userinfo":
            return route.fulfill(json=ok(users[0]))
        if parsed_path == "/base/profile" and method == "POST":
            users[0].update({"username": body["username"], "email": body["email"]})
            return route.fulfill(json=ok(users[0]))
        if parsed_path == "/base/update_password" and method == "POST":
            if body.get("old_password") != "123456":
                return route.fulfill(status=400, json={"detail": "旧密码验证错误"})
            return route.fulfill(json=ok(None, msg="密码修改成功"))
        if parsed_path == "/base/profile/test-email" and method == "POST":
            return route.fulfill(json=ok({"recipient": users[0]["email"], "subject": "测试邮件"}))
        if parsed_path == "/user/list":
            username = query.get("username", [""])[0]
            email = query.get("email", [""])[0]
            filtered = [user for user in users if username in user["username"] and email in user["email"]]
            return route.fulfill(json=ok(filtered, total=len(filtered), page=1, page_size=10))
        if parsed_path == "/user/create" and method == "POST":
            user = {
                "id": next_user_id["value"],
                "username": body["username"],
                "email": body["email"],
                "is_active": body.get("is_active", True),
                "is_superuser": body.get("is_superuser", False),
                "last_login": None,
                "roles": role_by_ids(body.get("role_ids", [])),
            }
            next_user_id["value"] += 1
            users.append(user)
            return route.fulfill(json=ok(user))
        if parsed_path == "/user/update" and method == "POST":
            user = next(item for item in users if item["id"] == body["id"])
            user.update(
                {
                    "username": body["username"],
                    "email": body["email"],
                    "is_active": body.get("is_active", True),
                    "is_superuser": body.get("is_superuser", False),
                    "roles": role_by_ids(body.get("role_ids", [])),
                }
            )
            return route.fulfill(json=ok(user))
        if parsed_path == "/user/delete" and method == "DELETE":
            user_id = int(query["user_id"][0])
            users[:] = [user for user in users if user["id"] != user_id]
            return route.fulfill(json=ok(None))
        if parsed_path == "/user/reset_password" and method == "POST":
            return route.fulfill(json=ok(None, msg="密码已重置为 123456"))
        if parsed_path == "/role/list":
            role_name = query.get("role_name", [""])[0]
            filtered = [role for role in roles if role_name in role["name"]]
            return route.fulfill(json=ok(filtered, total=len(filtered), page=1, page_size=10))
        if parsed_path == "/role/create" and method == "POST":
            role = {"id": next_role_id["value"], "name": body["name"], "desc": body.get("desc", ""), "created_at": "2026-05-22T00:00:00"}
            next_role_id["value"] += 1
            roles.append(role)
            authorized[role["id"]] = {"menu_ids": [], "api_ids": []}
            return route.fulfill(json=ok(role))
        if parsed_path == "/role/update" and method == "POST":
            role = next(item for item in roles if item["id"] == body["id"])
            role.update({"name": body["name"], "desc": body.get("desc", "")})
            return route.fulfill(json=ok(role))
        if parsed_path == "/role/delete" and method == "DELETE":
            role_id = int(query["role_id"][0])
            roles[:] = [role for role in roles if role["id"] != role_id]
            authorized.pop(role_id, None)
            return route.fulfill(json=ok(None))
        if parsed_path == "/menu/list":
            return route.fulfill(json=ok(menus, total=len(menus), page=1, page_size=len(menus)))
        if parsed_path == "/api/list":
            return route.fulfill(json=ok(apis, total=len(apis), page=1, page_size=len(apis)))
        if parsed_path == "/role/authorized" and method == "GET":
            role_id = int(query["id"][0])
            state = authorized.get(role_id, {"menu_ids": [], "api_ids": []})
            role = next(item for item in roles if item["id"] == role_id)
            data = {
                **role,
                "menus": [item for item in menus if item["id"] in state["menu_ids"]],
                "apis": [item for item in apis if item["id"] in state["api_ids"]],
            }
            return route.fulfill(json=ok(data))
        if parsed_path == "/role/authorized" and method == "POST":
            api_ids = [item["id"] for item in apis if any(info["path"] == item["path"] and info["method"] == item["method"] for info in body.get("api_infos", []))]
            authorized[body["id"]] = {"menu_ids": body.get("menu_ids", []), "api_ids": api_ids}
            return route.fulfill(json=ok(None))

        return route.fulfill(status=404, json={"detail": f"Unhandled mock route: {method} {parsed_path}"})

    page.route("**/api/v1/**", respond)


def wait_for_url(url: str, timeout: int) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            response = httpx.get(url, timeout=3, trust_env=False)
            if response.status_code < 500:
                return
        except httpx.HTTPError:
            time.sleep(1)
    raise TimeoutError(f"Target is not ready: {url}")


def screenshot(page: Page, directory: Path | None, name: str) -> None:
    if not directory:
        return
    directory.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=directory / f"{name}.png", full_page=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Playwright E2E test for admin login, users, profile and roles.")
    parser.add_argument("--base-url", default="http://127.0.0.1:5173")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="123456")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--screenshot-dir", default="")
    parser.add_argument("--mock-api", action="store_true", help="Mock backend API responses in the browser.")
    args = parser.parse_args()

    wait_for_url(args.base_url, args.timeout)
    screenshot_dir = Path(args.screenshot_dir) if args.screenshot_dir else None
    role_name = f"测试角色-{uuid4().hex[:8]}"
    user_name = f"tester-{uuid4().hex[:8]}"

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        if args.mock_api:
            install_mock_api(page)

        page.goto(f"{args.base_url}/system/user", wait_until="networkidle")
        expect(page).to_have_url(re.compile(r"/login"))
        screenshot(page, screenshot_dir, "01-login")

        page.get_by_placeholder("admin").fill(args.username)
        page.get_by_placeholder("123456").fill(args.password)
        page.get_by_role("button", name="登录").click()
        expect(page).to_have_url(re.compile(r"/system/user"), timeout=15000)
        expect(page.get_by_role("heading", name="用户列表")).to_be_visible(timeout=15000)
        screenshot(page, screenshot_dir, "02-user-list")

        page.get_by_role("button", name="新建用户").click()
        dialog = page.get_by_role("dialog")
        dialog.get_by_placeholder("请输入用户名称").fill(user_name)
        dialog.get_by_placeholder("请输入邮箱").fill(f"{user_name}@example.com")
        dialog.get_by_role("button", name="保存").click()
        expect(dialog).to_be_hidden(timeout=15000)
        table = page.locator(".n-data-table")
        expect(table.get_by_role("cell", name=user_name, exact=True)).to_be_visible(timeout=15000)

        page.locator("section.page-card").get_by_placeholder("请输入用户名称").fill(user_name)
        page.get_by_role("button", name="搜索").click()
        table = page.locator(".n-data-table")
        expect(table.get_by_role("cell", name=user_name, exact=True)).to_be_visible(timeout=15000)

        table.get_by_role("button", name="编辑").click()
        dialog = page.get_by_role("dialog")
        dialog.get_by_placeholder("请输入邮箱").fill(f"{user_name}-updated@example.com")
        dialog.get_by_role("button", name="保存").click()
        expect(dialog).to_be_hidden(timeout=15000)
        expect(page.get_by_text(f"{user_name}-updated@example.com")).to_be_visible(timeout=15000)

        table.get_by_role("button", name="重置密码").click()
        page.get_by_role("button", name="确定").click()
        expect(page.get_by_text("密码已重置为 123456")).to_be_visible(timeout=15000)

        page.get_by_text("个人中心").click()
        expect(page.get_by_role("heading", name="个人中心")).to_be_visible(timeout=15000)
        profile_email = page.locator("section.page-card").get_by_placeholder("请输入邮箱")
        original_email = profile_email.input_value()
        temporary_email = f"admin-e2e-{uuid4().hex[:8]}@example.com"
        profile_email.fill(temporary_email)
        page.locator("section.page-card").get_by_role("button", name="修改").first.click()
        expect(page.get_by_text("修改成功")).to_be_visible(timeout=15000)
        profile_email.fill(original_email)
        page.locator("section.page-card").get_by_role("button", name="修改").first.click()
        expect(page.get_by_text("修改成功")).to_be_visible(timeout=15000)
        screenshot(page, screenshot_dir, "03-profile")

        page.get_by_text("角色管理").click()
        expect(page.get_by_role("heading", name="角色列表")).to_be_visible(timeout=15000)
        page.get_by_role("button", name="新建角色").click()
        dialog = page.get_by_role("dialog")
        dialog.get_by_placeholder("请输入角色名称").fill(role_name)
        dialog.get_by_placeholder("请输入角色描述").fill("playwright smoke")
        dialog.get_by_role("button", name="保存").click()
        expect(dialog).to_be_hidden(timeout=15000)
        expect(page.get_by_text(role_name)).to_be_visible(timeout=15000)

        page.get_by_placeholder("请输入角色名").fill(role_name)
        page.get_by_role("button", name="搜索").click()
        expect(page.get_by_text(role_name)).to_be_visible(timeout=15000)

        table = page.locator(".n-data-table")
        table.get_by_role("button", name="编辑").click()
        dialog = page.get_by_role("dialog")
        dialog.get_by_placeholder("请输入角色描述").fill("playwright smoke updated")
        dialog.get_by_role("button", name="保存").click()
        expect(dialog).to_be_hidden(timeout=15000)
        expect(page.get_by_text("playwright smoke updated")).to_be_visible(timeout=15000)

        table.get_by_role("button", name="设置权限").click()
        expect(page.get_by_text("菜单权限", exact=True)).to_be_visible(timeout=15000)
        expect(page.get_by_text("接口权限", exact=True)).to_be_visible()
        screenshot(page, screenshot_dir, "04-authorized-drawer")
        page.get_by_role("button", name="确定").click()
        expect(page.get_by_text("权限保存成功")).to_be_visible(timeout=15000)

        page.get_by_role("button", name="删除").first.click()
        page.get_by_role("button", name="确定").click()
        expect(page.get_by_text("No Data")).to_be_visible(timeout=15000)

        page.get_by_role("button", name="admin").click()
        page.get_by_text("退出登录").click()
        expect(page).to_have_url(re.compile(r"/login"))

        browser.close()

    print("playwright e2e ok")


if __name__ == "__main__":
    main()
