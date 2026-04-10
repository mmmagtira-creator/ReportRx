from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Any

from calibration import fit_temperature_scaler
from evaluation import (
    graph_level_correctness,
    overall_metrics,
    plot_reliability_diagram,
    plot_risk_coverage_curve,
    save_metrics_json,
)
from extractor import build_graph
from io_utils import export_predictions_csv, export_predictions_jsonl, load_dataset
from preprocessing import preprocess_text
from schema import Edge, GraphOutput, Span


def get_first_present(data: Dict[str, Any], candidate_keys: List[str], default=None):
    for key in candidate_keys:
        if key in data:
            return data[key]
    return default


def normalize_edge_item(edge: Dict[str, Any], case_id: str, edge_index: int) -> Dict[str, Any]:
    label = get_first_present(edge, ["label", "relation", "edge_label"])
    source_span_id = get_first_present(
        edge,
        ["source_span_id", "source", "from", "head", "head_span_id"],
    )
    target_span_id = get_first_present(
        edge,
        ["target_span_id", "target", "to", "tail", "tail_span_id"],
    )

    if label is None:
        raise ValueError(
            f"Gold annotation error in case {case_id}, edge #{edge_index}: missing edge label."
        )
    if source_span_id is None:
        raise ValueError(
            f"Gold annotation error in case {case_id}, edge #{edge_index}: "
            f"missing source span reference. Expected one of "
            f"['source_span_id', 'source', 'from', 'head', 'head_span_id']."
        )
    if target_span_id is None:
        raise ValueError(
            f"Gold annotation error in case {case_id}, edge #{edge_index}: "
            f"missing target span reference. Expected one of "
            f"['target_span_id', 'target', 'to', 'tail', 'tail_span_id']."
        )

    return {
        "label": label,
        "source_span_id": source_span_id,
        "target_span_id": target_span_id,
        "confidence": float(edge.get("confidence", 1.0)),
        "rule_hits": list(edge.get("rule_hits", ["gold"])),
        "metadata": dict(edge.get("metadata", {})),
    }


def graph_from_gold_item(item: Dict[str, object]) -> GraphOutput:
    case_id = str(item["case_id"])

    spans = {}
    raw_spans = item.get("spans", {})
    if not isinstance(raw_spans, dict):
        raise ValueError(f"Gold annotation error in case {case_id}: 'spans' must be a JSON object.")

    for span_id, span in raw_spans.items():
        spans[span_id] = Span(
            label=span["label"],
            text=span["text"],
            start=int(span["start"]),
            end=int(span["end"]),
            confidence=float(span.get("confidence", 1.0)),
            rule_hits=list(span.get("rule_hits", ["gold"])),
            normalized_text=span.get("normalized_text"),
            metadata=dict(span.get("metadata", {})),
        )

    edges = []
    raw_edges = item.get("edges", [])
    if not isinstance(raw_edges, list):
        raise ValueError(f"Gold annotation error in case {case_id}: 'edges' must be a JSON array.")

    for edge_index, edge in enumerate(raw_edges, start=1):
        normalized_edge = normalize_edge_item(edge, case_id=case_id, edge_index=edge_index)

        if normalized_edge["source_span_id"] not in spans:
            raise ValueError(
                f"Gold annotation error in case {case_id}, edge #{edge_index}: "
                f"source span '{normalized_edge['source_span_id']}' not found in spans."
            )
        if normalized_edge["target_span_id"] not in spans:
            raise ValueError(
                f"Gold annotation error in case {case_id}, edge #{edge_index}: "
                f"target span '{normalized_edge['target_span_id']}' not found in spans."
            )

        edges.append(
            Edge(
                label=normalized_edge["label"],
                source_span_id=normalized_edge["source_span_id"],
                target_span_id=normalized_edge["target_span_id"],
                confidence=normalized_edge["confidence"],
                rule_hits=normalized_edge["rule_hits"],
                metadata=normalized_edge["metadata"],
            )
        )

    graph = GraphOutput(
        case_id=case_id,
        raw_text=item.get("raw_text", ""),
        normalized_text=item.get("normalized_text", item.get("raw_text", "")),
        tokens=[],
        spans=spans,
        edges=edges,
        raw_confidence=1.0,
        calibrated_confidence=1.0,
        status="gold",
        metadata=dict(item.get("metadata", {})),
        validation_errors=list(item.get("validation_errors", [])),
        latency_ms=None,
        processed_tokens=0,
    )
    return graph


def load_gold_jsonl(path: str | Path) -> Dict[str, GraphOutput]:
    gold_graphs: Dict[str, GraphOutput] = {}
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
                graph = graph_from_gold_item(item)
                gold_graphs[graph.case_id] = graph
            except Exception as exc:
                raise ValueError(
                    f"Failed to parse gold JSONL at line {line_number}: {exc}"
                ) from exc
    return gold_graphs


def run_pipeline(
    input_csv: str,
    output_dir: str,
    gold_jsonl: str | None = None,
    confidence_threshold: float = 0.70,
) -> None:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_dataset(input_csv)
    records = df.to_dict(orient="records")

    raw_graphs: List[GraphOutput] = []
    for row in records:
        text = str(row.get("text_report") or "")
        preprocessed = preprocess_text(text)
        graph = build_graph(
            case_id=row["case_id"],
            row=row,
            preprocessed=preprocessed,
            scaler=None,
            threshold=confidence_threshold,
        )
        raw_graphs.append(graph)

    scaler = None
    if gold_jsonl:
        gold_graphs = load_gold_jsonl(gold_jsonl)
        matched_graphs = [graph for graph in raw_graphs if graph.case_id in gold_graphs]
        correctness = graph_level_correctness(matched_graphs, gold_graphs)
        raw_confidences = [graph.raw_confidence for graph in matched_graphs]
        scaler = fit_temperature_scaler(raw_confidences, correctness)

    final_graphs: List[GraphOutput] = []
    for row in records:
        text = str(row.get("text_report") or "")
        preprocessed = preprocess_text(text)
        graph = build_graph(
            case_id=row["case_id"],
            row=row,
            preprocessed=preprocessed,
            scaler=scaler,
            threshold=confidence_threshold,
        )
        final_graphs.append(graph)

    export_predictions_csv(final_graphs, out_dir / "predictions.csv")
    export_predictions_jsonl(final_graphs, out_dir / "predictions.jsonl")

    if gold_jsonl:
        gold_graphs = load_gold_jsonl(gold_jsonl)
        matched_graphs = [graph for graph in final_graphs if graph.case_id in gold_graphs]
        metrics = overall_metrics(matched_graphs, gold_graphs, baseline_violation_rate=None)
        save_metrics_json(metrics, out_dir / "metrics.json")

        confidences = [graph.calibrated_confidence for graph in matched_graphs]
        correctness = graph_level_correctness(matched_graphs, gold_graphs)
        plot_reliability_diagram(confidences, correctness, out_dir / "reliability_diagram.png")
        plot_risk_coverage_curve(metrics["curve"], out_dir / "risk_coverage_curve.png")


def main() -> None:
    parser = argparse.ArgumentParser(description="Rule-based Taglish ADR span-graph extractor.")
    parser.add_argument("--input-csv", required=True, help="Path to the source survey CSV file.")
    parser.add_argument("--output-dir", required=True, help="Directory where outputs will be saved.")
    parser.add_argument("--gold-jsonl", default=None, help="Optional gold annotation JSONL for evaluation.")
    parser.add_argument("--confidence-threshold", type=float, default=0.70, help="Selective prediction threshold.")
    args = parser.parse_args()

    run_pipeline(
        input_csv=args.input_csv,
        output_dir=args.output_dir,
        gold_jsonl=args.gold_jsonl,
        confidence_threshold=args.confidence_threshold,
    )


if __name__ == "__main__":
    main()