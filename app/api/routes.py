"""API route definitions for ReportRx."""

from __future__ import annotations

import csv
import io
import logging
from typing import Dict, List

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.db import clear_all_reports, get_all_reports
from app.services.analyzers.orchestrator import analyze_report

logger = logging.getLogger("reportrx.api")

router = APIRouter()


# ── Request / Response schemas ──────────────────────────────────────────
class AnalyzeRequest(BaseModel):
    text_report: str = Field(..., min_length=1, description="Free-text ADR report")


class ReportRow(BaseModel):
    case_id: str
    text_report: str
    drug_mention: str
    reaction_mention: str
    onset: str
    raw_confidence: float
    status: str
    latency_ms: float


# ── Endpoints ───────────────────────────────────────────────────────────
@router.post("/api/analyze", response_model=ReportRow)
async def api_analyze(payload: AnalyzeRequest):
    """Analyse a single ADR report and persist the result."""
    try:
        row = await analyze_report(payload.text_report)
        return row
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception("Analysis pipeline error")
        raise HTTPException(
            status_code=500,
            detail="Unable to analyze report right now. Please try again.",
        )


@router.get("/api/reports", response_model=List[ReportRow])
async def api_reports():
    """Return all persisted analyzed reports."""
    return get_all_reports()


@router.get("/api/export/csv")
async def api_export_csv():
    """Download all reports as a CSV file."""
    reports = get_all_reports()
    buf = io.StringIO()
    fieldnames = [
        "case_id", "text_report", "drug_mention", "reaction_mention",
        "onset", "raw_confidence", "status", "latency_ms",
    ]
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for r in reports:
        writer.writerow(r)

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=reportrx_export.csv"},
    )


@router.delete("/api/reports")
async def api_clear_reports():
    """Delete all reports and reset case ID counter."""
    clear_all_reports()
    return {"status": "cleared"}


@router.get("/api/health")
async def api_health():
    """Quick liveness check."""
    return {"status": "ok"}
