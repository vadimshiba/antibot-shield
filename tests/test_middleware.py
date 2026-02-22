import hashlib
import re

from fastapi import FastAPI
from fastapi.testclient import TestClient

from antibot_shield import AntiBotShieldMiddleware, ShieldSettings


def build_app() -> FastAPI:
    app = FastAPI()
    settings = ShieldSettings(requests_per_minute=5, burst_requests=3, burst_window_sec=2)
    app.add_middleware(AntiBotShieldMiddleware, settings=settings)

    @app.get("/ping")
    def ping() -> dict:
        return {"ok": True}

    return app


def test_burst_limit_eventually_blocks_or_challenges() -> None:
    app = build_app()
    client = TestClient(app)
    statuses = []
    for _ in range(10):
        resp = client.get("/ping", headers={"user-agent": "Mozilla/5.0", "accept": "text/html", "accept-language": "en-US"})
        statuses.append(resp.status_code)

    assert any(code in (403, 429) for code in statuses)


def _solve_pow(nonce: str, fp_hash: str, difficulty: int, round_idx: int = 0) -> int:
    prefix = "0" * difficulty
    counter = 0
    while counter < 200000:
        digest = hashlib.sha256(f"{nonce}:{round_idx}:{fp_hash}:{counter}".encode("utf-8")).hexdigest()
        if digest.startswith(prefix):
            return counter
        counter += 1
    raise AssertionError("pow_not_found")


def test_js_challenge_verify_sets_cookie_and_unblocks() -> None:
    app = FastAPI()
    settings = ShieldSettings(
        challenge_threshold=10,
        block_threshold=95,
        js_challenge_difficulty=1,
        js_pow_rounds=1,
        js_score_discount=100,
        challenge_secret="test-secret",
    )
    app.add_middleware(AntiBotShieldMiddleware, settings=settings)

    @app.get("/")
    def root() -> dict:
        return {"ok": True}

    client = TestClient(app)
    first = client.get("/", headers={"accept": "text/html"})
    assert first.status_code == 429
    assert "One moment while we secure your access" in first.text

    m = re.search(r'"nonce"\s*:\s*"([^"]+)"', first.text)
    assert m
    nonce = m.group(1)
    signals = {
        "timezone": "UTC",
        "language": "en-US",
        "languages": ["en-US", "en"],
        "hardware_concurrency": 8,
        "device_memory": 8,
        "platform": "Linux x86_64",
        "ua": "Mozilla/5.0 Test Browser",
        "webdriver": False,
        "plugins_count": 3,
        "max_touch_points": 0,
        "has_chrome_object": True,
        "has_webcrypto": True,
        "screen": "1920x1080x24",
        "canvas_hash": "a" * 64,
        "webgl_hash": "b" * 64,
        "audio_hash": "c" * 64,
        "event_loop_jitter_ms": 0.5,
        "permission_notifications": "granted",
        "automation_artifacts": 0,
    }
    import json
    fp_raw = json.dumps(signals)
    fp_hash = hashlib.sha256(fp_raw.encode("utf-8")).hexdigest()
    counter = _solve_pow(nonce=nonce, fp_hash=fp_hash, difficulty=1, round_idx=0)
    verify_req_id = first.headers.get("x-request-id", "")

    verify = client.post(
        "/_abs/verify",
        json={
            "nonce": nonce,
            "counters": [counter],
            "fp_hash": fp_hash,
            "fp_raw": fp_raw,
            "signals": signals,
            "next": "/",
            "pow_rounds": 1,
            "pow_elapsed_ms": 500,
            "request_id": verify_req_id,
        },
    )
    assert verify.status_code == 200

    second = client.get("/", headers={"accept": "text/html"})
    assert second.status_code == 200
