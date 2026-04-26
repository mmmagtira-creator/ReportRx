from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

from config import (
    CHANNEL_LABEL,
    EDGE_ONSET_OF,
    EDGE_REPORTED_TO,
    EDGE_SUSPECT_DRUG,
    EXPOSURE_LABEL,
    ONSET_LABEL,
    REACTION_LABEL,
)


@dataclass(frozen=True)
class Token:
    text: str
    start: int
    end: int
    lang: str
    normalized: str


@dataclass
class Span:
    label: str
    text: str
    start: int
    end: int
    confidence: float
    rule_hits: List[str] = field(default_factory=list)
    normalized_text: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def key(self) -> Tuple[str, int, int, str]:
        return (self.label, self.start, self.end, self.text)

    def exact_match_key(self) -> Tuple[str, int, int]:
        return (self.label, self.start, self.end)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Edge:
    label: str
    source_span_id: str
    target_span_id: str
    confidence: float
    rule_hits: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def key(self, spans_by_id: Dict[str, Span]) -> Tuple[str, Tuple[str, int, int], Tuple[str, int, int]]:
        return (
            self.label,
            spans_by_id[self.source_span_id].exact_match_key(),
            spans_by_id[self.target_span_id].exact_match_key(),
        )

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GraphOutput:
    case_id: str
    raw_text: str
    normalized_text: str
    tokens: List[Token]
    spans: Dict[str, Span]
    edges: List[Edge]
    raw_confidence: float
    calibrated_confidence: float
    status: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    validation_errors: List[str] = field(default_factory=list)
    latency_ms: Optional[float] = None
    processed_tokens: int = 0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "raw_text": self.raw_text,
            "normalized_text": self.normalized_text,
            "tokens": [asdict(token) for token in self.tokens],
            "spans": {span_id: span.as_dict() for span_id, span in self.spans.items()},
            "edges": [edge.as_dict() for edge in self.edges],
            "raw_confidence": self.raw_confidence,
            "calibrated_confidence": self.calibrated_confidence,
            "status": self.status,
            "metadata": self.metadata,
            "validation_errors": self.validation_errors,
            "latency_ms": self.latency_ms,
            "processed_tokens": self.processed_tokens,
        }


def validate_graph(graph: GraphOutput) -> List[str]:
    errors: List[str] = []
    spans = graph.spans
    edges = graph.edges

    reaction_ids = [span_id for span_id, span in spans.items() if span.label == REACTION_LABEL]
    exposure_ids = [span_id for span_id, span in spans.items() if span.label == EXPOSURE_LABEL]
    onset_ids = [span_id for span_id, span in spans.items() if span.label == ONSET_LABEL]
    channel_ids = [span_id for span_id, span in spans.items() if span.label == CHANNEL_LABEL]

    allowed_pairs = {
        EDGE_SUSPECT_DRUG: (EXPOSURE_LABEL, REACTION_LABEL),
        EDGE_ONSET_OF: (ONSET_LABEL, REACTION_LABEL),
        EDGE_REPORTED_TO: (REACTION_LABEL, CHANNEL_LABEL),
    }

    onset_targets = {}
    reaction_has_exposure = {rid: False for rid in reaction_ids}
    reaction_has_channel = {rid: False for rid in reaction_ids}

    for edge in edges:
        if edge.source_span_id not in spans or edge.target_span_id not in spans:
            errors.append(f"missing_span_reference:{edge.label}")
            continue

        source_label = spans[edge.source_span_id].label
        target_label = spans[edge.target_span_id].label
        if edge.label not in allowed_pairs:
            errors.append(f"unknown_edge_label:{edge.label}")
            continue

        expected_source, expected_target = allowed_pairs[edge.label]
        if source_label != expected_source or target_label != expected_target:
            errors.append(
                f"invalid_edge_type:{edge.label}:{source_label}->{target_label}"
            )

        if edge.label == EDGE_SUSPECT_DRUG:
            reaction_has_exposure[edge.target_span_id] = True
        elif edge.label == EDGE_REPORTED_TO:
            reaction_has_channel[edge.source_span_id] = True
        elif edge.label == EDGE_ONSET_OF:
            onset_targets.setdefault(edge.target_span_id, 0)
            onset_targets[edge.target_span_id] += 1

    for reaction_id in reaction_ids:
        if not reaction_has_exposure.get(reaction_id, False):
            errors.append(f"reaction_without_exposure:{reaction_id}")

        if channel_ids and not reaction_has_channel.get(reaction_id, False):
            errors.append(f"reaction_without_channel:{reaction_id}")

        if onset_targets.get(reaction_id, 0) > 1:
            errors.append(f"reaction_with_multiple_onsets:{reaction_id}")

    for onset_id in onset_ids:
        attached = any(
            edge.label == EDGE_ONSET_OF and edge.source_span_id == onset_id for edge in edges
        )
        if not attached:
            errors.append(f"orphan_onset:{onset_id}")

    return errors


def tuple_set(graph: GraphOutput) -> set:
    spans = graph.spans
    exposure_to_reaction = []
    onset_to_reaction = {}
    for edge in graph.edges:
        if edge.label == EDGE_SUSPECT_DRUG:
            source = spans[edge.source_span_id]
            target = spans[edge.target_span_id]
            exposure_to_reaction.append((edge.source_span_id, edge.target_span_id, source.text, target.text))
        elif edge.label == EDGE_ONSET_OF:
            onset_to_reaction[edge.target_span_id] = spans[edge.source_span_id].text

    tuples = set()
    for _, reaction_id, exposure_text, reaction_text in exposure_to_reaction:
        tuples.add((exposure_text, reaction_text, onset_to_reaction.get(reaction_id, "")))
    return tuples