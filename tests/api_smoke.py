import argparse
import time
from uuid import uuid4

import httpx


def assert_ok(response: httpx.Response) -> dict:
    response.raise_for_status()
    payload = response.json()
    assert payload["code"] == 200, payload
    return payload


def wait_for_backend(api_url: str, timeout: int) -> None:
    deadline = time.time() + timeout
    health_url = api_url.replace("/api/v1", "/health")
    while time.time() < deadline:
        try:
            response = httpx.get(health_url, timeout=3, trust_env=False)
            if response.status_code == 200:
                return
        except httpx.HTTPError:
            time.sleep(1)
    raise TimeoutError(f"Backend is not ready: {health_url}")


def mock_etf_code() -> str:
    letters = "".join(chr(65 + (byte % 26)) for byte in uuid4().bytes[:8])
    return f"MOCK{letters}"


def run_admin_smoke(client: httpx.Client, headers: dict[str, str]) -> None:
    username = f"smoke-{uuid4().hex[:8]}"
    email = f"{username}@example.com"

    roles = assert_ok(client.get("/role/list", params={"page": 1, "page_size": 100}, headers=headers))["data"]
    role_ids = [roles[0]["id"]] if roles else []

    created_user = assert_ok(
        client.post(
            "/user/create",
            json={
                "username": username,
                "email": email,
                "password": "123456",
                "role_ids": role_ids,
                "is_active": True,
                "is_superuser": False,
            },
            headers=headers,
        )
    )["data"]
    user_id = created_user["id"]

    listed_users = assert_ok(
        client.get("/user/list", params={"page": 1, "page_size": 10, "username": username}, headers=headers)
    )["data"]
    assert any(item["id"] == user_id for item in listed_users), listed_users

    updated_email = f"{username}-updated@example.com"
    assert_ok(
        client.post(
            "/user/update",
            json={
                "id": user_id,
                "username": username,
                "email": updated_email,
                "role_ids": role_ids,
                "is_active": True,
                "is_superuser": False,
            },
            headers=headers,
        )
    )
    user_detail = assert_ok(client.get("/user/get", params={"user_id": user_id}, headers=headers))["data"]
    assert user_detail["email"] == updated_email, user_detail

    assert_ok(client.post("/user/reset_password", json={"user_id": user_id}, headers=headers))
    bad_password = client.post(
        "/base/update_password",
        json={"old_password": "wrong-password", "new_password": "654321", "confirm_password": "654321"},
        headers=headers,
    )
    assert bad_password.status_code == 400, bad_password.text

    assert_ok(client.delete("/user/delete", params={"user_id": user_id}, headers=headers))


def run_role_smoke(client: httpx.Client, headers: dict[str, str]) -> None:
    role_name = f"测试角色-{uuid4().hex[:8]}"
    created = assert_ok(client.post("/role/create", json={"name": role_name, "desc": "api smoke"}, headers=headers))
    role_id = created["data"]["id"]

    listed = assert_ok(client.get("/role/list", params={"page": 1, "page_size": 10, "role_name": role_name}, headers=headers))
    assert any(item["id"] == role_id for item in listed["data"]), listed

    assert_ok(client.post("/role/update", json={"id": role_id, "name": role_name, "desc": "api smoke updated"}, headers=headers))

    menus = assert_ok(client.get("/menu/list", headers=headers))["data"]
    apis = assert_ok(client.get("/api/list", headers=headers))["data"]
    api_infos = [{"path": item["path"], "method": item["method"]} for item in apis if item["method"] == "GET"]
    assert_ok(
        client.post(
            "/role/authorized",
            json={"id": role_id, "menu_ids": [item["id"] for item in menus], "api_infos": api_infos},
            headers=headers,
        )
    )
    authorized = assert_ok(client.get("/role/authorized", params={"id": role_id}, headers=headers))["data"]
    assert authorized["menus"], authorized

    assert_ok(client.delete("/role/delete", params={"role_id": role_id}, headers=headers))


def run_etf_smoke(client: httpx.Client, headers: dict[str, str]) -> None:
    code = mock_etf_code()
    created = assert_ok(
        client.post(
            "/etf/create",
            json={
                "code": code,
                "name": "ETF smoke",
                "time_range": "3y",
                "x_drop": 0.15,
                "y_step": 0.05,
                "holding_cost": 1.0,
                "holding_shares": 1000,
                "take_profit_enabled": True,
                "take_profit_first_rise": 0.15,
                "take_profit_step": 0.05,
                "is_active": True,
            },
            headers=headers,
        )
    )
    assert created["data"]["monitor"]["code"] == code, created
    assert created["data"]["monitor"]["holding_cost"] == 1.0, created
    assert created["data"]["monitor"]["holding_shares"] == 1000, created
    assert created["data"]["monitor"]["take_profit_enabled"] is True, created
    assert created["data"]["sync"] is None or "error" in created["data"]["sync"], created

    listed = assert_ok(client.get("/etf/list", headers=headers))
    assert any(item["code"] == code for item in listed["data"]), listed

    detail = assert_ok(client.get("/etf/detail", params={"code": code}, headers=headers))
    assert detail["data"]["code"] == code, detail
    assert "klines" in detail["data"], detail

    updated = assert_ok(
        client.post(
            "/etf/update",
            json={
                "code": code,
                "name": "ETF smoke updated",
                "time_range": "5y",
                "holding_cost": 1.2,
                "holding_shares": 1200,
                "take_profit_enabled": False,
                "is_active": True,
            },
            headers=headers,
        )
    )
    assert updated["data"]["name"] == "ETF smoke updated", updated
    assert updated["data"]["time_range"] == "5y", updated
    assert updated["data"]["holding_cost"] == 1.2, updated
    assert updated["data"]["holding_shares"] == 1200, updated
    assert updated["data"]["take_profit_enabled"] is False, updated

    synced = assert_ok(client.post("/etf/sync", json={"code": code}, headers=headers))
    assert synced["data"] and synced["data"][0]["code"] == code, synced
    assert "error" in synced["data"][0], synced

    monitored = assert_ok(client.post("/etf/monitor/run", json={"code": code}, headers=headers))
    assert monitored["data"] and monitored["data"][0]["code"] == code, monitored

    assert_ok(client.delete("/etf/delete", params={"code": code}, headers=headers))


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test login, admin and ETF APIs.")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="123456")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--skip-etf", action="store_true", help="Skip ETF API smoke checks.")
    args = parser.parse_args()

    wait_for_backend(args.api_url, args.timeout)

    with httpx.Client(base_url=args.api_url, timeout=10, trust_env=False) as client:
        login = assert_ok(client.post("/base/access_token", json={"username": args.username, "password": args.password}))
        token = login["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        assert_ok(client.get("/base/userinfo", headers=headers))
        assert_ok(client.get("/base/usermenu", headers=headers))
        assert_ok(client.get("/base/userapi", headers=headers))
        run_admin_smoke(client, headers)
        run_role_smoke(client, headers)

        if not args.skip_etf:
            run_etf_smoke(client, headers)

    print("api smoke ok")


if __name__ == "__main__":
    main()
