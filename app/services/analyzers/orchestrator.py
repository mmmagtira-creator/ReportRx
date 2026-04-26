"""Rule-based analysis orchestrator for the ReportRx web app."""

from __future__ import annotations

import logging
import re
import time
from typing import Dict

from app.config import (
    CONFIDENCE_THRESHOLD_ACCEPTED,
    CONFIDENCE_THRESHOLD_NEEDS_REVIEW,
)
from app.db import insert_report, next_case_id
from app.services.analyzers.base import AnalysisResult
from app.services.analyzers.local_fallback_provider import LocalFallbackProvider

logger = logging.getLogger("reportrx.orchestrator")

_fallback = LocalFallbackProvider()


def _sanitize(text: str) -> str:
    """Normalize whitespace before analysis."""
    return re.sub(r"\s+", " ", text).strip()


def _assign_status(result: AnalysisResult) -> str:
    """Map confidence to the prototype review workflow."""
    if result.is_empty():
        return "Abstain"
    if result.raw_confidence >= CONFIDENCE_THRESHOLD_ACCEPTED:
        return "Accepted"
    if result.raw_confidence >= CONFIDENCE_THRESHOLD_NEEDS_REVIEW:
        return "Needs Review"
    return "Abstain"


async def analyze_report(raw_text: str) -> Dict:
    """Run the local rule-based analyzer, persist the structured result, and return it."""
    clean_text = _sanitize(raw_text)
    if not clean_text:
        raise ValueError("Report text is empty")

    started = time.perf_counter()
    fallback_result = await _fallback.analyze(clean_text)
    latency_ms = round((time.perf_counter() - started) * 1000, 4)

    result = fallback_result if fallback_result is not None else AnalysisResult()
    status = _assign_status(result)
    case_id = next_case_id()

    row = {
        "case_id": case_id,
        "text_report": clean_text,
        "drug_mention": result.drug_mention,
        "reaction_mention": result.reaction_mention,
        "onset": result.onset,
        "raw_confidence": round(result.raw_confidence, 6),
        "status": status,
        "latency_ms": latency_ms,
    }

    insert_report(row)
    logger.info(
        "Analyzed %s  route=rule_based  latency=%.4fms  conf=%.6f -> %s",
        case_id,
        latency_ms,
        result.raw_confidence,
        status,
    )
    return row
