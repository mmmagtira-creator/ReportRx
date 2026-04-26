"""API route definitions for ReportRx."""

from __future__ import annotations

import csv
import io
import logging
from typing import Dict, List

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.db import clear_all_reports, get_all_reports
from app.services.analytics import build_analytics_summary
from app.services.analyzers.orchestrator import analyze_report
from app.services.reporting import build_analytics_report_pdf

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


class AnalyticsCountRow(BaseModel):
    name: str
    count: int


class AssociationRow(BaseModel):
    drug_name: str
    top_adr: str
    count: int


class AssociationChartRow(BaseModel):
    drug_name: str
    top_adr: str
    count: int


class AnalyticsSummary(BaseModel):
    view: str
    view_label: str
    filtered_report_count: int
    has_data: bool
    medicine_chart: List[AnalyticsCountRow]
    medicine_table: List[AnalyticsCountRow]
    reaction_chart: List[AnalyticsCountRow]
    reaction_table: List[AnalyticsCountRow]
    association_chart: List[AssociationChartRow]
    association_table: List[AssociationRow]


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


@router.get("/api/analytics", response_model=AnalyticsSummary)
async def api_analytics(view: str = Query("all")):
    """Return analytics summary derived from persisted reports."""
    try:
        return build_analytics_summary(view)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/api/analytics/report")
async def api_analytics_report(view: str = Query("all")):
    """Generate a formatted PDF report for the selected analytics view."""
    try:
        pdf_bytes = build_analytics_report_pdf(view)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        logger.exception("Analytics report generation error")
        raise HTTPException(
            status_code=500,
            detail="Unable to generate the analytics report right now.",
        )

    filename = f"reportrx_analytics_{view}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
