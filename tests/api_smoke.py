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


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test login and role management APIs.")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="123456")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    wait_for_backend(args.api_url, args.timeout)

    with httpx.Client(base_url=args.api_url, timeout=10, trust_env=False) as client:
        login = assert_ok(client.post("/base/access_token", json={"username": args.username, "password": args.password}))
        token = login["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        assert_ok(client.get("/base/userinfo", headers=headers))
        assert_ok(client.get("/base/usermenu", headers=headers))
        assert_ok(client.get("/base/userapi", headers=headers))

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

    print("api smoke ok")


if __name__ == "__main__":
    main()
