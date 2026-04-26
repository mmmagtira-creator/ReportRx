"""Centralized configuration for the ReportRx web app."""

from __future__ import annotations

from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
TEMPLATES_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"

DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "reportrx.db"
THESIS_CODE_ROOT = _PROJECT_ROOT

CONFIDENCE_THRESHOLD_ACCEPTED = 0.70
CONFIDENCE_THRESHOLD_NEEDS_REVIEW = 0.40
