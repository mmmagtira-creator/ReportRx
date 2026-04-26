"""ReportRx – FastAPI application entry point."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes import router as api_router
from app.config import STATIC_DIR, TEMPLATES_DIR
from app.db import init_db

# ── Logging ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-28s  %(levelname)-5s  %(message)s",
    datefmt="%H:%M:%S",
)
# Suppress noisy libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# ── App setup ───────────────────────────────────────────────────────────
app = FastAPI(
    title="ReportRx",
    description="ADR Report Analysis Prototype",
    version="0.1.0",
)

# Static files & templates
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# API routes
app.include_router(api_router)


# ── Events ──────────────────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup():
    init_db()
    logging.getLogger("reportrx").info("Database initialised · server ready")


# ── Page route ──────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")
