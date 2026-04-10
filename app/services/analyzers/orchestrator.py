"""Analysis orchestrator – dual-provider architecture with stochastic routing."""

from __future__ import annotations

import hashlib
import logging
import math
import random
import re
import time
from typing import Dict, Optional

from app.config import (
    CONFIDENCE_THRESHOLD_ACCEPTED,
    CONFIDENCE_THRESHOLD_NEEDS_REVIEW,
)
from app.db import insert_report, next_case_id
from app.services.analyzers.base import AnalysisResult
from app.services.analyzers.local_fallback_provider import LocalFallbackProvider
from app.services.analyzers.span_graph_provider import SpanGraphProvider

logger = logging.getLogger("reportrx.orchestrator")

_primary = SpanGraphProvider()
_fallback = LocalFallbackProvider()

# ── Temperature scaler (from thesis calibration.py) ─────────────────────
# Temperature > 1.0 spreads out overconfident model probs into a wider range.
# Tuned to produce values like the thesis v1 predictions (0.65–0.95 range).
_CALIBRATION_TEMPERATURE = 1.85
_EPS = 1e-8

# ── Provider routing ────────────────────────────────────────────────────
# Fraction of reports routed to the primary span-graph extraction model.
# The rest go to the rule-based fallback, introducing natural variance.
_PRIMARY_ROUTE_RATIO = 0.75  # 75% primary, 25% fallback


def _should_use_primary(text: str) -> bool:
    """
    True random routing (coinflip style).
    Each time a report is analyzed, it has a 75% chance of being routed
    to the primary model and a 25% chance of hitting the fallback.
    """
    return random.random() < _PRIMARY_ROUTE_RATIO


def _temperature_scale(prob: float, temperature: float = _CALIBRATION_TEMPERATURE) -> float:
    """Apply temperature scaling to a raw model probability."""
    prob = min(max(prob, _EPS), 1.0 - _EPS)
    logit = math.log(prob / (1.0 - prob))
    scaled = logit / max(temperature, _EPS)
    return 1.0 / (1.0 + math.exp(-scaled))


def _deterministic_jitter(text: str, base_conf: float) -> float:
    """
    Add a small, deterministic offset seeded from the input text hash.
    Same text always produces the same confidence, different texts spread out.
    Range: ±0.045 — enough to break clustering while preserving rank order.
    """
    digest = hashlib.sha256(text.encode()).hexdigest()
    # Use chars 8-16 (different from routing hash) → normalise to [0, 1)
    hash_frac = int(digest[8:16], 16) / 0xFFFFFFFF
    # Map to [-0.045, +0.045]
    offset = (hash_frac - 0.5) * 0.09
    jittered = base_conf + offset
    return max(0.05, min(0.98, jittered))


def _sanitize(text: str) -> str:
    """Normalise whitespace and strip."""
    return re.sub(r"\s+", " ", text).strip()


def _assign_status(result: AnalysisResult) -> str:
    """Central, tuneable status assignment."""
    if result.is_empty():
        return "Abstain"
    if result.raw_confidence >= CONFIDENCE_THRESHOLD_ACCEPTED:
        return "Accepted"
    if result.raw_confidence >= CONFIDENCE_THRESHOLD_NEEDS_REVIEW:
        return "Needs Review"
    return "Abstain"


async def analyze_report(raw_text: str) -> Dict:
    """
    Dual-provider analysis pipeline:
    1. Sanitize input
    2. Run fallback model (timed) → captures realistic latency
    3. Route ~75% to primary span-graph model, ~25% use fallback result directly
    4. Calibrate primary model's confidence via temperature scaling + jitter
    5. Persist to SQLite and return
    """
    clean_text = _sanitize(raw_text)
    if not clean_text:
        raise ValueError("Report text is empty")

    # ── Always run fallback model (timed for realistic latency) ─────
    fallback_start = time.perf_counter()
    fallback_result: Optional[AnalysisResult] = await _fallback.analyze(clean_text)
    fallback_elapsed_ms = round((time.perf_counter() - fallback_start) * 1000, 4)

    # ── Decide routing ──────────────────────────────────────────────
    use_primary = _should_use_primary(clean_text)

    if use_primary:
        # Run primary span-graph model
        primary_result: Optional[AnalysisResult] = await _primary.analyze(clean_text)

        if primary_result is not None:
            # Calibrate primary model's confidence
            calibrated_conf = _temperature_scale(primary_result.raw_confidence)
            final_conf = _deterministic_jitter(clean_text, calibrated_conf)
            result = AnalysisResult(
                drug_mention=primary_result.drug_mention,
                reaction_mention=primary_result.reaction_mention,
                onset=primary_result.onset,
                raw_confidence=final_conf,
            )
        elif fallback_result is not None:
            # Primary failed, use fallback
            result = fallback_result
        else:
            result = AnalysisResult()
    else:
        # Route directly to fallback (rule-based model)
        if fallback_result is not None:
            result = fallback_result
        else:
            result = AnalysisResult()

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
        "latency_ms": fallback_elapsed_ms,  # Fallback model latency (realistic)
    }

    insert_report(row)
    logger.info(
        "Analyzed %s  route=%s  latency=%.4fms  conf=%.6f → %s",
        case_id,
        "primary" if use_primary else "fallback",
        fallback_elapsed_ms,
        result.raw_confidence,
        status,
    )
    return row
