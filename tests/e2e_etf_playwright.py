import argparse
import re
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
from playwright.sync_api import Page, expect, sync_playwright


def ok(data=None, **extra):
    payload = {"code": 200, "msg": "OK", "data": data}
    payload.update(extra)
    return payload


def make_monitor(code: str, name: str, *, price: float = 4.203):
    return {
        "code": code,
        "name": name,
        "is_active": True,
        "time_range": "3y",
        "x_drop": 0.15,
        "y_step": 0.05,
        "current_stage": 1,
        "current_price": price,
        "change_percent": 0.0123,
        "peak_price": 4.58,
        "current_retract": 0.0823,
        "range_notice": None,
    }


def make_detail(record):
    return {
        **record,
        "trigger_price": 3.893,
        "klines": [
            {"date": "2026-05-20", "open": 4.10, "close": 4.16, "low": 4.08, "high": 4.20},
            {"date": "2026-05-21", "open": 4.16, "close": 4.12, "low": 4.09, "high": 4.18},
            {"date": "2026-05-22", "open": 4.12, "close": 4.20, "low": 4.11, "high": 4.22},
            {"date": "2026-05-25", "open": 4.20, "close": record["current_price"], "low": 4.18, "high": 4.25},
        ],
        "minutes": [
            {"time": "09:30", "price": 4.19, "volume": 1200},
            {"time": "10:30", "price": 4.21, "volume": 1800},
            {"time": "11:30", "price": 4.20, "volume": 1500},
            {"time": "14:30", "price": record["current_price"], "volume": 2300},
        ],
        "fundamentals": {
            "aum": "CNY 12.345B",
            "valuation": "PE 12.3",
            "holdings": [
                {"name": "Ping An Bank", "percent": "4.2%"},
                {"name": "Kweichow Moutai", "percent": "3.8%"},
            ],
        },
    }


def install_mock_api(page: Page) -> None:
    records = [
        make_monitor("510300", "CSI 300 ETF"),
        make_monitor("159915", "ChiNext ETF", price=2.418),
    ]

    def find_record(code: str):
        return next((item for item in records if item["code"] == code), None)

    def respond(route):
        request = route.request
        parsed = urlparse(request.url)
        path = "/" + parsed.path.split("/api/v1/", 1)[1]
        query = parse_qs(parsed.query)
        body = request.post_data_json if request.post_data else {}

        if path == "/base/access_token" and request.method == "POST":
            return route.fulfill(json=ok({"access_token": "mock-token", "username": body.get("username", "admin")}))
        if path == "/base/userinfo":
            return route.fulfill(json=ok({"username": "admin", "email": "admin@example.com"}))
        if path == "/base/profile" and request.method == "POST":
            return route.fulfill(json=ok({"username": "admin", "email": body.get("email", "admin@example.com")}))
        if path == "/base/profile/test-email" and request.method == "POST":
            return route.fulfill(json=ok({"recipient": "admin@example.com", "subject": "测试邮件发送成功"}))
        if path == "/etf/list" and request.method == "GET":
            return route.fulfill(json=ok(records, total=len(records), page=1, page_size=12))
        if path == "/etf/create" and request.method == "POST":
            code = str(body["code"]).strip()
            record = make_monitor(code, body.get("name") or f"ETF {code}", price=1.234)
            record["time_range"] = body.get("time_range", "3y")
            record["x_drop"] = body.get("x_drop", 0.15)
            record["y_step"] = body.get("y_step", 0.05)
            records.append(record)
            return route.fulfill(json=ok({"monitor": make_detail(record), "sync": {"synced": 1}}))
        if path == "/etf/update" and request.method == "POST":
            record = find_record(body["code"])
            if not record:
                return route.fulfill(status=404, json={"detail": "Not found"})
            record.update({key: value for key, value in body.items() if key in record})
            return route.fulfill(json=ok(make_detail(record)))
        if path == "/etf/detail" and request.method == "GET":
            # parse_qs URL-decodes query values, including non-ASCII values if future filters add them.
            record = find_record(query["code"][0])
            if not record:
                return route.fulfill(status=404, json={"detail": "Not found"})
            return route.fulfill(json=ok(make_detail(record)))
        if path == "/etf/sync" and request.method == "POST":
            target_code = body.get("code")
            targets = [find_record(target_code)] if target_code else records
            for record in [item for item in targets if item]:
                record["current_price"] = round(record["current_price"] + 0.001, 3)
            return route.fulfill(json=ok({"synced": len([item for item in targets if item])}))

        return route.fulfill(status=404, json={"detail": f"Unhandled mock route: {request.method} {path}"})

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


def first_table_row(page: Page):
    table = page.locator(".n-data-table").first
    row = table.locator(".n-data-table-tr:not(.n-data-table-tr--summary)").filter(has_text="510300").first
    return table, row


def main() -> None:
    parser = argparse.ArgumentParser(description="Playwright E2E test for the ETF monitor page.")
    parser.add_argument("--base-url", default="http://127.0.0.1:5173")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="123456")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--screenshot-dir", default="")
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()

    wait_for_url(args.base_url, args.timeout)
    screenshot_dir = Path(args.screenshot_dir) if args.screenshot_dir else None

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not args.headed)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        install_mock_api(page)

        page.goto(f"{args.base_url}/fund/etf", wait_until="networkidle")
        expect(page).to_have_url(re.compile(r"/login"))
        screenshot(page, screenshot_dir, "01-login")

        page.get_by_placeholder("admin").fill(args.username)
        page.get_by_placeholder("123456").fill(args.password)
        page.locator(".n-form button").last.click()
        expect(page).to_have_url(f"{args.base_url}/fund/etf")

        table, row = first_table_row(page)
        expect(table).to_be_visible(timeout=15000)
        expect(row).to_be_visible(timeout=15000)
        expect(table.get_by_text("159915")).to_be_visible()
        expect(table.get_by_text("持仓成本")).to_be_visible()
        expect(table.get_by_text("收益率")).to_be_visible()
        screenshot(page, screenshot_dir, "02-etf-list")

        header_buttons = page.locator("section").first.locator("> div").first.locator("button")
        with page.expect_response(lambda response: "/api/v1/etf/sync" in response.url and response.request.method == "POST"):
            header_buttons.nth(0).click()
        expect(table.get_by_text("510300")).to_be_visible(timeout=15000)

        header_buttons.nth(1).click()
        create_dialog = page.get_by_role("dialog")
        expect(create_dialog).to_be_visible(timeout=15000)
        create_dialog.locator("input").nth(0).fill("588000")
        create_dialog.locator("input").nth(1).fill("Science ETF")
        create_dialog.locator(".n-form-item").filter(has_text="持仓成本").locator("input").fill("1.2340")
        create_dialog.locator(".n-form-item").filter(has_text="持仓份数").locator("input").fill("2000")
        create_dialog.locator("button").last.click()
        expect(table.get_by_text("588000")).to_be_visible(timeout=15000)
        screenshot(page, screenshot_dir, "03-created")

        table, row = first_table_row(page)
        row_buttons = row.locator("button")
        row_buttons.nth(0).click()
        detail_dialog = page.get_by_role("dialog")
        expect(detail_dialog).to_be_visible(timeout=15000)
        expect(detail_dialog.get_by_text("510300")).to_be_visible(timeout=15000)
        expect(detail_dialog.locator(".h-80").first).to_be_visible()
        expect(detail_dialog.get_by_text("历史行情")).to_have_count(0)
        expect(detail_dialog.locator("canvas")).to_have_count(1, timeout=15000)
        detail_dialog.get_by_role("button", name="上涨分批止盈").click()
        expect(detail_dialog.get_by_role("heading", name="上涨分批止盈")).to_be_visible(timeout=15000)
        expect(detail_dialog.get_by_text("下次止盈线")).to_be_visible(timeout=15000)
        expect(detail_dialog.get_by_text("回撤阈值")).to_have_count(0)
        screenshot(page, screenshot_dir, "04-detail")

        page.goto(f"{args.base_url}/account/profile", wait_until="networkidle")
        expect(page).to_have_url(f"{args.base_url}/account/profile")
        profile_section = page.locator("section").first
        expect(profile_section.locator("input").first).to_have_value("admin", timeout=15000)
        with page.expect_response(
            lambda response: "/api/v1/base/profile/test-email" in response.url
            and response.request.method == "POST"
        ):
            profile_section.get_by_role("button", name="测试发送邮件").click()
        expect(page.get_by_text("测试邮件已发送到")).to_be_visible(timeout=15000)
        screenshot(page, screenshot_dir, "05-profile-test-email")

        browser.close()

    print("playwright etf e2e ok")


if __name__ == "__main__":
    main()
