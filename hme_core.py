from __future__ import annotations

import ast
import json
import pprint
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

try:
    from pyicloud import PyiCloudService
except Exception as exc:  # pragma: no cover - depends on optional dependency
    PyiCloudService = None  # type: ignore[assignment]
    PYCLOUD_IMPORT_ERROR: Exception | None = exc
else:  # pragma: no cover - trivial branch
    PYCLOUD_IMPORT_ERROR = None

PROJECT_ROOT = Path(__file__).resolve().parent
COOKIES_FILE = PROJECT_ROOT / "cookies.txt"
COOKIES_TEMPLATE_FILE = PROJECT_ROOT / "cookies.txt.template"
EMAILS_FILE = PROJECT_ROOT / "emails.txt"
AUTH_ROOT = PROJECT_ROOT / ".pyicloud"
ACTIVE_PROFILE_FILE = AUTH_ROOT / "active_profile.json"
DEFAULT_TIMEOUT = 20
REGION_LABELS = {"us": "美国区", "cn": "中国区"}

_RUNTIME_LOCK = threading.RLock()
_RUNTIME_SERVICE: Any = None
_RUNTIME_PROFILE_KEY: str | None = None

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


def format_cookie_text(cookies: Dict[str, str]) -> str:
    normalized = {str(key): str(value) for key, value in sorted(cookies.items())}
    body = pprint.pformat(normalized, sort_dicts=True, width=120)
    return f"cookies = {body}\n"


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


def save_cookies_mapping(cookies: Dict[str, str], path: Path = COOKIES_FILE) -> Dict[str, str]:
    path.write_text(format_cookie_text(cookies), encoding="utf-8")
    return cookies


def save_cookies_text(raw_text: str, path: Path = COOKIES_FILE) -> Dict[str, str]:
    cookies = parse_cookie_text(raw_text)
    return save_cookies_mapping(cookies, path=path)


def normalize_region(region: Optional[str]) -> str:
    value = (region or "us").strip().lower()
    aliases = {
        "us": "us",
        "usa": "us",
        "global": "us",
        "world": "us",
        "cn": "cn",
        "china": "cn",
        "mainland": "cn",
        "zh-cn": "cn",
    }
    normalized = aliases.get(value)
    if not normalized:
        raise ValueError("region 只能是 us 或 cn")
    return normalized


def region_label(region: Optional[str]) -> str:
    return REGION_LABELS.get(normalize_region(region), "未知")


def auth_supported() -> bool:
    return PYCLOUD_IMPORT_ERROR is None and PyiCloudService is not None


def auth_support_message() -> str:
    if auth_supported():
        return "可用"
    detail = f": {PYCLOUD_IMPORT_ERROR}" if PYCLOUD_IMPORT_ERROR else ""
    return f"未安装 pyicloud 依赖，请先执行 pip install -r requirements.txt{detail}"


def ensure_auth_root() -> None:
    AUTH_ROOT.mkdir(parents=True, exist_ok=True)


def session_directory_for_region(region: Optional[str]) -> Path:
    ensure_auth_root()
    session_dir = AUTH_ROOT / normalize_region(region)
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def profile_key(apple_id: str, region: str) -> str:
    return f"{normalize_region(region)}::{apple_id.strip().lower()}"


def load_active_profile() -> Optional[Dict[str, str]]:
    try:
        raw = ACTIVE_PROFILE_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None

    apple_id = str(payload.get("appleId", "")).strip()
    if not apple_id:
        return None

    region = normalize_region(str(payload.get("region", "us")))
    return {"appleId": apple_id, "region": region}


def save_active_profile(apple_id: str, region: str) -> Dict[str, str]:
    ensure_auth_root()
    payload = {
        "appleId": apple_id.strip(),
        "region": normalize_region(region),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    ACTIVE_PROFILE_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {"appleId": payload["appleId"], "region": payload["region"]}


def clear_active_profile() -> None:
    try:
        ACTIVE_PROFILE_FILE.unlink()
    except FileNotFoundError:
        return


def runtime_service_key() -> Optional[str]:
    with _RUNTIME_LOCK:
        return _RUNTIME_PROFILE_KEY


def clear_runtime_service() -> None:
    global _RUNTIME_PROFILE_KEY, _RUNTIME_SERVICE
    with _RUNTIME_LOCK:
        _RUNTIME_PROFILE_KEY = None
        _RUNTIME_SERVICE = None


def load_persisted_authenticated_service(apple_id: str, region: str) -> Any | None:
    if not auth_supported():
        return None

    try:
        service = build_service(
            apple_id,
            region,
            password="",
            authenticate=True,
        )
    except Exception:
        return None

    if bool(getattr(service, "requires_2fa", False)):
        return None

    if not bool(getattr(service, "is_trusted_session", False)):
        return None

    return service


def set_runtime_service(service: Any, apple_id: str, region: str) -> Any:
    global _RUNTIME_PROFILE_KEY, _RUNTIME_SERVICE
    key = profile_key(apple_id, region)
    with _RUNTIME_LOCK:
        _RUNTIME_PROFILE_KEY = key
        _RUNTIME_SERVICE = service
    return service


def build_service(
    apple_id: str,
    region: str,
    password: Optional[str] = None,
    *,
    authenticate: bool,
) -> Any:
    if not auth_supported():
        raise RuntimeError(auth_support_message())

    normalized_region = normalize_region(region)
    return PyiCloudService(  # type: ignore[misc]
        apple_id.strip(),
        password=password,
        cookie_directory=str(session_directory_for_region(normalized_region)),
        china_mainland=(normalized_region == "cn"),
        authenticate=authenticate,
    )


def get_runtime_service(apple_id: str, region: str) -> Any | None:
    key = profile_key(apple_id, region)
    with _RUNTIME_LOCK:
        if _RUNTIME_PROFILE_KEY == key:
            return _RUNTIME_SERVICE
    return None


def has_pending_mfa(service: Any) -> bool:
    try:
        if getattr(service, "requires_2fa", False):
            return True
        return bool(getattr(service, "_auth_data", {}))
    except Exception:
        return False


def service_file_info(service: Any) -> Dict[str, str]:
    info: Dict[str, str] = {}
    session = getattr(service, "session", None)
    if session is not None:
        session_path = getattr(session, "session_path", None)
        cookiejar_path = getattr(session, "cookiejar_path", None)
        if session_path:
            info["sessionPath"] = str(session_path)
        if cookiejar_path:
            info["cookiejarPath"] = str(cookiejar_path)
    return info


def export_service_cookies(service: Any, path: Path = COOKIES_FILE) -> Dict[str, str]:
    session = getattr(service, "session", None)
    if session is None:
        return {}

    cookie_jar = getattr(session, "cookies", None)
    if cookie_jar is None:
        return {}

    if hasattr(cookie_jar, "get_dict"):
        cookies = {str(k): str(v) for k, v in cookie_jar.get_dict().items()}
    else:
        cookies = {str(k): str(v) for k, v in dict(cookie_jar).items()}

    if cookies:
        save_cookies_mapping(cookies, path=path)
    return cookies


def serialize_auth_status(
    service: Any | None,
    *,
    apple_id: str = "",
    region: str = "us",
    validated_status: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    normalized_region = normalize_region(region)
    status: Dict[str, Any] = {
        "available": auth_supported(),
        "availableMessage": auth_support_message(),
        "hasProfile": bool(apple_id),
        "appleId": apple_id,
        "region": normalized_region,
        "regionLabel": region_label(normalized_region),
        "authenticated": False,
        "trustedSession": False,
        "requires2FA": False,
        "requires2SA": False,
        "deliveryMethod": "unknown",
        "deliveryNotice": None,
        "sessionDirectory": str(session_directory_for_region(normalized_region)),
        "source": "none",
    }

    if service is None:
        return status

    status.update(service_file_info(service))

    session = getattr(service, "session", None)
    session_data = getattr(session, "data", {}) if session is not None else {}
    status["hasSessionToken"] = bool(session_data.get("session_token"))
    status["hasTrustToken"] = bool(session_data.get("trust_token"))

    if validated_status is not None:
        status.update(
            {
                "authenticated": bool(validated_status.get("authenticated")),
                "trustedSession": bool(validated_status.get("trusted_session")),
                "requires2FA": bool(validated_status.get("requires_2fa")),
                "requires2SA": bool(validated_status.get("requires_2sa")),
            }
        )
    else:
        status.update(
            {
                "authenticated": bool(getattr(service, "is_trusted_session", False))
                and not bool(getattr(service, "requires_2fa", False))
                and bool(getattr(service, "data", {})),
                "trustedSession": bool(getattr(service, "is_trusted_session", False)),
                "requires2FA": bool(getattr(service, "requires_2fa", False)),
                "requires2SA": bool(getattr(service, "requires_2sa", False)),
            }
        )

    try:
        status["deliveryMethod"] = str(getattr(service, "two_factor_delivery_method", "unknown"))
    except Exception:
        pass

    try:
        status["deliveryNotice"] = getattr(service, "two_factor_delivery_notice", None)
    except Exception:
        pass

    if status["authenticated"]:
        status["source"] = "session"
    elif status["requires2FA"]:
        status["source"] = "pending-2fa"

    return status


def get_active_auth_status() -> Dict[str, Any]:
    if not auth_supported():
        return serialize_auth_status(None)

    profile = load_active_profile()
    if not profile:
        return serialize_auth_status(None)

    apple_id = profile["appleId"]
    region = profile["region"]
    runtime_service = get_runtime_service(apple_id, region)

    if runtime_service is not None and has_pending_mfa(runtime_service):
        return serialize_auth_status(runtime_service, apple_id=apple_id, region=region)

    service = load_persisted_authenticated_service(apple_id, region)
    if service is None:
        clear_runtime_service()
        return serialize_auth_status(None, apple_id=apple_id, region=region)

    try:
        validated = service.get_auth_status()
    except Exception:
        clear_runtime_service()
        return serialize_auth_status(None, apple_id=apple_id, region=region)

    status = serialize_auth_status(
        service,
        apple_id=apple_id,
        region=region,
        validated_status=validated,
    )

    if status["authenticated"]:
        export_service_cookies(service)
        set_runtime_service(service, apple_id, region)

    return status


def login_icloud_account(apple_id: str, password: str, region: str) -> Dict[str, Any]:
    if not apple_id.strip():
        raise ValueError("Apple ID 不能为空")
    if not password:
        raise ValueError("密码不能为空")

    normalized_region = normalize_region(region)
    service = build_service(
        apple_id.strip(),
        normalized_region,
        password=password,
        authenticate=True,
    )
    set_runtime_service(service, apple_id.strip(), normalized_region)
    save_active_profile(apple_id.strip(), normalized_region)

    status = serialize_auth_status(service, apple_id=apple_id.strip(), region=normalized_region)
    if status["authenticated"]:
        export_service_cookies(service)
        status["message"] = "登录成功，已复用/持久化本地 session。"
    elif status["requires2FA"]:
        status["message"] = "账号密码已通过，接下来需要二次验证。请点击“触发验证码 / 设备提示”。"
    else:
        status["message"] = "登录流程已完成，但当前会话尚未通过验证。"
    return status


def require_runtime_service_for_auth() -> tuple[Any, Dict[str, str]]:
    profile = load_active_profile()
    if not profile:
        raise RuntimeError("当前没有已保存的账号，请先登录")

    apple_id = profile["appleId"]
    region = profile["region"]
    service = get_runtime_service(apple_id, region)
    if service is None:
        raise RuntimeError("当前没有可继续的登录上下文，请重新输入账号密码登录")

    return service, profile


def request_icloud_2fa_code() -> Dict[str, Any]:
    if not auth_supported():
        raise RuntimeError(auth_support_message())

    service, profile = require_runtime_service_for_auth()
    if not bool(getattr(service, "requires_2fa", False)):
        return serialize_auth_status(service, apple_id=profile["appleId"], region=profile["region"])

    supported = bool(service.request_2fa_code())
    status = serialize_auth_status(service, apple_id=profile["appleId"], region=profile["region"])
    status["deliveryTriggered"] = supported
    if supported:
        status["message"] = "已触发验证码/设备提示，请在 Apple 设备或短信中查看验证码。"
    else:
        status["message"] = "当前 2FA 方式无法自动触发，可能需要安全密钥或手动在 Apple 设备上确认。"
    return status


def verify_icloud_2fa_code(code: str) -> Dict[str, Any]:
    if not code.strip():
        raise ValueError("验证码不能为空")

    service, profile = require_runtime_service_for_auth()
    success = bool(service.validate_2fa_code(code.strip()))
    status = serialize_auth_status(service, apple_id=profile["appleId"], region=profile["region"])
    status["verificationPassed"] = success

    if status["authenticated"]:
        export_service_cookies(service)
        status["message"] = "二次验证成功，本地持久化 session 已可复用。"
    elif success:
        status["message"] = "验证码已提交，但当前会话还未完全受信任，请稍后再试。"
    else:
        status["message"] = "验证码校验失败，请重新输入。"
    return status


def logout_icloud_account() -> Dict[str, Any]:
    profile = load_active_profile()
    if not profile:
        clear_runtime_service()
        return {
            "ok": True,
            "message": "当前没有已保存的登录会话。",
            "status": serialize_auth_status(None),
        }

    apple_id = profile["appleId"]
    region = profile["region"]
    service = get_runtime_service(apple_id, region)
    if service is None and auth_supported():
        service = build_service(apple_id, region, authenticate=False)

    if service is not None:
        try:
            service.logout(clear_local_session=True)
        except Exception:
            session = getattr(service, "session", None)
            if session is not None and hasattr(session, "clear_persistence"):
                session.clear_persistence(remove_files=True)

    clear_active_profile()
    clear_runtime_service()
    return {
        "ok": True,
        "message": "本地持久化登录状态已清除。",
        "status": serialize_auth_status(None),
    }


def get_active_authenticated_service() -> Any | None:
    if not auth_supported():
        return None

    profile = load_active_profile()
    if not profile:
        return None

    apple_id = profile["appleId"]
    region = profile["region"]
    runtime_service = get_runtime_service(apple_id, region)

    if runtime_service is not None and has_pending_mfa(runtime_service):
        return None

    service = load_persisted_authenticated_service(apple_id, region)
    if service is None:
        return None

    set_runtime_service(service, apple_id, region)
    export_service_cookies(service)
    return service


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
    email = item.get("hme")
    if email is None:
        email = item.get("email")

    return {
        "anonymousId": str(item.get("anonymousId", "")),
        "email": str(email or ""),
        "isActive": bool(item.get("isActive", False)),
        "label": str(item.get("label") or ""),
        "note": str(item.get("note") or ""),
        "forwardTo": str(item.get("forwardToEmail") or item.get("forwardTo") or ""),
    }


def fetch_hme_list_from_cookies(cookies: Dict[str, str]) -> List[Dict[str, Any]]:
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


def fetch_hme_list_from_service(service: Any) -> List[Dict[str, Any]]:
    try:
        endpoint = service.hidemyemail._list_endpoint
        response = service.session.get(
            endpoint,
            params=service.params,
            timeout=DEFAULT_TIMEOUT,
        )
        payload = response.json()
        emails = payload.get("result", {}).get("hmeEmails")
        if not isinstance(emails, list):
            raise RuntimeError("Hide My Email 返回数据格式异常")
        export_service_cookies(service)
        return [normalize_hme_item(item) for item in emails]
    except Exception as exc:
        raise RuntimeError(f"请求列表失败: {exc}") from exc


def fetch_hme_list(cookies: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    if cookies is None:
        service = get_active_authenticated_service()
        if service is not None:
            return fetch_hme_list_from_service(service)
        cookies = load_cookies()
    return fetch_hme_list_from_cookies(cookies)


def fetch_hme_list_with_source(cookies: Optional[Dict[str, str]] = None) -> Tuple[List[Dict[str, Any]], str]:
    if cookies is None:
        service = get_active_authenticated_service()
        if service is not None:
            return fetch_hme_list_from_service(service), "session"
        cookies = load_cookies()
    return fetch_hme_list_from_cookies(cookies), "cookies"


def deactivate_hme_with_cookies(cookies: Dict[str, str], anon_id: str) -> Tuple[bool, str]:
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


def deactivate_hme_with_service(service: Any, anon_id: str) -> Tuple[bool, str]:
    try:
        response = service.session.post(
            service.hidemyemail._deactivate_endpoint,
            params=service.params,
            json={"anonymousId": anon_id},
            timeout=DEFAULT_TIMEOUT,
        )
        ok, message = parse_response(response)
        if ok:
            export_service_cookies(service)
        return ok, message
    except Exception as exc:
        return False, f"停用失败: {exc}"


def deactivate_hme(cookies: Optional[Dict[str, str]], anon_id: str) -> Tuple[bool, str]:
    if cookies is None:
        service = get_active_authenticated_service()
        if service is not None:
            return deactivate_hme_with_service(service, anon_id)
        cookies = load_cookies()
    return deactivate_hme_with_cookies(cookies, anon_id)


def delete_hme_with_cookies(cookies: Dict[str, str], anon_id: str) -> Tuple[bool, str]:
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


def delete_hme_with_service(service: Any, anon_id: str) -> Tuple[bool, str]:
    try:
        response = service.session.post(
            service.hidemyemail._delete_endpoint,
            params=service.params,
            json={"anonymousId": anon_id},
            timeout=DEFAULT_TIMEOUT,
        )
        ok, message = parse_response(response)
        if ok:
            export_service_cookies(service)
        return ok, message
    except Exception as exc:
        return False, f"删除失败: {exc}"


def delete_hme(cookies: Optional[Dict[str, str]], anon_id: str) -> Tuple[bool, str]:
    if cookies is None:
        service = get_active_authenticated_service()
        if service is not None:
            return delete_hme_with_service(service, anon_id)
        cookies = load_cookies()
    return delete_hme_with_cookies(cookies, anon_id)


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
