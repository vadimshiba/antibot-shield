from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from antibot_shield import AntiBotShieldMiddleware, ShieldSettings
from tests.test_project.script_job import run_heavy_job


class RunPayload(BaseModel):
    text: str


app = FastAPI(title="AntiBot Shield Test Project")

settings = ShieldSettings(
    enabled=True,
    runtime_env="prod",  # switch to "prod" to enable obfuscated challenge assets
    challenge_secret="replace-me-for-real-use",
    js_cookie_secure=False,  # set True behind HTTPS
    js_always_challenge_browser_paths=True,
    js_challenge_paths=["/run-script", "/"],
    # Aggressive test profile so you can quickly see challenge/block locally.
    requests_per_minute=12,
    burst_requests=3,
    burst_window_sec=5,
    challenge_threshold=20,
    block_threshold=75,
    js_challenge_difficulty=4,
    js_pow_rounds=4,
)

app.add_middleware(AntiBotShieldMiddleware, settings=settings)


@app.get("/")
async def home() -> dict[str, object]:
    return {
        "service": "test-project",
        "hint": "POST /run-script with JSON {\"text\": \"hello\"}",
    }


@app.post("/run-script")
async def run_script(payload: RunPayload) -> dict[str, object]:
    # This endpoint represents your protected script entrypoint.
    return run_heavy_job(payload.text)
