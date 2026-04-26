from __future__ import annotations

import re
import time
from typing import Dict, List, Optional, Tuple

from calibration import TemperatureScaler
from config import (
    CHANNEL_LABEL,
    DEFAULT_CONFIDENCE_THRESHOLD,
    EDGE_ONSET_OF,
    EDGE_REPORTED_TO,
    EDGE_SUSPECT_DRUG,
    EXPOSURE_LABEL,
    ONSET_LABEL,
    REACTION_LABEL,
)
from patterns import (
    EXPOSURE_CUE_PATTERNS,
    ONSET_REGEXES,
    REACTION_PATTERNS,
    REPORTING_CHANNEL_PATTERNS,
    find_pattern_spans,
    has_local_negation,
)
from preprocessing import PreprocessedText
from schema import Edge, GraphOutput, Span, validate_graph
from stopwords_utils import PROTECTED_CUES, combined_stopwords
from weak_supervision import medicine_candidates_from_row

STOPWORDS = combined_stopwords()

LEFT_REACTION_MODIFIERS = {
    "slight",
    "mild",
    "medyo",
    "konting",
    "konti",
    "very",
    "really",
    "talaga",
    "sobrang",
    "super",
    "grabe",
    "matinding",
    "parang",
}

PAIN_TAIL_TOKENS = {
    "ng",
    "konti",
    "unti",
    "unti-unti",
    "ang",
    "yung",
    "yong",
    "tiyan",
    "sikmura",
    "ulo",
    "dibdib",
    "lalamunan",
    "braso",
    "kamay",
    "paa",
    "likod",
    "chest",
    "stomach",
    "abdomen",
    "head",
    "throat",
    "arm",
    "arms",
    "leg",
    "legs",
    "back",
    "ko",
    "my",
    "talaga",
    "sobrang",
    "super",
}

RASH_LOCATION_TOKENS = {
    "sa",
    "on",
    "around",
    "near",
    "leeg",
    "braso",
    "kamay",
    "paa",
    "mukha",
    "dibdib",
    "tiyan",
    "likod",
    "face",
    "neck",
    "arm",
    "arms",
    "hand",
    "hands",
    "leg",
    "legs",
    "chest",
    "stomach",
    "back",
    "body",
    "and",
    "at",
    "ko",
    "my",
}

CLAUSE_BREAKERS = {
    ",",
    ".",
    ";",
    ":",
    "?",
    "!",
    "pero",
    "but",
    "however",
    "kaya",
    "so",
}

BODY_PART_WORDS = {
    "tiyan",
    "sikmura",
    "ulo",
    "dibdib",
    "lalamunan",
    "braso",
    "kamay",
    "paa",
    "likod",
    "chest",
    "stomach",
    "abdomen",
    "head",
    "throat",
    "arm",
    "arms",
    "leg",
    "legs",
    "back",
    "neck",
    "face",
}


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def make_span_id(label: str, index: int) -> str:
    return f"{label.lower()}_{index}"


def build_flexible_literal_pattern(candidate: str) -> str:
    parts = [part for part in re.split(r"\s+", candidate.strip()) if part]
    if not parts:
        return ""

    body = r"\s+".join(re.escape(part) for part in parts)
    if re.fullmatch(r"[\w-]+(?:\s+[\w-]+)*", candidate, flags=re.UNICODE):
        return rf"(?<!\w){body}(?!\w)"
    return body


def has_nearby_exposure_cue(text: str, start: int, window_size: int = 35) -> bool:
    left_context = text[max(0, start - window_size):start]
    return bool(
        re.search(
            r"\b(?:uminom|inom|take|took|using|used|nag[- ]?[a-zA-Z][\w-]*)\b",
            left_context,
            flags=re.IGNORECASE,
        )
    )


def overlapping_token_range(preprocessed: PreprocessedText, start: int, end: int) -> Optional[Tuple[int, int]]:
    indices = [
        idx
        for idx, token in enumerate(preprocessed.tokens)
        if token.start < end and start < token.end
    ]
    if not indices:
        return None
    return indices[0], indices[-1] + 1


def token_norms(preprocessed: PreprocessedText, start_idx: int, end_idx: int) -> List[str]:
    return [token.normalized for token in preprocessed.tokens[start_idx:end_idx]]


def expand_left_modifiers(preprocessed: PreprocessedText, start_idx: int) -> int:
    idx = start_idx
    while idx > 0:
        prev = preprocessed.tokens[idx - 1]
        if prev.normalized in LEFT_REACTION_MODIFIERS:
            idx -= 1
            continue
        break
    return idx


def expand_right_with_lexicon(
    preprocessed: PreprocessedText,
    end_idx: int,
    allowed_tokens: set[str],
    max_extra_word_tokens: int = 8,
) -> int:
    idx = end_idx
    consumed = 0

    while idx < len(preprocessed.tokens):
        token = preprocessed.tokens[idx]
        normalized = token.normalized

        if normalized in CLAUSE_BREAKERS:
            break

        if normalized in allowed_tokens or normalized in BODY_PART_WORDS:
            idx += 1
            if re.search(r"\w", token.text):
                consumed += 1
            if consumed >= max_extra_word_tokens:
                break
            continue

        break

    return idx


def reaction_rule_confidence(rule_name: str) -> float:
    if rule_name.startswith("reaction_exact_"):
        return 0.95
    if rule_name.startswith("reaction_"):
        return 0.82
    return 0.78


def onset_rule_confidence(rule_name: str) -> float:
    if rule_name.startswith("onset_"):
        return 0.88
    return 0.80


def channel_rule_confidence(rule_name: str) -> float:
    if rule_name.startswith("channel_"):
        return 0.98
    return 0.92


def expand_reaction_token_window(
    preprocessed: PreprocessedText,
    trigger_start_idx: int,
    trigger_end_idx: int,
    rule_name: str,
) -> Tuple[int, int]:
    if rule_name.startswith("reaction_exact_"):
        return trigger_start_idx, trigger_end_idx

    head_text = " ".join(token_norms(preprocessed, trigger_start_idx, trigger_end_idx))
    start_idx = expand_left_modifiers(preprocessed, trigger_start_idx)
    end_idx = trigger_end_idx

    if any(head in head_text for head in ["sumakit", "masakit", "pain", "headache", "stomach pain"]):
        end_idx = expand_right_with_lexicon(
            preprocessed,
            end_idx,
            allowed_tokens=PAIN_TAIL_TOKENS,
            max_extra_word_tokens=8,
        )
    elif any(head in head_text for head in ["kati", "itch", "rash", "rashes", "pantal", "namamantal"]):
        end_idx = expand_right_with_lexicon(
            preprocessed,
            end_idx,
            allowed_tokens=RASH_LOCATION_TOKENS,
            max_extra_word_tokens=8,
        )
    elif any(head in head_text for head in ["nausea", "nasusuka", "nagsuka", "vomit", "vomiting"]):
        end_idx = trigger_end_idx
    elif any(
        head in head_text
        for head in [
            "nahirapan",
            "hirap",
            "difficulty breathing",
            "trouble breathing",
            "shortness of breath",
            "throat tightness",
        ]
    ):
        end_idx = trigger_end_idx
    else:
        end_idx = trigger_end_idx

    return start_idx, end_idx


def find_exposure_spans(preprocessed: PreprocessedText, row: Dict[str, object]) -> List[Span]:
    text = preprocessed.normalized_text
    spans: List[Span] = []
    seen = set()

    candidates = medicine_candidates_from_row(row)

    for candidate in candidates:
        if not candidate:
            continue

        pattern = build_flexible_literal_pattern(candidate)
        if not pattern:
            continue

        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            span_text = match.group(0)
            if not span_text.strip():
                continue

            key = (match.start(), match.end(), span_text.lower())
            if key in seen:
                continue
            seen.add(key)

            rule_hits = ["weak_alignment_checkbox"]
            confidence = 0.88

            if has_nearby_exposure_cue(text, match.start()):
                confidence += 0.05
                rule_hits.append("local_exposure_cue")

            spans.append(
                Span(
                    label=EXPOSURE_LABEL,
                    text=span_text,
                    start=match.start(),
                    end=match.end(),
                    confidence=clamp(confidence),
                    normalized_text=span_text.lower(),
                    rule_hits=rule_hits,
                )
            )

    if not spans:
        for cue in find_pattern_spans(text, EXPOSURE_CUE_PATTERNS):
            cue_start = int(cue["end"])
            tail = text[cue_start: cue_start + 60]
            tail_match = re.search(
                r"\b(?:ng|of)?\s*([A-Za-z][A-Za-z0-9\- ]{2,40})",
                tail,
                flags=re.IGNORECASE,
            )
            if tail_match:
                candidate = tail_match.group(1)
                candidate_lower = candidate.lower().strip()

                if not candidate_lower:
                    continue
                if candidate_lower in STOPWORDS or candidate_lower in PROTECTED_CUES:
                    continue

                start = cue_start + tail_match.start(1)
                end = cue_start + tail_match.end(1)

                spans.append(
                    Span(
                        label=EXPOSURE_LABEL,
                        text=text[start:end],
                        start=start,
                        end=end,
                        confidence=0.55,
                        normalized_text=candidate_lower,
                        rule_hits=["exposure_fallback_from_cue"],
                    )
                )

    return merge_overlapping_spans(spans)


def find_reaction_spans(preprocessed: PreprocessedText) -> List[Span]:
    text = preprocessed.normalized_text
    found = find_pattern_spans(text, REACTION_PATTERNS)
    spans: List[Span] = []
    seen = set()

    for item in found:
        token_range = overlapping_token_range(preprocessed, int(item["start"]), int(item["end"]))
        if token_range is None:
            continue

        trigger_start_idx, trigger_end_idx = token_range
        expanded_start_idx, expanded_end_idx = expand_reaction_token_window(
            preprocessed,
            trigger_start_idx,
            trigger_end_idx,
            str(item["rule"]),
        )

        start = preprocessed.tokens[expanded_start_idx].start
        end = preprocessed.tokens[expanded_end_idx - 1].end
        span_text = text[start:end]

        if not span_text.strip():
            continue

        confidence = reaction_rule_confidence(str(item["rule"]))
        rule_hits = [str(item["rule"])]

        if has_local_negation(text, start, end):
            confidence -= 0.35
            rule_hits.append("local_negation_penalty")

        key = (start, end, span_text.lower())
        if key in seen:
            continue
        seen.add(key)

        spans.append(
            Span(
                label=REACTION_LABEL,
                text=span_text,
                start=start,
                end=end,
                confidence=clamp(confidence),
                normalized_text=span_text.lower(),
                rule_hits=rule_hits,
            )
        )

    return merge_overlapping_spans(spans)


def find_onset_spans(preprocessed: PreprocessedText) -> List[Span]:
    text = preprocessed.normalized_text
    found = find_pattern_spans(text, ONSET_REGEXES)
    spans: List[Span] = []
    seen = set()

    for item in found:
        start = int(item["start"])
        end = int(item["end"])
        span_text = text[start:end]

        if not span_text.strip():
            continue

        key = (start, end, span_text.lower())
        if key in seen:
            continue
        seen.add(key)

        spans.append(
            Span(
                label=ONSET_LABEL,
                text=span_text,
                start=start,
                end=end,
                confidence=onset_rule_confidence(str(item["rule"])),
                normalized_text=span_text.lower(),
                rule_hits=[str(item["rule"])],
            )
        )

    return merge_overlapping_spans(spans)


def find_reporting_channel_spans(preprocessed: PreprocessedText) -> List[Span]:
    text = preprocessed.normalized_text
    found = find_pattern_spans(text, REPORTING_CHANNEL_PATTERNS)
    spans: List[Span] = []
    seen = set()

    for item in found:
        start = int(item["start"])
        end = int(item["end"])
        span_text = text[start:end]

        if not span_text.strip():
            continue

        key = (start, end, span_text.lower())
        if key in seen:
            continue
        seen.add(key)

        spans.append(
            Span(
                label=CHANNEL_LABEL,
                text=span_text,
                start=start,
                end=end,
                confidence=channel_rule_confidence(str(item["rule"])),
                normalized_text=span_text.lower(),
                rule_hits=[str(item["rule"])],
            )
        )

    return merge_overlapping_spans(spans)


def merge_overlapping_spans(spans: List[Span]) -> List[Span]:
    if not spans:
        return []

    spans = sorted(
        spans,
        key=lambda span: (span.start, -(span.end - span.start), -span.confidence),
    )

    merged: List[Span] = []
    for span in spans:
        if not merged:
            merged.append(span)
            continue

        previous = merged[-1]
        overlaps = (
            span.label == previous.label
            and span.start < previous.end
            and previous.start < span.end
        )

        if overlaps:
            if span.confidence > previous.confidence:
                merged[-1] = span
            elif span.confidence == previous.confidence and (span.end - span.start) > (previous.end - previous.start):
                merged[-1] = span
        else:
            merged.append(span)

    return merged


def sentence_bounds(text: str, position: int) -> Tuple[int, int]:
    previous_break = max(
        text.rfind(".", 0, position),
        text.rfind("?", 0, position),
        text.rfind("!", 0, position),
    )
    next_break_candidates = [
        idx
        for idx in (
            text.find(".", position),
            text.find("?", position),
            text.find("!", position),
        )
        if idx != -1
    ]

    start = 0 if previous_break == -1 else previous_break + 1
    end = min(next_break_candidates) if next_break_candidates else len(text)
    return start, end


def onset_scope_end(spans: Dict[str, Span], ordered_onset_ids: List[str], onset_id: str, text: str) -> Tuple[int, int]:
    onset = spans[onset_id]
    sentence_start, sentence_end = sentence_bounds(text, onset.start)
    later_onset_starts = [
        spans[other_id].start
        for other_id in ordered_onset_ids
        if spans[other_id].start > onset.start and spans[other_id].start < sentence_end
    ]
    scope_end = min(later_onset_starts) if later_onset_starts else sentence_end
    return sentence_start, scope_end


def build_graph(
    case_id: str,
    row: Dict[str, object],
    preprocessed: PreprocessedText,
    scaler: TemperatureScaler | None = None,
    threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> GraphOutput:
    start_time = time.perf_counter()

    exposures = find_exposure_spans(preprocessed, row)
    reactions = find_reaction_spans(preprocessed)
    onsets = find_onset_spans(preprocessed)
    channels = find_reporting_channel_spans(preprocessed)

    spans: Dict[str, Span] = {}
    edges: List[Edge] = []

    span_order = exposures + reactions + onsets + channels
    for idx, span in enumerate(span_order, start=1):
        span_id = make_span_id(span.label, idx)
        spans[span_id] = span

    exposure_ids = [span_id for span_id, span in spans.items() if span.label == EXPOSURE_LABEL]
    reaction_ids = [span_id for span_id, span in spans.items() if span.label == REACTION_LABEL]
    onset_ids = sorted(
        [span_id for span_id, span in spans.items() if span.label == ONSET_LABEL],
        key=lambda span_id: spans[span_id].start,
    )
    channel_ids = [span_id for span_id, span in spans.items() if span.label == CHANNEL_LABEL]

    for exposure_id in exposure_ids:
        for reaction_id in reaction_ids:
            exposure = spans[exposure_id]
            reaction = spans[reaction_id]
            if reaction.start >= exposure.start:
                edges.append(
                    Edge(
                        label=EDGE_SUSPECT_DRUG,
                        source_span_id=exposure_id,
                        target_span_id=reaction_id,
                        confidence=clamp((exposure.confidence + reaction.confidence) / 2.0),
                        rule_hits=["reaction_after_exposure"],
                    )
                )

    for onset_id in onset_ids:
        onset = spans[onset_id]
        sentence_start, scope_end = onset_scope_end(spans, onset_ids, onset_id, preprocessed.normalized_text)

        eligible_reactions = [
            reaction_id
            for reaction_id in reaction_ids
            if sentence_start <= spans[reaction_id].start
            and onset.end <= spans[reaction_id].start
            and spans[reaction_id].end <= scope_end
        ]

        for reaction_id in eligible_reactions:
            reaction = spans[reaction_id]
            edges.append(
                Edge(
                    label=EDGE_ONSET_OF,
                    source_span_id=onset_id,
                    target_span_id=reaction_id,
                    confidence=clamp((onset.confidence + reaction.confidence) / 2.0),
                    rule_hits=["same_sentence_onset_scope"],
                )
            )

    for channel_id in channel_ids:
        channel_span = spans[channel_id]
        for reaction_id in reaction_ids:
            reaction = spans[reaction_id]
            if reaction.start < channel_span.start:
                edges.append(
                    Edge(
                        label=EDGE_REPORTED_TO,
                        source_span_id=reaction_id,
                        target_span_id=channel_id,
                        confidence=clamp((reaction.confidence + channel_span.confidence) / 2.0),
                        rule_hits=["explicit_channel_mention"],
                    )
                )

    raw_confidence = aggregate_graph_confidence(spans, edges)
    calibrated_confidence = scaler.predict(raw_confidence) if scaler else raw_confidence
    status = "accepted" if calibrated_confidence >= threshold else "abstain"

    graph = GraphOutput(
        case_id=case_id,
        raw_text=preprocessed.raw_text,
        normalized_text=preprocessed.normalized_text,
        tokens=preprocessed.tokens,
        spans=spans,
        edges=edges,
        raw_confidence=raw_confidence,
        calibrated_confidence=calibrated_confidence,
        status=status,
        metadata={
            "age": row.get("age"),
            "weight": row.get("weight"),
            "sex": row.get("sex"),
            "dosage": row.get("dosage"),
            "route": row.get("route"),
            "reason": row.get("reason"),
            "valid": row.get("valid"),
        },
        processed_tokens=len(preprocessed.tokens),
    )

    graph.validation_errors = validate_graph(graph)
    graph.latency_ms = (time.perf_counter() - start_time) * 1000.0
    return graph


def aggregate_graph_confidence(spans: Dict[str, Span], edges: List[Edge]) -> float:
    if not spans:
        return 0.05

    span_mean = sum(span.confidence for span in spans.values()) / len(spans)
    edge_mean = sum(edge.confidence for edge in edges) / len(edges) if edges else span_mean
    score = (0.6 * span_mean) + (0.4 * edge_mean)

    labels = [span.label for span in spans.values()]
    if REACTION_LABEL not in labels or EXPOSURE_LABEL not in labels:
        score -= 0.20

    has_suspect_edge = any(edge.label == EDGE_SUSPECT_DRUG for edge in edges)
    if REACTION_LABEL in labels and not has_suspect_edge:
        score -= 0.12

    has_onset_span = any(span.label == ONSET_LABEL for span in spans.values())
    has_onset_edge = any(edge.label == EDGE_ONSET_OF for edge in edges)
    if has_onset_span and not has_onset_edge:
        score -= 0.08

    return clamp(score)