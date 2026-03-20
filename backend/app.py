import json
import re
import logging
import time
import urllib.parse
from contextlib import asynccontextmanager
from pathlib import Path

import requests as http_requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel

logger = logging.getLogger("rollcall")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
CONFIG_DIR = PROJECT_ROOT / "config"

DEFAULT_CONFIG = {
    "jaccount": "",
    "password": "",
    "service_port": 5000,
    "host": "0.0.0.0",
    "sign_domain": "https://mlearning.sjtu.edu.cn",
    "qr_url_prefix": "https://mlearning.sjtu.edu.cn/lms/mobile2/forscan/",
}


def _write_default_config(config_path: Path) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=4) + "\n",
        encoding="utf-8",
    )


def load_config() -> dict:
    config_path = CONFIG_DIR / "default_config.json"
    if not config_path.exists():
        _write_default_config(config_path)
        logger.warning(
            "未找到配置文件，已自动生成 %s。请先填写 jaccount 和 password 后再使用签到功能。",
            config_path,
        )
        return DEFAULT_CONFIG.copy()

    try:
        loaded = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _write_default_config(config_path)
        logger.warning(
            "配置文件损坏或不可读，已重置为默认配置：%s。请重新填写 jaccount 和 password。",
            config_path,
        )
        return DEFAULT_CONFIG.copy()

    merged = DEFAULT_CONFIG.copy()
    if isinstance(loaded, dict):
        merged.update(loaded)
    return merged


class SignRequest(BaseModel):
    qr_url: str


def _extract_message_from_payload(payload):
    if isinstance(payload, dict):
        for key in ("message", "msg", "error", "detail"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    if isinstance(payload, str):
        return payload.strip()
    return ""


def _contains_expired_hint(text: str) -> bool:
    lowered = (text or "").lower()
    hints = ("过期", "已结束", "已截止", "失效", "不存在", "expired", "closed")
    return any(hint in lowered for hint in hints)


def _do_sign(qr_url: str, username: str, password: str) -> dict:
    """执行完整的 jAccount 登录 + 签到流程。

    Args:
        qr_url:   扫描到的签到二维码链接
        username: jAccount 账号
        password: jAccount 密码

    Returns:
        包含 success 和 message 字段的结果字典
    """
    if not username or not password:
        return {"success": False, "message": "未配置 jAccount 账号或密码"}

    session = http_requests.Session()
    session.trust_env = False
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Connection": "keep-alive",
    })

    # 步骤 1：访问签到链接，触发重定向到 jAccount 登录页
    try:
        login_page_resp = session.get(qr_url, timeout=15)
    except http_requests.RequestException as e:
        return {"success": False, "message": f"访问签到链接失败: {e}"}

    parsed_url = urlparse(login_page_resp.url)
    params = parse_qs(parsed_url.query)

    sid = params.get("sid", [""])[0]
    client = params.get("client", [""])[0]
    returl = params.get("returl", [""])[0]
    se = params.get("se", [""])[0]

    soup = BeautifulSoup(login_page_resp.text, "html.parser")

    uuid_match = re.search(r"uuid=([a-zA-Z0-9\-]+)", login_page_resp.text)
    if not uuid_match:
        return {"success": False, "message": "未能从登录页提取 UUID"}
    uuid = uuid_match.group(1)

    lt_tag = soup.find("input", {"name": "lt"})
    lt = lt_tag["value"] if lt_tag else "p"

    v_tag = soup.find("input", {"name": "v"})
    v = v_tag["value"] if v_tag else ""

    # 步骤 2：获取并识别验证码
    captcha_url = f"https://jaccount.sjtu.edu.cn/jaccount/captcha?uuid={uuid}"
    session.headers.update({"Referer": login_page_resp.url})

    def _fetch_captcha_image():
        target_url = captcha_url
        session.get(target_url, timeout=10)
        return session.get(target_url, timeout=10)

    try:
        captcha_resp = _fetch_captcha_image()
    except http_requests.RequestException as e:
        return {"success": False, "message": f"获取验证码失败: {e}"}

    session.headers.update({
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://jaccount.sjtu.edu.cn",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    })

    result = None
    max_captcha_retry = 3
    for attempt in range(1, max_captcha_retry + 1):
        try:
            import ddddocr
            ocr = ddddocr.DdddOcr(show_ad=False)
            raw_captcha = ocr.classification(captcha_resp.content)
            captcha_text = raw_captcha.strip().lower()
        except Exception as e:
            return {"success": False, "message": f"验证码识别失败: {e}"}

        logger.info("验证码识别结果(第 %d 次): %s", attempt, captcha_text)

        payload = {
            "sid": sid,
            "client": client,
            "returl": returl,
            "se": se,
            "v": v,
            "uuid": uuid,
            "user": username,
            "pass": password,
            "captcha": captcha_text,
            "lt": lt,
        }

        try:
            time.sleep(1)
            login_resp = session.post(
                "https://jaccount.sjtu.edu.cn/jaccount/ulogin",
                data=payload,
                timeout=15,
            )
        except http_requests.RequestException as e:
            return {"success": False, "message": f"登录请求失败: {e}"}

        try:
            result = login_resp.json()
        except json.JSONDecodeError:
            return {"success": False, "message": "登录响应解析失败"}

        errno = result.get("errno")
        error = result.get("error")
        code = result.get("code")
        wrong_captcha = error == "Wrong captcha" or code == "WRONG_CAPTCHA"
        if not wrong_captcha:
            break

        if attempt >= max_captcha_retry:
            return {"success": False, "message": "验证码识别错误，3 次重试后仍失败"}

        try:
            captcha_resp = _fetch_captcha_image()
        except http_requests.RequestException as e:
            return {"success": False, "message": f"刷新验证码失败: {e}"}

    if not isinstance(result, dict):
        return {"success": False, "message": "登录响应异常"}

    errno = result.get("errno")
    code = result.get("code")
    if errno != 0 and code != "SUCCESS":
        return {"success": False, "message": f"登录被拒绝: {result}"}

    # 步骤 4：跟随重定向，获取 JWT Token
    redirect_url = result.get("url", "")
    if redirect_url and not redirect_url.startswith("http"):
        redirect_url = "https://jaccount.sjtu.edu.cn" + redirect_url

    if redirect_url:
        try:
            session.get(redirect_url, timeout=15)
        except http_requests.RequestException:
            pass

    jwt_token = ""
    for cookie in session.cookies:
        if cookie.name == "token":
            jwt_token = urllib.parse.unquote(cookie.value).strip('"')
            break

    if not jwt_token:
        return {"success": False, "message": "未能获取登录令牌"}

    # 步骤 5：调用签到 API
    parsed_qr = urlparse(qr_url)
    qr_params = parse_qs(parsed_qr.query)
    roll_call_token = qr_params.get("rollCallToken", [""])[0]
    sign_history_id = qr_params.get("signHistoryId", [""])[0]

    if not roll_call_token or not sign_history_id:
        return {"success": False, "message": "二维码缺少必要参数 (rollCallToken / signHistoryId)"}

    sign_api_url = (
        f"https://mlearning.sjtu.edu.cn"
        f"/lms-lti-rollcall-sjtu/sign/scan/{roll_call_token}/{sign_history_id}"
    )

    session.headers.clear()
    session.headers.update({
        "Authorization": jwt_token,
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": "https://mlearning.sjtu.edu.cn/lms/mobile/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    })
    session.cookies.set("token", jwt_token, domain="mlearning.sjtu.edu.cn")

    try:
        sign_resp = session.get(sign_api_url, timeout=15)
    except http_requests.RequestException as e:
        return {"success": False, "message": f"签到请求失败: {e}"}

    resp_text = sign_resp.text
    logger.info("签到响应 [%d]: %s", sign_resp.status_code, resp_text[:200])

    payload_message = ""
    try:
        sign_payload = sign_resp.json()
        payload_message = _extract_message_from_payload(sign_payload)
    except ValueError:
        sign_payload = None

    if "操作成功" in resp_text or '"200"' in resp_text:
        return {"success": True, "message": "签到成功"}

    if _contains_expired_hint(payload_message) or _contains_expired_hint(resp_text):
        if payload_message:
            return {"success": False, "message": f"二维码已过期: {payload_message}"}
        return {"success": False, "message": "二维码已过期"}

    if payload_message:
        return {"success": False, "message": f"签到未成功: {payload_message}"}

    return {"success": False, "message": f"签到未成功: {resp_text[:200]}"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = load_config()
    app.state.config = config
    logger.info("Rollcall service started on port %s", config.get("service_port"))
    yield
    logger.info("Rollcall service stopped")


app = FastAPI(title="SJTU Rollcall", lifespan=lifespan)


def _is_mobile_request(request: Request) -> bool:
    ua = request.headers.get("user-agent", "").lower()
    ch_platform = request.headers.get("sec-ch-ua-platform", "").strip('"').lower()
    ch_mobile = request.headers.get("sec-ch-ua-mobile", "").lower()

    has_mobile_hint = any(token in ua for token in ("android", "iphone", "ipad", "ipod", "mobile"))
    if not has_mobile_hint:
        return False

    desktop_ua_tokens = (
        "windows nt",
        "macintosh",
        "x11",
        "cros",
        "ubuntu",
        "fedora",
        "debian",
        "linux x86_64",
    )
    if any(token in ua for token in desktop_ua_tokens):
        return False

    if ch_platform in {"windows", "macos", "linux", "chrome os"}:
        return False

    is_ipad = "ipad" in ua
    if ch_mobile and ch_mobile != "?1" and not is_ipad:
        return False

    return True


def _mobile_only_block_response() -> HTMLResponse:
    return HTMLResponse(
        status_code=403,
        content=(
            "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<title>访问受限</title></head><body style='margin:0;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Arial,sans-serif;background:#f3f2f1;color:#323130;'>"
            "<div style='max-width:520px;margin:16vh auto;padding:24px;background:#fff;border:1px solid #edebe9;border-radius:8px;'>"
            "<h2 style='margin:0 0 12px;font-size:20px;'>仅支持手机端访问</h2>"
            "<p style='margin:0;line-height:1.7;'>检测到不受支持的设备环境，已拒绝访问。"
            "请使用手机浏览器打开本网站。</p></div></body></html>"
        ),
    )


@app.middleware("http")
async def mobile_only_guard(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)

    if not _is_mobile_request(request):
        return _mobile_only_block_response()

    return await call_next(request)


def _is_within_directory(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def _is_valid_qr_url(qr_url: str, expected_host: str, expected_path_prefix: str) -> bool:
    parsed = urlparse(qr_url)
    if parsed.scheme.lower() != "https":
        return False

    host = (parsed.hostname or "").lower()
    if host != expected_host.lower():
        return False

    return parsed.path.startswith(expected_path_prefix)


@app.post("/api/sign")
async def sign_endpoint(req: SignRequest):
    """接收前端扫描到的二维码链接，执行签到流程。"""
    config = app.state.config
    qr_url = req.qr_url.strip()

    expected_host = urlparse(config.get("sign_domain", "https://mlearning.sjtu.edu.cn")).hostname or ""
    expected_path_prefix = urlparse(config.get("qr_url_prefix", "https://mlearning.sjtu.edu.cn/lms/mobile2/forscan/")).path

    if not _is_valid_qr_url(qr_url, expected_host, expected_path_prefix):
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "无效的签到链接"},
        )

    import asyncio
    result = await asyncio.to_thread(
        _do_sign,
        qr_url,
        config.get("jaccount", ""),
        config.get("password", ""),
    )
    return result


@app.get("/api/status")
async def status_endpoint():
    """返回当前配置状态（是否已配置账号）。"""
    config = app.state.config
    configured = bool(config.get("jaccount")) and bool(config.get("password"))
    return {
        "configured": configured,
        "jaccount": config.get("jaccount", ""),
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    """前端 SPA 路由回退。"""
    frontend_resolved = FRONTEND_DIR.resolve()
    file_path = (FRONTEND_DIR / full_path).resolve()
    if not _is_within_directory(file_path, frontend_resolved):
        return JSONResponse(status_code=403, content={"detail": "Access denied"})
    if file_path.is_file():
        return FileResponse(str(file_path))
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"detail": "Frontend not found"}
