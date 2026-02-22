from __future__ import annotations

import asyncio
import ipaddress
import json
import time
import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response

from antibot_shield.challenge import (
    challenge_html,
    check_pow,
    evaluate_client_signals,
    fingerprint_hash_from_payload,
    get_challenge_css,
    get_challenge_js,
    get_i18n_json,
    make_nonce,
    sign_js_token,
    verify_js_token,
)
from antibot_shield.config import ShieldSettings
from antibot_shield.engine import ShieldEngine
from antibot_shield.models import RequestContext
from antibot_shield.storage.factory import build_storage


class AntiBotShieldMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: ShieldSettings | None = None):
        super().__init__(app)
        self.settings = settings or ShieldSettings()
        self.storage = build_storage(self.settings)
        self.engine = ShieldEngine()

    def _is_browser_path(self, path: str) -> bool:
        for prefix in self.settings.browser_path_prefixes:
            if path.startswith(prefix):
                return True
        return False

    def _is_challenge_eligible(self, path: str) -> bool:
        for prefix in self.settings.js_challenge_paths:
            if path.startswith(prefix):
                return True
        return False

    def _client_ip(self, request: Request) -> str:
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.split(",")[0].strip()

        xff = request.headers.get("x-forwarded-for", "")
        if xff:
            return xff.split(",")[0].strip()

        if request.client and request.client.host:
            return request.client.host
        return "unknown"

    async def _record_response_status(self, client_id: str, status_code: int) -> None:
        key = f"abs:resp404:{client_id}:300"
        value = "404" if status_code == 404 else "ok"
        await self.storage.lpush_trim(key, value, max_len=600, ttl_sec=300)

    def _has_html_accept(self, request: Request) -> bool:
        accept = request.headers.get("accept", "")
        return "text/html" in accept or "application/xhtml+xml" in accept

    def _get_js_cookie(self, request: Request) -> str:
        return request.cookies.get(self.settings.js_cookie_name, "")

    def _cookie_is_valid(self, request: Request, client_id: str) -> bool:
        token = self._get_js_cookie(request)
        if not token:
            return False
        return verify_js_token(
            token=token,
            client_id=client_id,
            user_agent=request.headers.get("user-agent", ""),
            secret=self.settings.challenge_secret,
        )

    def _subnet_prefix(self, client_ip: str) -> str:
        try:
            ip_obj = ipaddress.ip_address(client_ip)
        except Exception:
            return ""
        if ip_obj.version == 4:
            parts = str(ip_obj).split(".")
            if len(parts) == 4:
                return ".".join(parts[:3]) + ".0/24"
            return ""
        network = ipaddress.ip_network(f"{ip_obj}/64", strict=False)
        return str(network)

    async def _mark_ban_and_maybe_subnet(self, client_id: str, ttl_sec: int) -> None:
        await self.storage.set(f"abs:ban:{client_id}", "1", ttl_sec=ttl_sec)
        if not self.settings.subnet_ban_enabled:
            return
        prefix = self._subnet_prefix(client_id)
        if not prefix:
            return
        hit_key = f"abs:banhit:subnet:{prefix}:{self.settings.subnet_ban_window_sec}"
        hits = await self.storage.incr(hit_key, ttl_sec=self.settings.subnet_ban_window_sec)
        if hits >= self.settings.subnet_ban_trigger:
            await self.storage.set(f"abs:ban:net:{prefix}", "1", ttl_sec=self.settings.subnet_ban_seconds)

    async def _verify_failure_response(
        self,
        client_id: str,
        request_id: str,
        error: str,
        status_code: int = 400,
        extra: dict[str, object] | None = None,
    ) -> Response:
        fail_key = f"abs:verify:fail:{client_id}:600"
        fails = await self.storage.incr(fail_key, ttl_sec=600)
        payload: dict[str, object] = {"error": error, "request_id": request_id, "verify_failures": fails}
        if extra:
            payload.update(extra)

        if fails >= self.settings.verify_fail_long_ban_threshold:
            await self._mark_ban_and_maybe_subnet(client_id, ttl_sec=self.settings.verify_fail_long_ban_sec)
            return JSONResponse(status_code=403, content={**payload, "error": "blocked_long"}, headers={"X-Request-ID": request_id})

        if fails >= self.settings.verify_fail_short_ban_threshold:
            await self._mark_ban_and_maybe_subnet(client_id, ttl_sec=self.settings.verify_fail_short_ban_sec)
            return JSONResponse(status_code=403, content={**payload, "error": "blocked_short"}, headers={"X-Request-ID": request_id})

        if fails >= self.settings.verify_fail_delay_start:
            delay_ms = min(2000, int(self.settings.slow_delay_ms * (fails - self.settings.verify_fail_delay_start + 1)))
            await asyncio.sleep(delay_ms / 1000.0)
            payload["penalty_delay_ms"] = delay_ms

        return JSONResponse(status_code=status_code, content=payload, headers={"X-Request-ID": request_id})

    async def _issue_challenge_response(
        self,
        request: Request,
        client_id: str,
        request_id: str,
        score: int = 0,
        tags: list[str] | None = None,
    ) -> Response:
        nonce = make_nonce()
        nonce_key = f"abs:jsnonce:{client_id}:{nonce}"
        nonce_meta = json.dumps({"iat": int(time.time()), "rid": request_id})
        ttl_sec = max(10, int(self.settings.js_nonce_verify_window_sec or (self.settings.challenge_retry_after_sec + 20)))
        await self.storage.set(nonce_key, nonce_meta, ttl_sec=ttl_sec)
        return HTMLResponse(
            status_code=429,
            content=challenge_html(request, self.settings, nonce=nonce, score=score, tags=tags or [], request_id=request_id),
            headers={"Retry-After": str(self.settings.challenge_retry_after_sec), "X-Request-ID": request_id},
        )

    async def _handle_verify(self, request: Request, client_id: str, request_id: str) -> Response:
        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(status_code=400, content={"error": "invalid_json", "request_id": request_id}, headers={"X-Request-ID": request_id})

        nonce = str(payload.get("nonce", ""))
        fp_hash = str(payload.get("fp_hash", ""))
        fp_raw = str(payload.get("fp_raw", ""))
        next_url = str(payload.get("next", "/"))
        signals = payload.get("signals", {})
        payload_request_id = str(payload.get("request_id", ""))
        try:
            payload_pow_rounds = int(payload.get("pow_rounds", 0))
        except Exception:
            payload_pow_rounds = 0
        try:
            payload_pow_elapsed_ms = int(payload.get("pow_elapsed_ms", -1))
        except Exception:
            payload_pow_elapsed_ms = -1
        counters: list[int] = []
        raw_counters = payload.get("counters")
        if isinstance(raw_counters, list):
            for item in raw_counters:
                try:
                    c = int(item)
                except Exception:
                    c = -1
                if c < 0:
                    counters = []
                    break
                counters.append(c)
        elif "counter" in payload:
            try:
                c = int(payload.get("counter", -1))
            except Exception:
                c = -1
            if c >= 0:
                counters = [c]

        if fp_hash:
            fp_key = f"abs:verify:fp:{fp_hash}:60"
            fp_rate = await self.storage.incr(fp_key, ttl_sec=60)
            if fp_rate > self.settings.js_fp_hash_requests_per_min:
                return await self._verify_failure_response(
                    client_id=client_id,
                    request_id=request_id,
                    error="fp_hash_rate_limited",
                    status_code=429,
                    extra={"retry_after_sec": 60},
                )

        if payload_request_id:
            reqid_key = f"abs:verify:reqid:{payload_request_id}:60"
            reqid_rate = await self.storage.incr(reqid_key, ttl_sec=60)
            if reqid_rate > self.settings.js_request_id_requests_per_min:
                return await self._verify_failure_response(
                    client_id=client_id,
                    request_id=request_id,
                    error="request_id_rate_limited",
                    status_code=429,
                    extra={"retry_after_sec": 60},
                )

        required_rounds = max(1, int(self.settings.js_pow_rounds or 1))
        if (
            not nonce
            or not fp_hash
            or len(counters) != required_rounds
            or payload_pow_rounds != required_rounds
            or payload_pow_elapsed_ms < self.settings.js_verify_min_pow_elapsed_ms
            or payload_pow_elapsed_ms > self.settings.js_verify_max_pow_elapsed_ms
        ):
            return await self._verify_failure_response(
                client_id=client_id,
                request_id=request_id,
                error="invalid_payload",
                status_code=400,
            )

        nonce_key = f"abs:jsnonce:{client_id}:{nonce}"
        nonce_raw = await self.storage.get(nonce_key)
        if not nonce_raw:
            return await self._verify_failure_response(client_id=client_id, request_id=request_id, error="nonce_expired", status_code=400)

        try:
            nonce_meta = json.loads(nonce_raw)
        except Exception:
            nonce_meta = {}

        now_ts = int(time.time())
        nonce_iat = int(nonce_meta.get("iat", now_ts))
        nonce_rid = str(nonce_meta.get("rid", ""))
        nonce_age = now_ts - nonce_iat
        if nonce_age < 0 or nonce_age > int(self.settings.js_nonce_verify_window_sec):
            await self.storage.delete(nonce_key)
            return await self._verify_failure_response(client_id=client_id, request_id=request_id, error="nonce_expired", status_code=400)
        if nonce_rid and payload_request_id and nonce_rid != payload_request_id:
            return await self._verify_failure_response(client_id=client_id, request_id=request_id, error="request_id_mismatch", status_code=400)

        nonce_attempts_key = f"abs:jsnonce_attempts:{client_id}:{nonce}"
        nonce_attempts = await self.storage.incr(nonce_attempts_key, ttl_sec=self.settings.js_nonce_verify_window_sec)
        if nonce_attempts > self.settings.js_nonce_max_verify_attempts:
            await self.storage.delete(nonce_key)
            return await self._verify_failure_response(client_id=client_id, request_id=request_id, error="nonce_attempts_exceeded", status_code=429)

        for round_idx, counter in enumerate(counters):
            if not check_pow(
                nonce=nonce,
                fp_hash=fp_hash,
                counter=counter,
                difficulty=self.settings.js_challenge_difficulty,
                round_idx=round_idx,
            ):
                return await self._verify_failure_response(client_id=client_id, request_id=request_id, error="pow_failed", status_code=400)

        if fp_raw:
            calc_fp_hash = fingerprint_hash_from_payload(fp_raw)
            if calc_fp_hash != fp_hash:
                return await self._verify_failure_response(client_id=client_id, request_id=request_id, error="fingerprint_mismatch", status_code=400)

        signal_risk, signal_tags = evaluate_client_signals(signals if isinstance(signals, dict) else {})
        if signal_risk >= 70:
            return await self._verify_failure_response(
                client_id=client_id,
                request_id=request_id,
                error="automation_detected",
                status_code=403,
                extra={"tags": signal_tags},
            )

        await self.storage.delete(nonce_key)
        await self.storage.delete(f"abs:verify:fail:{client_id}:600")

        token = sign_js_token(
            client_id=client_id,
            user_agent=request.headers.get("user-agent", ""),
            ttl_sec=self.settings.js_cookie_ttl_sec,
            secret=self.settings.challenge_secret,
        )

        response = JSONResponse(
            status_code=200,
            content={"status": "ok", "next": next_url, "request_id": request_id, "signal_risk": signal_risk},
            headers={"X-Request-ID": request_id},
        )
        response.set_cookie(
            self.settings.js_cookie_name,
            token,
            max_age=self.settings.js_cookie_ttl_sec,
            httponly=True,
            secure=self.settings.js_cookie_secure,
            samesite="lax",
            path="/",
        )
        return response

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("x-request-id", "") or str(uuid.uuid4())

        if not self.settings.enabled:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response

        ip = self._client_ip(request)
        client_id = ip
        path = request.url.path

        if path == "/_abs/static/challenge.css":
            return Response(
                content=get_challenge_css(self.settings),
                media_type="text/css",
                headers={"X-Request-ID": request_id, "Cache-Control": "public, max-age=300"},
            )

        if path == "/_abs/static/challenge.js":
            return Response(
                content=get_challenge_js(self.settings),
                media_type="application/javascript",
                headers={"X-Request-ID": request_id, "Cache-Control": "public, max-age=300"},
            )

        if path.startswith("/_abs/i18n/") and path.endswith(".json"):
            locale = path[len("/_abs/i18n/") : -len(".json")]
            return Response(
                content=get_i18n_json(locale),
                media_type="application/json",
                headers={"X-Request-ID": request_id, "Cache-Control": "public, max-age=300"},
            )

        if path == "/_abs/verify":
            return await self._handle_verify(request, client_id, request_id)

        if ip in self.settings.trusted_ips:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response

        ban_key = f"abs:ban:{client_id}"
        subnet_key = ""
        prefix = self._subnet_prefix(client_id)
        if prefix:
            subnet_key = f"abs:ban:net:{prefix}"

        banned = await self.storage.get(ban_key)
        subnet_banned = await self.storage.get(subnet_key) if subnet_key else None
        if banned or subnet_banned:
            return JSONResponse(
                status_code=403,
                content={
                    "error": "blocked",
                    "message": "Temporary blocked by anti-bot policy",
                    "retry_after_sec": self.settings.subnet_ban_seconds if subnet_banned else self.settings.ban_seconds,
                    "scope": "subnet" if subnet_banned else "ip",
                    "request_id": request_id,
                },
                headers={"X-Request-ID": request_id},
            )

        force_js_challenge = (
            self.settings.js_always_challenge_browser_paths
            and self._has_html_accept(request)
            and self._is_challenge_eligible(path)
            and not self._cookie_is_valid(request, client_id)
        )
        if force_js_challenge:
            return await self._issue_challenge_response(
                request=request,
                client_id=client_id,
                request_id=request_id,
                score=0,
                tags=["js_challenge_forced"],
            )

        ctx = RequestContext(
            client_ip=ip,
            client_id=client_id,
            method=request.method,
            path=path,
            user_agent=request.headers.get("user-agent", ""),
            headers={k.lower(): v for k, v in request.headers.items()},
            is_browser_path=self._is_browser_path(path),
        )

        score, hard, tags, meta = await self.engine.evaluate(ctx, self.storage, self.settings)

        if self._cookie_is_valid(request, client_id):
            score = max(0, score - self.settings.js_score_discount)
            tags.append("js_verified")

        if hard or score >= self.settings.block_threshold:
            strike_key = f"abs:strike:{client_id}"
            strikes = await self.storage.incr(strike_key, ttl_sec=self.settings.strike_window_sec)
            if strikes >= self.settings.strike_limit or hard:
                await self._mark_ban_and_maybe_subnet(client_id, ttl_sec=self.settings.ban_seconds)

            return JSONResponse(
                status_code=403,
                content={
                    "error": "blocked",
                    "score": score,
                    "tags": tags,
                    "meta": meta,
                    "request_id": request_id,
                },
                headers={"X-Request-ID": request_id},
            )

        if score >= self.settings.challenge_threshold:
            if self._has_html_accept(request) and self._is_challenge_eligible(path):
                return await self._issue_challenge_response(
                    request=request,
                    client_id=client_id,
                    request_id=request_id,
                    score=score,
                    tags=tags,
                )

            return JSONResponse(
                status_code=429,
                content={
                    "error": "challenge_required",
                    "message": "Suspicious traffic pattern. Slow down and retry.",
                    "score": score,
                    "tags": tags,
                    "retry_after_sec": self.settings.challenge_retry_after_sec,
                    "request_id": request_id,
                },
                headers={"Retry-After": str(self.settings.challenge_retry_after_sec), "X-Request-ID": request_id},
            )

        if score >= self.settings.slow_threshold:
            await asyncio.sleep(self.settings.slow_delay_ms / 1000.0)

        response = await call_next(request)
        await self._record_response_status(client_id, response.status_code)
        response.headers["X-AntiBot-Score"] = str(score)
        response.headers["X-Request-ID"] = request_id
        if tags:
            response.headers["X-AntiBot-Tags"] = ",".join(sorted(set(tags))[:8])
        return response
