from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests

PROJECT_ROOT = Path(__file__).resolve().parent
COOKIES_FILE = PROJECT_ROOT / "cookies.txt"
COOKIES_TEMPLATE_FILE = PROJECT_ROOT / "cookies.txt.template"
EMAILS_FILE = PROJECT_ROOT / "emails.txt"
DEFAULT_TIMEOUT = 20

HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "text/plain",
    "Origin": "https://www.icloud.com",
    "Referer": "https://www.icloud.com/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "sec-ch-ua": '"Chromium";"Google Chrome";"Not A(Brand"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}

DEFAULT_COOKIE_TEMPLATE = """cookies = {
    'X-APPLE-WEBAUTH-USER': '\"v=1:s=0:d=YOUR_DSID\"',
    'X-APPLE-WEBAUTH-TOKEN': '\"v=2:t=YOUR_TOKEN\"',
    'X-APPLE-DS-WEB-SESSION-TOKEN': '\"YOUR_SESSION_TOKEN\"',
    # ... add all other cookies here
}
"""


def parse_cookie_text(content: str) -> Dict[str, str]:
    text = content.strip()
    if not text:
        raise ValueError("cookies.txt 为空")

    try:
        module = ast.parse(text, mode="exec")
    except SyntaxError as exc:
        raise ValueError(f"Cookie 格式无效: {exc}") from exc

    value_node = None
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "cookies":
                    value_node = node.value
                    break
        elif isinstance(node, ast.Expr) and value_node is None:
            value_node = node.value

        if value_node is not None:
            break

    if value_node is None:
        raise ValueError("cookies.txt 必须包含 cookies = {...} 或纯 dict")

    try:
        parsed = ast.literal_eval(value_node)
    except (SyntaxError, ValueError) as exc:
        raise ValueError(f"Cookie 格式无效: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Cookie 内容必须是 dict")

    cookies: Dict[str, str] = {}
    for key, value in parsed.items():
        cookies[str(key)] = str(value)

    if not cookies:
        raise ValueError("没有解析到任何 cookie")

    return cookies


def load_cookies(path: Path = COOKIES_FILE) -> Dict[str, str]:
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FileNotFoundError("cookies.txt 不存在") from exc

    return parse_cookie_text(content)


def load_cookies_text(path: Path = COOKIES_FILE) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def load_cookie_template(path: Path = COOKIES_TEMPLATE_FILE) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return DEFAULT_COOKIE_TEMPLATE


def save_cookies_text(raw_text: str, path: Path = COOKIES_FILE) -> Dict[str, str]:
    cookies = parse_cookie_text(raw_text)
    normalized = raw_text.strip() + "\n"
    path.write_text(normalized, encoding="utf-8")
    return cookies


def extract_dsid(cookies: Dict[str, str]) -> str:
    raw = cookies.get("X-APPLE-WEBAUTH-USER", "")
    if "d=" not in raw:
        raise ValueError("缺少 X-APPLE-WEBAUTH-USER，无法提取 dsid")

    dsid = raw.split("d=", 1)[1].replace('"', "").strip()
    if not dsid:
        raise ValueError("无法从 X-APPLE-WEBAUTH-USER 提取 dsid")
    return dsid


def api_params(cookies: Dict[str, str]) -> Dict[str, str]:
    dsid = extract_dsid(cookies)
    return {
        "clientBuildNumber": "2542Build17",
        "clientMasteringNumber": "2542Build17",
        "clientId": "auto-script",
        "dsid": dsid,
    }


def parse_response(response: requests.Response) -> Tuple[bool, str]:
    try:
        data = response.json()
    except ValueError:
        return False, f"HTTP {response.status_code}: 返回了无效 JSON"

    if response.ok and data.get("success"):
        return True, data.get("resultMessage", "Success")

    if isinstance(data.get("error"), dict):
        error = data["error"]
        reason = (
            error.get("errorMessage")
            or error.get("reason")
            or error.get("errorCode")
            or "Unknown error"
        )
        return False, str(reason)

    if isinstance(data.get("message"), str):
        return False, data["message"]

    return False, f"HTTP {response.status_code}: 请求失败"


def normalize_hme_item(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "anonymousId": str(item.get("anonymousId", "")),
        "email": str(item.get("hme", "")),
        "isActive": bool(item.get("isActive", False)),
        "label": str(item.get("label") or ""),
        "note": str(item.get("note") or ""),
        "forwardTo": str(item.get("forwardToEmail") or ""),
    }


def fetch_hme_list(cookies: Dict[str, str]) -> List[Dict[str, Any]]:
    url = "https://p158-maildomainws.icloud.com/v2/hme/list"

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            cookies=cookies,
            params=api_params(cookies),
            timeout=DEFAULT_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"请求列表失败: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError("Apple API 返回了无效 JSON") from exc

    emails = payload.get("result", {}).get("hmeEmails")
    if isinstance(emails, list):
        return [normalize_hme_item(item) for item in emails]

    ok, message = parse_response(response)
    if ok:
        return []
    raise RuntimeError(message)


def deactivate_hme(cookies: Dict[str, str], anon_id: str) -> Tuple[bool, str]:
    url = "https://p158-maildomainws.icloud.com/v1/hme/deactivate"
    payload = json.dumps({"anonymousId": anon_id})

    try:
        response = requests.post(
            url,
            headers=HEADERS,
            cookies=cookies,
            params=api_params(cookies),
            data=payload,
            timeout=DEFAULT_TIMEOUT,
        )
    except requests.RequestException as exc:
        return False, f"停用失败: {exc}"

    return parse_response(response)


def delete_hme(cookies: Dict[str, str], anon_id: str) -> Tuple[bool, str]:
    url = "https://p158-maildomainws.icloud.com/v1/hme/delete"
    payload = json.dumps({"anonymousId": anon_id})

    try:
        response = requests.post(
            url,
            headers=HEADERS,
            cookies=cookies,
            params=api_params(cookies),
            data=payload,
            timeout=DEFAULT_TIMEOUT,
        )
    except requests.RequestException as exc:
        return False, f"删除失败: {exc}"

    return parse_response(response)


def export_hme_list(items: List[Dict[str, Any]], path: Path = EMAILS_FILE) -> Path:
    lines = [
        (
            f"anonymousId: {item['anonymousId']} | "
            f"email: {item['email']} | "
            f"active: {item['isActive']}"
        )
        for item in items
    ]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return path


def summarize_items(items: List[Dict[str, Any]]) -> Dict[str, int]:
    total = len(items)
    active = sum(1 for item in items if item["isActive"])
    inactive = total - active
    return {"total": total, "active": active, "inactive": inactive}
