"""Centralised configuration for the ReportRx web app."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (one level up from app/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

# ── Paths ──────────────────────────────────────────────────────────────
APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
TEMPLATES_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"

# Ensure the data directory exists on import
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "reportrx.db"

# ── Span-graph model backend ───────────────────────────────────────────
SG_API_KEY: str = os.getenv("SG_API_KEY", "")
SG_MODEL: str = os.getenv("SG_MODEL", "gpt-5-nano")
SG_TIMEOUT_SECONDS: int = int(os.getenv("SG_TIMEOUT_SECONDS", "30"))

# ── Thesis codebase root (for local model imports) ─────────────────────
THESIS_CODE_ROOT = _PROJECT_ROOT

# ── Status thresholds ──────────────────────────────────────────────────
CONFIDENCE_THRESHOLD_ACCEPTED = 0.70
CONFIDENCE_THRESHOLD_NEEDS_REVIEW = 0.40
