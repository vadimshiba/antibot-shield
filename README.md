# antibot-shield

Adaptive L7 anti-bot middleware for FastAPI/Starlette services.

It adds scoring, JS challenge verification, progressive penalties, and temporary bans before requests reach your expensive endpoints.

[![CI](https://github.com/vadimshiba/antibot-shield/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/vadimshiba/antibot-shield/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Issues](https://img.shields.io/github/issues/vadimshiba/antibot-shield)](https://github.com/vadimshiba/antibot-shield/issues)

## Features

- Multi-signal request scoring:
  - rate limit
  - burst behavior
  - UA/header anomalies
  - scanner path probes
  - strict auth path checks
  - recent 404 behavior
  - anti-automation fingerprints
- Browser challenge flow with `/_abs/verify`:
  - signed `abs_js_ok` cookie
  - nonce-based one-time verify
  - multi-round PoW
  - fingerprint hash checks
  - locale-aware challenge UI (`/_abs/i18n/{locale}.json`)
- Progressive enforcement:
  - delay -> challenge (`429`) -> short ban -> long ban
- Verify hardening:
  - limits by `fp_hash`
  - limits by `request_id`
  - nonce age window + max attempts
  - anti-replay checks for `pow_rounds` and `pow_elapsed_ms`
- Optional subnet escalation bans:
  - IPv4 `/24`
  - IPv6 `/64`
- Production asset obfuscation for challenge JS/CSS while keeping editable source files.

## Quick Start

### 1. Install

```bash
cd /root/antibot-shield
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

### 2. Add middleware

```python
from fastapi import FastAPI
from antibot_shield import AntiBotShieldMiddleware, ShieldSettings

app = FastAPI()

settings = ShieldSettings(
    challenge_secret="replace-with-long-random-secret",
    js_cookie_secure=False,  # True behind HTTPS
)

app.add_middleware(AntiBotShieldMiddleware, settings=settings)
```

### 3. Run local demo

```bash
uvicorn tests.test_project.app:app --host 0.0.0.0 --port 8080 --reload
```

Open `http://localhost:8080/`.

## How it works

1. Request enters middleware.
2. Risk checks produce `score`, `tags`, optional hard block.
3. Middleware applies mitigation:
   - low score: allow
   - medium score: delay
   - high score: challenge (`429`)
   - critical score: block (`403`)
4. On challenge success, middleware sets signed `abs_js_ok` cookie and discounts future score.

`X-Request-ID` is returned in responses for tracing.

## Challenge Assets

- Template: `antibot_shield/templates/challenge.html`
- Styles: `antibot_shield/static/challenge.css`
- Logic: `antibot_shield/static/challenge.js`
- Dictionaries: `antibot_shield/i18n/*.json`

You edit these source files directly. In production, middleware can obfuscate delivered JS/CSS.

## Configuration (Env)

All settings use `ABS_` prefix.

### Core

- `ABS_ENABLED=true|false`
- `ABS_REDIS_URL=redis://localhost:6379/0`
- `ABS_RUNTIME_ENV=dev|prod`
- `ABS_CHALLENGE_SECRET=<long-random-secret>`

### Risk and mitigation

- `ABS_REQUESTS_PER_MINUTE=120`
- `ABS_BURST_REQUESTS=25`
- `ABS_BURST_WINDOW_SEC=5`
- `ABS_SLOW_THRESHOLD=30`
- `ABS_CHALLENGE_THRESHOLD=55`
- `ABS_BLOCK_THRESHOLD=80`
- `ABS_SLOW_DELAY_MS=250`
- `ABS_BAN_SECONDS=600`
- `ABS_STRIKE_LIMIT=5`
- `ABS_STRIKE_WINDOW_SEC=900`

### JS challenge

- `ABS_JS_ALWAYS_CHALLENGE_BROWSER_PATHS=true|false`
- `ABS_JS_CHALLENGE_PATHS='[\"/\",\"/app\",\"/web\",\"/ui\"]'`
- `ABS_JS_CHALLENGE_DIFFICULTY=4`
- `ABS_JS_POW_ROUNDS=4`
- `ABS_JS_COOKIE_NAME=abs_js_ok`
- `ABS_JS_COOKIE_TTL_SEC=3600`
- `ABS_JS_COOKIE_SECURE=true|false`
- `ABS_JS_OBFUSCATE_ASSETS_IN_PROD=true|false`

### Verify hardening

- `ABS_JS_NONCE_MAX_VERIFY_ATTEMPTS=4`
- `ABS_JS_NONCE_VERIFY_WINDOW_SEC=60`
- `ABS_JS_VERIFY_MIN_POW_ELAPSED_MS=180`
- `ABS_JS_VERIFY_MAX_POW_ELAPSED_MS=180000`
- `ABS_JS_FP_HASH_REQUESTS_PER_MIN=40`
- `ABS_JS_REQUEST_ID_REQUESTS_PER_MIN=80`

### Progressive penalties for `/_abs/verify`

- `ABS_VERIFY_FAIL_DELAY_START=2`
- `ABS_VERIFY_FAIL_SHORT_BAN_THRESHOLD=6`
- `ABS_VERIFY_FAIL_LONG_BAN_THRESHOLD=12`
- `ABS_VERIFY_FAIL_SHORT_BAN_SEC=120`
- `ABS_VERIFY_FAIL_LONG_BAN_SEC=900`

### Subnet escalation bans

- `ABS_SUBNET_BAN_ENABLED=true|false`
- `ABS_SUBNET_BAN_TRIGGER=3`
- `ABS_SUBNET_BAN_WINDOW_SEC=3600`
- `ABS_SUBNET_BAN_SECONDS=900`

## Production Profile (Recommended)

1. Set `ABS_RUNTIME_ENV=prod`.
2. Set `ABS_JS_OBFUSCATE_ASSETS_IN_PROD=true`.
3. Use strong `ABS_CHALLENGE_SECRET`.
4. Set `ABS_JS_COOKIE_SECURE=true` behind HTTPS.
5. Use Redis (`ABS_REDIS_URL`) for multi-instance deployments.
6. Put CDN/WAF/reverse proxy in front of app.

## Test Project (No examples dependency)

Use:

- `tests/test_project/app.py`
- `tests/test_project/script_job.py`
- `tests/test_project/README.md`

It is a minimal protected script endpoint (`/run-script`) for local testing.

## Important Notes

- `abs_js_ok` cookie is not a standalone DDoS shield. It is one signal in the L7 flow.
- For real attacks, combine:
  - edge DDoS/WAF
  - reverse proxy limits
  - this middleware
- This project protects application layer traffic (HTTP), not raw network flood by itself.
