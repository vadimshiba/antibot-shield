from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response

from antibot_shield import AntiBotShieldMiddleware, ShieldSettings

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Protected Service")
app.add_middleware(AntiBotShieldMiddleware, settings=ShieldSettings())


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/")
def home() -> dict:
    return {"message": "service alive"}


@app.get("/api/data")
def data() -> dict:
    return {"items": [1, 2, 3]}


@app.get("/assets/user-page.css")
def user_page_css() -> Response:
    return Response((STATIC_DIR / "user-page.css").read_text(encoding="utf-8"), media_type="text/css")


@app.get("/assets/user-page.js")
def user_page_js() -> Response:
    return Response((STATIC_DIR / "user-page.js").read_text(encoding="utf-8"), media_type="application/javascript")


@app.get("/app/user", response_class=HTMLResponse)
def user_page() -> str:
    return (TEMPLATES_DIR / "user_challenge_page.html").read_text(encoding="utf-8")
