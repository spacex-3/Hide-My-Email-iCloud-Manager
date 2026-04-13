from __future__ import annotations

import json
import mimetypes
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from hme_core import (
    COOKIES_FILE,
    EMAILS_FILE,
    delete_hme,
    export_hme_list,
    fetch_hme_list,
    fetch_hme_list_with_source,
    get_active_auth_status,
    load_cookie_template,
    load_cookies_text,
    login_icloud_account,
    logout_icloud_account,
    request_icloud_2fa_code,
    save_cookies_text,
    summarize_items,
    verify_icloud_2fa_code,
    deactivate_hme,
)

PROJECT_ROOT = Path(__file__).resolve().parent
WEB_ROOT = PROJECT_ROOT / "web"
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))


class AppHandler(BaseHTTPRequestHandler):
    server_version = "HideMyEmailWeb/2.0"

    def do_GET(self) -> None:
        path = urlparse(self.path).path

        if path == "/api/bootstrap":
            self._handle_bootstrap()
            return

        if path == "/api/list":
            self._handle_list()
            return

        if path == "/api/auth/status":
            self._handle_auth_status()
            return

        self._serve_static(path)

    def do_POST(self) -> None:
        path = urlparse(self.path).path

        if path == "/api/cookies/save":
            self._handle_save_cookies()
            return

        if path == "/api/action":
            self._handle_action()
            return

        if path == "/api/auth/login":
            self._handle_auth_login()
            return

        if path == "/api/auth/request-2fa":
            self._handle_auth_request_2fa()
            return

        if path == "/api/auth/verify-2fa":
            self._handle_auth_verify_2fa()
            return

        if path == "/api/auth/logout":
            self._handle_auth_logout()
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def log_message(self, format: str, *args) -> None:
        return

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON 解析失败: {exc}") from exc

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, request_path: str) -> None:
        relative = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
        file_path = (WEB_ROOT / relative).resolve()

        if WEB_ROOT.resolve() not in file_path.parents and file_path != WEB_ROOT.resolve():
            self._send_json(HTTPStatus.FORBIDDEN, {"error": "Forbidden"})
            return

        if not file_path.exists() or not file_path.is_file():
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return

        content = file_path.read_bytes()
        mime_type, _ = mimetypes.guess_type(file_path.name)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{mime_type or 'application/octet-stream'}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _handle_bootstrap(self) -> None:
        self._send_json(
            HTTPStatus.OK,
            {
                "cookiesText": load_cookies_text(),
                "cookieTemplate": load_cookie_template(),
                "cookiesPath": str(COOKIES_FILE.name),
                "emailsPath": str(EMAILS_FILE.name),
                "authStatus": get_active_auth_status(),
            },
        )

    def _handle_auth_status(self) -> None:
        self._send_json(HTTPStatus.OK, {"status": get_active_auth_status()})

    def _handle_auth_login(self) -> None:
        try:
            payload = self._read_json()
            apple_id = str(payload.get("appleId", "")).strip()
            password = str(payload.get("password", ""))
            region = str(payload.get("region", "us"))
            status = login_icloud_account(apple_id, password, region)
        except Exception as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        self._send_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "message": status.get("message", "登录成功"),
                "status": status,
            },
        )

    def _handle_auth_request_2fa(self) -> None:
        try:
            status = request_icloud_2fa_code()
        except Exception as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        self._send_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "message": status.get("message", "已触发验证码"),
                "status": status,
            },
        )

    def _handle_auth_verify_2fa(self) -> None:
        try:
            payload = self._read_json()
            code = str(payload.get("code", "")).strip()
            status = verify_icloud_2fa_code(code)
        except Exception as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        self._send_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "message": status.get("message", "验证码已提交"),
                "status": status,
            },
        )

    def _handle_auth_logout(self) -> None:
        try:
            result = logout_icloud_account()
        except Exception as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        self._send_json(HTTPStatus.OK, result)

    def _handle_list(self) -> None:
        try:
            items, source = fetch_hme_list_with_source()
            export_hme_list(items)
        except Exception as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        self._send_json(
            HTTPStatus.OK,
            {
                "items": items,
                "summary": summarize_items(items),
                "exportedTo": EMAILS_FILE.name,
                "source": source,
                "authStatus": get_active_auth_status(),
            },
        )

    def _handle_save_cookies(self) -> None:
        try:
            payload = self._read_json()
            text = str(payload.get("text", ""))
            save_cookies_text(text)
        except Exception as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        self._send_json(HTTPStatus.OK, {"ok": True, "message": "cookies.txt 已保存"})

    def _handle_action(self) -> None:
        try:
            payload = self._read_json()
            action = str(payload.get("action", "")).strip().lower()
            ids = payload.get("ids", [])
            if action not in {"deactivate", "delete"}:
                raise ValueError("action 只能是 deactivate 或 delete")
            if not isinstance(ids, list) or not ids:
                raise ValueError("ids 不能为空")

            normalized_ids = [str(item).strip() for item in ids if str(item).strip()]
            if not normalized_ids:
                raise ValueError("没有可执行的 anonymousId")

            current_items = fetch_hme_list()
            current_map = {item["anonymousId"]: item for item in current_items}

            results = []
            for anon_id in normalized_ids:
                item = current_map.get(anon_id)
                if not item:
                    results.append({"anonymousId": anon_id, "ok": False, "message": "当前列表里找不到该 ID"})
                    continue

                if action == "deactivate":
                    if not item["isActive"]:
                        ok, message = True, "Already inactive"
                    else:
                        ok, message = deactivate_hme(None, anon_id)
                else:
                    ok, message = delete_hme(None, anon_id)

                results.append(
                    {
                        "anonymousId": anon_id,
                        "email": item.get("email", ""),
                        "ok": ok,
                        "message": message,
                    }
                )

            refreshed_items, source = fetch_hme_list_with_source()
            export_hme_list(refreshed_items)
        except Exception as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        self._send_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "results": results,
                "items": refreshed_items,
                "summary": summarize_items(refreshed_items),
                "exportedTo": EMAILS_FILE.name,
                "source": source,
                "authStatus": get_active_auth_status(),
            },
        )


def run() -> None:
    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
    print(f"Web UI running at http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    run()
