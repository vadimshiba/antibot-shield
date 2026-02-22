from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import secrets
import time
from functools import lru_cache
from pathlib import Path
import re
from urllib.parse import quote

from starlette.requests import Request

from antibot_shield.config import ShieldSettings


def _sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


@lru_cache(maxsize=8)
def _read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def get_challenge_template() -> str:
    path = Path(__file__).with_name("templates") / "challenge.html"
    return _read_text(str(path))


def _is_prod_asset_obfuscation_enabled(settings: ShieldSettings | None) -> bool:
    if settings is None:
        return False
    if not settings.js_obfuscate_assets_in_prod:
        return False
    return settings.runtime_env.strip().lower() in {"prod", "production"}


def _minify_css(css: str) -> str:
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    css = re.sub(r"\s+", " ", css)
    css = re.sub(r"\s*([{}:;,>])\s*", r"\1", css)
    css = css.replace(";}", "}")
    return css.strip()


@lru_cache(maxsize=4)
def _obfuscated_css(plain_css: str) -> str:
    compact = _minify_css(plain_css)
    encoded = base64.b64encode(compact.encode("utf-8")).decode("ascii")
    return f'@import url("data:text/css;base64,{encoded}");'


@lru_cache(maxsize=4)
def _obfuscated_js(plain_js: str) -> str:
    encoded = base64.b64encode(plain_js.encode("utf-8")).decode("ascii")
    seed = hashlib.sha256(plain_js.encode("utf-8")).hexdigest()
    chunk_size = 44 + (int(seed[:2], 16) % 12)
    chunks = [encoded[i : i + chunk_size] for i in range(0, len(encoded), chunk_size)]
    reversed_chunks = list(reversed(chunks))
    arr_name = f"_{seed[2:9]}"
    b64_name = f"_{seed[10:17]}"
    bin_name = f"_{seed[34:41]}"
    bytes_name = f"_{seed[42:49]}"
    i_name = f"_{seed[50:57]}"
    decoded_name = f"_{seed[58:65]}"
    script_name = f"_{seed[18:25]}"
    text_name = f"_{seed[26:33]}"
    chunks_literal = ",".join(json.dumps(part) for part in reversed_chunks)
    return (
        f"(function(){{const {arr_name}=[{chunks_literal}];"
        f"const {b64_name}={arr_name}.reverse().join('');"
        f"const {bin_name}=atob({b64_name});"
        f"const {bytes_name}=new Uint8Array({bin_name}.length);"
        f"for(let {i_name}=0;{i_name}<{bin_name}.length;{i_name}++){{{bytes_name}[{i_name}]={bin_name}.charCodeAt({i_name});}}"
        f"const {decoded_name}=typeof TextDecoder!=='undefined'"
        f"?new TextDecoder('utf-8').decode({bytes_name})"
        f":decodeURIComponent(escape({bin_name}));"
        f"const {script_name}=document.createElement('script');"
        f"const {text_name}=document.createTextNode({decoded_name});"
        f"{script_name}.appendChild({text_name});"
        f"(document.head||document.documentElement).appendChild({script_name});"
        f"{script_name}.remove();"
        f"}})();"
    )


def get_challenge_css(settings: ShieldSettings | None = None) -> str:
    path = Path(__file__).with_name("static") / "challenge.css"
    plain = _read_text(str(path))
    if _is_prod_asset_obfuscation_enabled(settings):
        return _obfuscated_css(plain)
    return plain


def get_challenge_js(settings: ShieldSettings | None = None) -> str:
    path = Path(__file__).with_name("static") / "challenge.js"
    plain = _read_text(str(path))
    if _is_prod_asset_obfuscation_enabled(settings):
        return _obfuscated_js(plain)
    return plain


def get_i18n_json(locale: str) -> str:
    safe = (locale or "").lower().strip()
    if not re.fullmatch(r"[a-z]{2}(-[a-z]{2})?", safe):
        safe = "en"

    base_dir = Path(__file__).with_name("i18n")
    full_path = base_dir / f"{safe}.json"
    if not full_path.exists() and "-" in safe:
        short = safe.split("-", 1)[0]
        full_path = base_dir / f"{short}.json"
    if not full_path.exists():
        full_path = base_dir / "en.json"

    return _read_text(str(full_path))


def make_nonce() -> str:
    return secrets.token_urlsafe(18)


def build_pow_payload(nonce: str, fp_hash: str, counter: int, round_idx: int = 0) -> str:
    return f"{nonce}:{round_idx}:{fp_hash}:{counter}"


def check_pow(nonce: str, fp_hash: str, counter: int, difficulty: int, round_idx: int = 0) -> bool:
    digest = _sha256_hex(build_pow_payload(nonce, fp_hash, counter, round_idx=round_idx))
    return digest.startswith("0" * difficulty)


def sign_js_token(client_id: str, user_agent: str, ttl_sec: int, secret: str) -> str:
    exp = int(time.time()) + ttl_sec
    ua_hash = _sha256_hex(user_agent)[:16]
    payload = f"{client_id}:{ua_hash}:{exp}"
    sig = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def verify_js_token(token: str, client_id: str, user_agent: str, secret: str) -> bool:
    try:
        token_client, token_ua_hash, token_exp, token_sig = token.split(":", 3)
        exp_int = int(token_exp)
    except Exception:
        return False

    if token_client != client_id:
        return False
    if exp_int < int(time.time()):
        return False

    ua_hash = _sha256_hex(user_agent)[:16]
    if ua_hash != token_ua_hash:
        return False

    payload = f"{token_client}:{token_ua_hash}:{token_exp}"
    expected = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, token_sig)


def fingerprint_hash_from_payload(fp_raw: str) -> str:
    return _sha256_hex(fp_raw)


def evaluate_client_signals(signals: dict[str, object]) -> tuple[int, list[str]]:
    score = 0
    tags: list[str] = []

    webdriver = bool(signals.get("webdriver", False))
    if webdriver:
        score += 65
        tags.append("js_webdriver")

    has_chrome = bool(signals.get("has_chrome_object", False))
    ua = str(signals.get("ua", "")).lower()
    if "chrome" in ua and not has_chrome:
        score += 8
        tags.append("js_chrome_object_missing")

    languages = signals.get("languages", [])
    if not isinstance(languages, list) or len(languages) == 0:
        score += 7
        tags.append("js_languages_missing")

    plugins_count = int(signals.get("plugins_count", 0) or 0)
    if plugins_count == 0:
        score += 10
        tags.append("js_plugins_empty")

    tz = str(signals.get("timezone", ""))
    if not tz:
        score += 6
        tags.append("js_timezone_missing")

    hc = int(signals.get("hardware_concurrency", 0) or 0)
    if hc <= 0:
        score += 6
        tags.append("js_hardware_concurrency_invalid")

    dm = float(signals.get("device_memory", 0) or 0)
    if dm and dm < 0.25:
        score += 5
        tags.append("js_device_memory_unusual")

    canvas_hash = str(signals.get("canvas_hash", ""))
    if len(canvas_hash) < 16:
        score += 15
        tags.append("js_canvas_missing")

    webgl_hash = str(signals.get("webgl_hash", ""))
    if len(webgl_hash) < 16:
        score += 12
        tags.append("js_webgl_missing")

    audio_hash = str(signals.get("audio_hash", ""))
    if len(audio_hash) < 16:
        score += 8
        tags.append("js_audio_missing")

    touch_points = int(signals.get("max_touch_points", 0) or 0)
    platform = str(signals.get("platform", "")).lower()
    if "iphone" in platform and touch_points == 0:
        score += 10
        tags.append("js_touch_inconsistent")

    has_webcrypto = bool(signals.get("has_webcrypto", False))
    if not has_webcrypto:
        score += 20
        tags.append("js_webcrypto_missing")

    perm_notifications = str(signals.get("permission_notifications", "unknown"))
    if perm_notifications == "denied":
        score += 3
        tags.append("js_perm_notifications_denied")

    artifacts = int(signals.get("automation_artifacts", 0) or 0)
    if artifacts >= 2:
        score += 40
        tags.append("js_automation_artifacts")

    jitter = float(signals.get("event_loop_jitter_ms", 0) or 0)
    if jitter < 0.05:
        score += 8
        tags.append("js_eventloop_too_stable")

    if "headless" in ua or "selenium" in ua or "playwright" in ua or "phantom" in ua:
        score += 55
        tags.append("js_ua_automation_marker")

    return score, tags


def challenge_html(
    request: Request,
    settings: ShieldSettings,
    nonce: str,
    score: int,
    tags: list[str],
    request_id: str,
) -> str:
    _ = score
    _ = tags
    next_url = request.url.path
    if request.url.query:
        next_url = f"{next_url}?{request.url.query}"
    safe_next = quote(next_url, safe="/%?=&-._~")

    accept_language = request.headers.get("accept-language", "")
    preferred_locale = "en"
    if accept_language:
        first = accept_language.split(",")[0].strip().lower()
        if re.fullmatch(r"[a-z]{2}(-[a-z]{2})?", first):
            preferred_locale = first

    config = {
        "nonce": nonce,
        "difficulty": settings.js_challenge_difficulty,
        "pow_rounds": settings.js_pow_rounds,
        "next_url": safe_next,
        "request_id": request_id,
        "verify_endpoint": "/_abs/verify",
        "preferred_locale": preferred_locale,
    }

    config_json = json.dumps(config).replace("</", "<\\/")

    template = get_challenge_template()
    rendered = template.replace("__ABS_REQUEST_ID__", html.escape(request_id))
    rendered = rendered.replace("__ABS_CONFIG_JSON__", config_json)
    return rendered
