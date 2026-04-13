from __future__ import annotations

import ast
import json
import pprint
import shutil
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
PROFILES_FILE = AUTH_ROOT / "profiles.json"
ACCOUNT_LISTS_ROOT = AUTH_ROOT / "lists"
ACCOUNT_COOKIES_ROOT = AUTH_ROOT / "cookies"
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


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def normalize_apple_id(apple_id: str) -> str:
    value = apple_id.strip().lower()
    if not value:
        raise ValueError("Apple ID 不能为空")
    return value


def auth_supported() -> bool:
    return PYCLOUD_IMPORT_ERROR is None and PyiCloudService is not None


def auth_support_message() -> str:
    if auth_supported():
        return "可用"
    detail = f": {PYCLOUD_IMPORT_ERROR}" if PYCLOUD_IMPORT_ERROR else ""
    return f"未安装 pyicloud 依赖，请先执行 pip install -r requirements.txt{detail}"


def ensure_auth_root() -> None:
    AUTH_ROOT.mkdir(parents=True, exist_ok=True)
    ACCOUNT_LISTS_ROOT.mkdir(parents=True, exist_ok=True)
    ACCOUNT_COOKIES_ROOT.mkdir(parents=True, exist_ok=True)


def relative_project_path(path: Path | None) -> str:
    if not path:
        return ""
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except Exception:
        return str(path)


def session_directory_for_region(region: Optional[str]) -> Path:
    ensure_auth_root()
    session_dir = AUTH_ROOT / normalize_region(region)
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def safe_account_fragment(apple_id: str) -> str:
    value = "".join(ch for ch in normalize_apple_id(apple_id) if ch.isalnum())
    return value or "account"


def storage_id_for_profile(apple_id: str, region: str) -> str:
    return f"{normalize_region(region)}__{safe_account_fragment(apple_id)}"


def profile_key(apple_id: str, region: str) -> str:
    return f"{normalize_region(region)}::{normalize_apple_id(apple_id)}"


def account_list_json_path(apple_id: str, region: str) -> Path:
    ensure_auth_root()
    return ACCOUNT_LISTS_ROOT / f"{storage_id_for_profile(apple_id, region)}.json"


def account_list_text_path(apple_id: str, region: str) -> Path:
    ensure_auth_root()
    return ACCOUNT_LISTS_ROOT / f"{storage_id_for_profile(apple_id, region)}.txt"


def account_cookie_snapshot_path(apple_id: str, region: str) -> Path:
    ensure_auth_root()
    return ACCOUNT_COOKIES_ROOT / f"{storage_id_for_profile(apple_id, region)}.txt"


def make_profile_record(apple_id: str, region: str, existing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    existing = dict(existing or {})
    normalized_id = normalize_apple_id(apple_id)
    normalized_region = normalize_region(region)
    storage_id = storage_id_for_profile(normalized_id, normalized_region)

    record = {
        "profileKey": profile_key(normalized_id, normalized_region),
        "appleId": normalized_id,
        "region": normalized_region,
        "regionLabel": region_label(normalized_region),
        "storageId": storage_id,
        "sessionDirectory": relative_project_path(session_directory_for_region(normalized_region)),
        "listJsonPath": relative_project_path(account_list_json_path(normalized_id, normalized_region)),
        "listTextPath": relative_project_path(account_list_text_path(normalized_id, normalized_region)),
        "cookieSnapshotPath": relative_project_path(account_cookie_snapshot_path(normalized_id, normalized_region)),
        "createdAt": existing.get("createdAt") or now_iso(),
        "updatedAt": now_iso(),
        "lastUsedAt": existing.get("lastUsedAt"),
        "lastAuthenticatedAt": existing.get("lastAuthenticatedAt"),
        "lastFetchAt": existing.get("lastFetchAt"),
        "cachedSummary": existing.get("cachedSummary") or {"total": 0, "active": 0, "inactive": 0},
        "cachedAt": existing.get("cachedAt"),
        "cachedListAvailable": bool(existing.get("cachedListAvailable", False)),
        "hasSessionFiles": bool(existing.get("hasSessionFiles", False)),
        "lastKnownAuthenticated": bool(existing.get("lastKnownAuthenticated", False)),
        "lastKnownTrusted": bool(existing.get("lastKnownTrusted", False)),
    }
    return record


def load_profiles_registry() -> Dict[str, Dict[str, Any]]:
    ensure_auth_root()
    try:
        raw = PROFILES_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}

    if not isinstance(payload, dict):
        return {}

    profiles = payload.get("profiles", payload)
    if not isinstance(profiles, dict):
        return {}

    result: Dict[str, Dict[str, Any]] = {}
    for key, value in profiles.items():
        if isinstance(value, dict):
            result[str(key)] = value
    return result


def save_profiles_registry(registry: Dict[str, Dict[str, Any]]) -> None:
    ensure_auth_root()
    payload = {
        "updatedAt": now_iso(),
        "profiles": registry,
    }
    PROFILES_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def upsert_profile_record(
    apple_id: str,
    region: str,
    *,
    service: Any | None = None,
    updates: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    normalized_id = normalize_apple_id(apple_id)
    normalized_region = normalize_region(region)
    registry = load_profiles_registry()
    key = profile_key(normalized_id, normalized_region)
    record = make_profile_record(normalized_id, normalized_region, registry.get(key))

    session_path = session_directory_for_region(normalized_region) / f"{safe_account_fragment(normalized_id)}.session"
    cookiejar_path = session_directory_for_region(normalized_region) / f"{safe_account_fragment(normalized_id)}.cookiejar"
    record["hasSessionFiles"] = session_path.exists() and cookiejar_path.exists()

    if service is not None:
        status = {
            "authenticated": bool(getattr(service, "is_trusted_session", False)) and not bool(getattr(service, "requires_2fa", False)),
            "trustedSession": bool(getattr(service, "is_trusted_session", False)),
        }
        record["lastKnownAuthenticated"] = status["authenticated"]
        record["lastKnownTrusted"] = status["trustedSession"]
        if status["authenticated"]:
            record["lastAuthenticatedAt"] = now_iso()
        service_info = service_file_info(service)
        if service_info.get("sessionPath"):
            record["sessionPath"] = relative_project_path(Path(service_info["sessionPath"]))
        if service_info.get("cookiejarPath"):
            record["cookiejarPath"] = relative_project_path(Path(service_info["cookiejarPath"]))

    if updates:
        record.update(updates)

    record["updatedAt"] = now_iso()
    registry[key] = record
    save_profiles_registry(registry)
    return record


def remove_profile_record(profile_key_value: str) -> None:
    registry = load_profiles_registry()
    if profile_key_value in registry:
        del registry[profile_key_value]
        save_profiles_registry(registry)


def get_profile_record(profile_key_value: str) -> Optional[Dict[str, Any]]:
    return load_profiles_registry().get(profile_key_value)


def list_saved_accounts() -> List[Dict[str, Any]]:
    active = load_active_profile()
    active_key = profile_key(active["appleId"], active["region"]) if active else None
    accounts: List[Dict[str, Any]] = []
    for key, raw in load_profiles_registry().items():
        record = make_profile_record(raw.get("appleId", ""), raw.get("region", "us"), raw)
        record["profileKey"] = key
        session_dir = session_directory_for_region(record["region"])
        session_path = session_dir / f"{safe_account_fragment(record['appleId'])}.session"
        cookiejar_path = session_dir / f"{safe_account_fragment(record['appleId'])}.cookiejar"
        record["hasSessionFiles"] = session_path.exists() and cookiejar_path.exists()
        record["sessionPath"] = relative_project_path(session_path)
        record["cookiejarPath"] = relative_project_path(cookiejar_path)
        record["cachedListAvailable"] = account_list_json_path(record["appleId"], record["region"]).exists()
        record["isActive"] = key == active_key
        accounts.append(record)

    accounts.sort(
        key=lambda item: (
            0 if item.get("isActive") else 1,
            item.get("lastUsedAt") or "",
            item.get("lastAuthenticatedAt") or "",
            item["appleId"],
        ),
        reverse=True,
    )
    if accounts:
        active_accounts = [item for item in accounts if item.get("isActive")]
        inactive_accounts = [item for item in accounts if not item.get("isActive")]
        accounts = active_accounts + inactive_accounts
    return accounts


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
    return {"appleId": normalize_apple_id(apple_id), "region": region}


def save_active_profile(apple_id: str, region: str) -> Dict[str, str]:
    ensure_auth_root()
    normalized_id = normalize_apple_id(apple_id)
    normalized_region = normalize_region(region)
    payload = {
        "appleId": normalized_id,
        "region": normalized_region,
        "updatedAt": now_iso(),
    }
    ACTIVE_PROFILE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    upsert_profile_record(normalized_id, normalized_region, updates={"lastUsedAt": now_iso()})
    return {"appleId": normalized_id, "region": normalized_region}


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


def set_runtime_service(service: Any, apple_id: str, region: str) -> Any:
    global _RUNTIME_PROFILE_KEY, _RUNTIME_SERVICE
    key = profile_key(apple_id, region)
    with _RUNTIME_LOCK:
        _RUNTIME_PROFILE_KEY = key
        _RUNTIME_SERVICE = service
    return service


def get_runtime_service(apple_id: str, region: str) -> Any | None:
    key = profile_key(apple_id, region)
    with _RUNTIME_LOCK:
        if _RUNTIME_PROFILE_KEY == key:
            return _RUNTIME_SERVICE
    return None


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
        normalize_apple_id(apple_id),
        password=password,
        cookie_directory=str(session_directory_for_region(normalized_region)),
        china_mainland=(normalized_region == "cn"),
        authenticate=authenticate,
    )


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


def is_active_profile(apple_id: str, region: str) -> bool:
    active = load_active_profile()
    if not active:
        return False
    return profile_key(apple_id, region) == profile_key(active["appleId"], active["region"])


def copy_to_active_exports(apple_id: str, region: str) -> None:
    text_path = account_list_text_path(apple_id, region)
    cookie_path = account_cookie_snapshot_path(apple_id, region)
    if text_path.exists():
        shutil.copyfile(text_path, EMAILS_FILE)
    if cookie_path.exists():
        shutil.copyfile(cookie_path, COOKIES_FILE)


def export_service_cookies(service: Any, apple_id: str, region: str) -> Dict[str, str]:
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

    if not cookies:
        return {}

    snapshot_path = account_cookie_snapshot_path(apple_id, region)
    save_cookies_mapping(cookies, path=snapshot_path)
    if is_active_profile(apple_id, region):
        save_cookies_mapping(cookies, path=COOKIES_FILE)
    return cookies


def summarize_items(items: List[Dict[str, Any]]) -> Dict[str, int]:
    total = len(items)
    active = sum(1 for item in items if item["isActive"])
    inactive = total - active
    return {"total": total, "active": active, "inactive": inactive}


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


def save_account_list_cache(apple_id: str, region: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    normalized_id = normalize_apple_id(apple_id)
    normalized_region = normalize_region(region)
    json_path = account_list_json_path(normalized_id, normalized_region)
    text_path = account_list_text_path(normalized_id, normalized_region)
    summary = summarize_items(items)
    payload = {
        "appleId": normalized_id,
        "region": normalized_region,
        "updatedAt": now_iso(),
        "summary": summary,
        "items": items,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    export_hme_list(items, path=text_path)
    if is_active_profile(normalized_id, normalized_region):
        export_hme_list(items, path=EMAILS_FILE)
    upsert_profile_record(
        normalized_id,
        normalized_region,
        updates={
            "lastFetchAt": payload["updatedAt"],
            "cachedSummary": summary,
            "cachedAt": payload["updatedAt"],
            "cachedListAvailable": True,
        },
    )
    return {
        "items": items,
        "summary": summary,
        "updatedAt": payload["updatedAt"],
        "accountExportPath": relative_project_path(text_path),
        "activeExportPath": relative_project_path(EMAILS_FILE),
        "cacheJsonPath": relative_project_path(json_path),
    }


def load_account_list_cache(apple_id: str, region: str) -> Optional[Dict[str, Any]]:
    json_path = account_list_json_path(apple_id, region)
    if not json_path.exists():
        return None

    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    items = payload.get("items")
    if not isinstance(items, list):
        return None

    normalized_items = [normalize_hme_item(item) for item in items]
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        summary = summarize_items(normalized_items)
    return {
        "items": normalized_items,
        "summary": summary,
        "updatedAt": payload.get("updatedAt"),
        "accountExportPath": relative_project_path(account_list_text_path(apple_id, region)),
        "activeExportPath": relative_project_path(EMAILS_FILE),
        "cacheJsonPath": relative_project_path(json_path),
    }


def get_active_cached_list() -> Optional[Dict[str, Any]]:
    profile = load_active_profile()
    if not profile:
        return None
    cached = load_account_list_cache(profile["appleId"], profile["region"])
    if cached and is_active_profile(profile["appleId"], profile["region"]):
        text_path = account_list_text_path(profile["appleId"], profile["region"])
        if text_path.exists():
            shutil.copyfile(text_path, EMAILS_FILE)
        cookie_path = account_cookie_snapshot_path(profile["appleId"], profile["region"])
        if cookie_path.exists():
            shutil.copyfile(cookie_path, COOKIES_FILE)
    return cached


def serialize_auth_status(
    service: Any | None,
    *,
    apple_id: str = "",
    region: str = "us",
    validated_status: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    normalized_region = normalize_region(region)
    normalized_id = apple_id.strip().lower() if apple_id else ""
    profile_record = None
    if normalized_id:
        profile_record = get_profile_record(profile_key(normalized_id, normalized_region))

    status: Dict[str, Any] = {
        "available": auth_supported(),
        "availableMessage": auth_support_message(),
        "hasProfile": bool(normalized_id),
        "appleId": normalized_id,
        "region": normalized_region,
        "regionLabel": region_label(normalized_region),
        "profileKey": profile_key(normalized_id, normalized_region) if normalized_id else "",
        "storageId": storage_id_for_profile(normalized_id, normalized_region) if normalized_id else "",
        "authenticated": False,
        "trustedSession": False,
        "requires2FA": False,
        "requires2SA": False,
        "deliveryMethod": "unknown",
        "deliveryNotice": None,
        "sessionDirectory": relative_project_path(session_directory_for_region(normalized_region)),
        "source": "none",
        "sessionPath": profile_record.get("sessionPath", "") if profile_record else "",
        "cookiejarPath": profile_record.get("cookiejarPath", "") if profile_record else "",
        "cookieSnapshotPath": profile_record.get("cookieSnapshotPath", "") if profile_record else relative_project_path(account_cookie_snapshot_path(normalized_id, normalized_region)) if normalized_id else "",
        "accountExportPath": profile_record.get("listTextPath", "") if profile_record else relative_project_path(account_list_text_path(normalized_id, normalized_region)) if normalized_id else "",
        "cacheJsonPath": profile_record.get("listJsonPath", "") if profile_record else relative_project_path(account_list_json_path(normalized_id, normalized_region)) if normalized_id else "",
        "lastFetchAt": profile_record.get("lastFetchAt") if profile_record else None,
        "cachedSummary": profile_record.get("cachedSummary") if profile_record else {"total": 0, "active": 0, "inactive": 0},
    }

    if service is None:
        return status

    session = getattr(service, "session", None)
    session_data = getattr(session, "data", {}) if session is not None else {}
    status["hasSessionToken"] = bool(session_data.get("session_token"))
    status["hasTrustToken"] = bool(session_data.get("trust_token"))

    info = service_file_info(service)
    if info.get("sessionPath"):
        status["sessionPath"] = relative_project_path(Path(info["sessionPath"]))
    if info.get("cookiejarPath"):
        status["cookiejarPath"] = relative_project_path(Path(info["cookiejarPath"]))

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
                "authenticated": bool(getattr(service, "is_trusted_session", False)) and not bool(getattr(service, "requires_2fa", False)) and bool(getattr(service, "data", {})),
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


def load_persisted_authenticated_service(apple_id: str, region: str) -> Any | None:
    if not auth_supported():
        return None

    try:
        service = build_service(apple_id, region, password="", authenticate=True)
    except Exception:
        return None

    if bool(getattr(service, "requires_2fa", False)):
        return None
    if not bool(getattr(service, "is_trusted_session", False)):
        return None
    return service


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
        status = serialize_auth_status(None, apple_id=apple_id, region=region)
        upsert_profile_record(apple_id, region, updates={"lastKnownAuthenticated": False, "lastKnownTrusted": False})
        return status

    try:
        validated = service.get_auth_status()
    except Exception:
        clear_runtime_service()
        status = serialize_auth_status(None, apple_id=apple_id, region=region)
        upsert_profile_record(apple_id, region, updates={"lastKnownAuthenticated": False, "lastKnownTrusted": False})
        return status

    set_runtime_service(service, apple_id, region)
    export_service_cookies(service, apple_id, region)
    upsert_profile_record(
        apple_id,
        region,
        service=service,
        updates={
            "lastKnownAuthenticated": bool(validated.get("authenticated")),
            "lastKnownTrusted": bool(validated.get("trusted_session")),
            "lastUsedAt": now_iso(),
        },
    )
    return serialize_auth_status(service, apple_id=apple_id, region=region, validated_status=validated)


def get_saved_accounts_payload() -> List[Dict[str, Any]]:
    return list_saved_accounts()


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
    export_service_cookies(service, apple_id, region)
    upsert_profile_record(
        apple_id,
        region,
        service=service,
        updates={"lastUsedAt": now_iso(), "lastKnownAuthenticated": True, "lastKnownTrusted": True},
    )
    return service


def login_icloud_account(apple_id: str, password: str, region: str) -> Dict[str, Any]:
    normalized_id = normalize_apple_id(apple_id)
    if not password:
        raise ValueError("密码不能为空")
    normalized_region = normalize_region(region)

    service = build_service(normalized_id, normalized_region, password=password, authenticate=True)
    set_runtime_service(service, normalized_id, normalized_region)
    save_active_profile(normalized_id, normalized_region)
    export_service_cookies(service, normalized_id, normalized_region)
    upsert_profile_record(
        normalized_id,
        normalized_region,
        service=service,
        updates={
            "lastUsedAt": now_iso(),
            "lastAuthenticatedAt": now_iso(),
            "lastKnownAuthenticated": bool(getattr(service, "is_trusted_session", False)) and not bool(getattr(service, "requires_2fa", False)),
            "lastKnownTrusted": bool(getattr(service, "is_trusted_session", False)),
        },
    )

    status = serialize_auth_status(service, apple_id=normalized_id, region=normalized_region)
    if status["authenticated"]:
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
    upsert_profile_record(profile["appleId"], profile["region"], service=service)
    return status


def verify_icloud_2fa_code(code: str) -> Dict[str, Any]:
    if not code.strip():
        raise ValueError("验证码不能为空")

    service, profile = require_runtime_service_for_auth()
    success = bool(service.validate_2fa_code(code.strip()))
    export_service_cookies(service, profile["appleId"], profile["region"])
    upsert_profile_record(
        profile["appleId"],
        profile["region"],
        service=service,
        updates={
            "lastAuthenticatedAt": now_iso() if success else None,
            "lastKnownAuthenticated": bool(success and getattr(service, "is_trusted_session", False)),
            "lastKnownTrusted": bool(getattr(service, "is_trusted_session", False)),
            "lastUsedAt": now_iso(),
        },
    )
    status = serialize_auth_status(service, apple_id=profile["appleId"], region=profile["region"])
    status["verificationPassed"] = success

    if status["authenticated"]:
        status["message"] = "二次验证成功，本地持久化 session 已可复用。"
    elif success:
        status["message"] = "验证码已提交，但当前会话还未完全受信任，请稍后再试。"
    else:
        status["message"] = "验证码校验失败，请重新输入。"
    return status


def switch_icloud_account(profile_key_value: str) -> Dict[str, Any]:
    record = get_profile_record(profile_key_value)
    if not record:
        raise ValueError("找不到要切换的账号")

    apple_id = normalize_apple_id(record["appleId"])
    region = normalize_region(record["region"])
    save_active_profile(apple_id, region)

    service = load_persisted_authenticated_service(apple_id, region)
    if service is not None:
        set_runtime_service(service, apple_id, region)
        export_service_cookies(service, apple_id, region)
        upsert_profile_record(
            apple_id,
            region,
            service=service,
            updates={
                "lastUsedAt": now_iso(),
                "lastKnownAuthenticated": True,
                "lastKnownTrusted": True,
            },
        )
        status = serialize_auth_status(service, apple_id=apple_id, region=region)
        status["message"] = "已切换到已保存账号，无需重新登录。"
    else:
        clear_runtime_service()
        copy_to_active_exports(apple_id, region)
        upsert_profile_record(
            apple_id,
            region,
            updates={"lastUsedAt": now_iso(), "lastKnownAuthenticated": False, "lastKnownTrusted": False},
        )
        status = serialize_auth_status(None, apple_id=apple_id, region=region)
        status["message"] = "已切换账号，但本地 session 已失效，需要重新登录。"

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
    key = profile_key(apple_id, region)
    service = get_runtime_service(apple_id, region) or load_persisted_authenticated_service(apple_id, region)
    if service is not None:
        try:
            service.logout(clear_local_session=True)
        except Exception:
            session = getattr(service, "session", None)
            if session is not None and hasattr(session, "clear_persistence"):
                try:
                    session.clear_persistence(remove_files=True)
                except Exception:
                    pass

    for path in [
        account_cookie_snapshot_path(apple_id, region),
        account_list_json_path(apple_id, region),
        account_list_text_path(apple_id, region),
    ]:
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    remove_profile_record(key)
    clear_runtime_service()

    remaining = list_saved_accounts()
    if remaining:
        next_record = remaining[0]
        save_active_profile(next_record["appleId"], next_record["region"])
        status = switch_icloud_account(next_record["profileKey"])
        return {
            "ok": True,
            "message": "当前账号本地会话已清除，并已切换到下一个已保存账号。",
            "status": status,
        }

    clear_active_profile()
    for path in (COOKIES_FILE, EMAILS_FILE):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    return {
        "ok": True,
        "message": "当前账号本地持久化登录状态已清除。",
        "status": serialize_auth_status(None),
    }


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
        reason = error.get("errorMessage") or error.get("reason") or error.get("errorCode") or "Unknown error"
        return False, str(reason)

    if isinstance(data.get("message"), str):
        return False, data["message"]

    return False, f"HTTP {response.status_code}: 请求失败"


def normalize_hme_item(item: Dict[str, Any]) -> Dict[str, Any]:
    email = item.get("hme") if item.get("hme") is not None else item.get("email")
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


def fetch_hme_list_from_service(service: Any, apple_id: str, region: str) -> List[Dict[str, Any]]:
    try:
        endpoint = service.hidemyemail._list_endpoint
        response = service.session.get(endpoint, params=service.params, timeout=DEFAULT_TIMEOUT)
        payload = response.json()
        emails = payload.get("result", {}).get("hmeEmails")
        if not isinstance(emails, list):
            raise RuntimeError("Hide My Email 返回数据格式异常")
        items = [normalize_hme_item(item) for item in emails]
        export_service_cookies(service, apple_id, region)
        save_account_list_cache(apple_id, region, items)
        return items
    except Exception as exc:
        raise RuntimeError(f"请求列表失败: {exc}") from exc


def fetch_hme_list(cookies: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    if cookies is None:
        profile = load_active_profile()
        service = get_active_authenticated_service()
        if service is not None and profile is not None:
            return fetch_hme_list_from_service(service, profile["appleId"], profile["region"])
        cookies = load_cookies()
    return fetch_hme_list_from_cookies(cookies)


def fetch_hme_list_with_source(cookies: Optional[Dict[str, str]] = None) -> Tuple[List[Dict[str, Any]], str]:
    if cookies is None:
        profile = load_active_profile()
        service = get_active_authenticated_service()
        if service is not None and profile is not None:
            return fetch_hme_list_from_service(service, profile["appleId"], profile["region"]), "session"
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


def deactivate_hme_with_service(service: Any, apple_id: str, region: str, anon_id: str) -> Tuple[bool, str]:
    try:
        response = service.session.post(
            service.hidemyemail._deactivate_endpoint,
            params=service.params,
            json={"anonymousId": anon_id},
            timeout=DEFAULT_TIMEOUT,
        )
        ok, message = parse_response(response)
        if ok:
            export_service_cookies(service, apple_id, region)
        return ok, message
    except Exception as exc:
        return False, f"停用失败: {exc}"


def deactivate_hme(cookies: Optional[Dict[str, str]], anon_id: str) -> Tuple[bool, str]:
    if cookies is None:
        profile = load_active_profile()
        service = get_active_authenticated_service()
        if service is not None and profile is not None:
            return deactivate_hme_with_service(service, profile["appleId"], profile["region"], anon_id)
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


def delete_hme_with_service(service: Any, apple_id: str, region: str, anon_id: str) -> Tuple[bool, str]:
    try:
        response = service.session.post(
            service.hidemyemail._delete_endpoint,
            params=service.params,
            json={"anonymousId": anon_id},
            timeout=DEFAULT_TIMEOUT,
        )
        ok, message = parse_response(response)
        if ok:
            export_service_cookies(service, apple_id, region)
        return ok, message
    except Exception as exc:
        return False, f"删除失败: {exc}"


def delete_hme(cookies: Optional[Dict[str, str]], anon_id: str) -> Tuple[bool, str]:
    if cookies is None:
        profile = load_active_profile()
        service = get_active_authenticated_service()
        if service is not None and profile is not None:
            return delete_hme_with_service(service, profile["appleId"], profile["region"], anon_id)
        cookies = load_cookies()
    return delete_hme_with_cookies(cookies, anon_id)
