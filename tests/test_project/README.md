# Test Project (No examples/)

Minimal standalone project to protect your own script endpoint with `antibot_shield`.

## Files

- `app.py` - FastAPI app + `AntiBotShieldMiddleware`
- `script_job.py` - your script logic (replace with real code)

## Run

From repository root:

```bash
source .venv/bin/activate
uvicorn tests.test_project.app:app --host 0.0.0.0 --port 8080 --reload
```

Open:

- `http://127.0.0.1:8080/`

Send request:

```bash
curl -X POST 'http://127.0.0.1:8080/run-script' \
  -H 'content-type: application/json' \
  -d '{"text":"hello"}'
```

## Quick challenge test

This test project uses aggressive thresholds. Trigger challenge quickly:

```bash
for i in {1..8}; do curl -I 'http://127.0.0.1:8080/' ; done
```

Trigger with suspicious UA:

```bash
curl -i 'http://127.0.0.1:8080/' -H 'user-agent: curl/8.0'
```

For API-style requests (without browser `Accept`), you may get JSON like:

- `429 challenge_required`
- `403 blocked`

## Production toggles

Use env vars (or set in `ShieldSettings`):

```bash
export ABS_RUNTIME_ENV=prod
export ABS_JS_OBFUSCATE_ASSETS_IN_PROD=true
export ABS_CHALLENGE_SECRET='your-long-secret'
export ABS_JS_COOKIE_SECURE=true
```

## Where to plug your real script

Edit `tests/test_project/script_job.py` function `run_heavy_job()` and keep `/run-script` as the protected entrypoint.
