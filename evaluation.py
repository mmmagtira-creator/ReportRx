from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np
from sklearn.model_selection import KFold

from config import DEFAULT_NUM_ECE_BINS, DEFAULT_RANDOM_STATE
from schema import GraphOutput, tuple_set


@dataclass
class ExactCounts:
    tp: int
    fp: int
    fn: int

    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) else 0.0

    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) else 0.0

    def f1(self) -> float:
        p = self.precision()
        r = self.recall()
        return 2 * p * r / (p + r) if (p + r) else 0.0


def exact_match_counts(predicted: set, gold: set) -> ExactCounts:
    tp = len(predicted & gold)
    fp = len(predicted - gold)
    fn = len(gold - predicted)
    return ExactCounts(tp=tp, fp=fp, fn=fn)


def span_sets(graph: GraphOutput) -> Tuple[set, Dict[str, set]]:
    all_spans = set()
    by_label: Dict[str, set] = defaultdict(set)
    for span in graph.spans.values():
        item = (span.label, span.start, span.end)
        all_spans.add(item)
        by_label[span.label].add(item)
    return all_spans, by_label


def edge_sets(graph: GraphOutput) -> Tuple[set, Dict[str, set]]:
    all_edges = set()
    by_label: Dict[str, set] = defaultdict(set)
    for edge in graph.edges:
        item = edge.key(graph.spans)
        all_edges.add(item)
        by_label[edge.label].add(item)
    return all_edges, by_label


def micro_macro_scores(
    predictions: Sequence[GraphOutput],
    gold_graphs: Dict[str, GraphOutput],
    object_type: str = "span",
) -> Dict[str, float]:
    micro_tp = micro_fp = micro_fn = 0
    per_label_f1 = []

    for predicted in predictions:
        gold = gold_graphs[predicted.case_id]
        if object_type == "span":
            pred_all, pred_by_label = span_sets(predicted)
            gold_all, gold_by_label = span_sets(gold)
        elif object_type == "edge":
            pred_all, pred_by_label = edge_sets(predicted)
            gold_all, gold_by_label = edge_sets(gold)
        else:
            raise ValueError("object_type must be span or edge")

        counts = exact_match_counts(pred_all, gold_all)
        micro_tp += counts.tp
        micro_fp += counts.fp
        micro_fn += counts.fn

        for label in set(pred_by_label.keys()) | set(gold_by_label.keys()):
            per_label = exact_match_counts(
                pred_by_label.get(label, set()),
                gold_by_label.get(label, set()),
            )
            per_label_f1.append(per_label.f1())

    micro = ExactCounts(tp=micro_tp, fp=micro_fp, fn=micro_fn)
    macro_f1 = float(np.mean(per_label_f1)) if per_label_f1 else 0.0
    return {
        "micro_precision": micro.precision(),
        "micro_recall": micro.recall(),
        "micro_f1": micro.f1(),
        "macro_f1": macro_f1,
    }


def tuple_accuracy(predictions: Sequence[GraphOutput], gold_graphs: Dict[str, GraphOutput]) -> float:
    matches = 0
    total = 0
    for predicted in predictions:
        gold = gold_graphs[predicted.case_id]
        total += 1
        matches += int(tuple_set(predicted) == tuple_set(gold))
    return matches / total if total else 0.0


def edge_violation_rate(predictions: Sequence[GraphOutput]) -> float:
    invalid = 0
    total = 0
    for graph in predictions:
        total += len(graph.edges)
        invalid += sum(
            1
            for error in graph.validation_errors
            if error.startswith(("invalid_edge_type", "missing_span_reference", "unknown_edge_label"))
        )
    return invalid / total if total else 0.0


def graph_violation_rate(predictions: Sequence[GraphOutput]) -> float:
    if not predictions:
        return 0.0
    with_any_violation = sum(1 for graph in predictions if graph.validation_errors)
    return with_any_violation / len(predictions)


def violation_reduction(system_vr: float, baseline_vr: float) -> float:
    if baseline_vr <= 0:
        return 0.0
    return 1.0 - (system_vr / baseline_vr)


def expected_calibration_error(
    confidences: Sequence[float],
    correctness: Sequence[int],
    n_bins: int = DEFAULT_NUM_ECE_BINS,
) -> float:
    confidences = np.asarray(confidences, dtype=float)
    correctness = np.asarray(correctness, dtype=float)
    if len(confidences) == 0:
        return 0.0

    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for index in range(n_bins):
        lower = bins[index]
        upper = bins[index + 1]
        if index == n_bins - 1:
            mask = (confidences >= lower) & (confidences <= upper)
        else:
            mask = (confidences >= lower) & (confidences < upper)

        if not np.any(mask):
            continue
        bin_conf = confidences[mask].mean()
        bin_acc = correctness[mask].mean()
        ece += (mask.sum() / len(confidences)) * abs(bin_acc - bin_conf)
    return float(ece)


def brier_score(confidences: Sequence[float], labels: Sequence[int]) -> float:
    confidences = np.asarray(confidences, dtype=float)
    labels = np.asarray(labels, dtype=float)
    if len(confidences) == 0:
        return 0.0
    return float(np.mean((confidences - labels) ** 2))


def selective_prediction_curve(
    confidences: Sequence[float],
    correctness: Sequence[int],
    num_thresholds: int = 101,
) -> List[Dict[str, float]]:
    thresholds = np.linspace(0.0, 1.0, num_thresholds)
    confidences = np.asarray(confidences, dtype=float)
    correctness = np.asarray(correctness, dtype=float)
    curve = []
    total_items = len(confidences)
    if total_items == 0:
        return curve

    for threshold in thresholds:
        mask = confidences >= threshold
        coverage = mask.sum() / total_items
        if mask.sum() == 0:
            accuracy = 0.0
            risk = 1.0
        else:
            accuracy = correctness[mask].mean()
            risk = 1.0 - accuracy
        curve.append(
            {
                "threshold": float(threshold),
                "coverage": float(coverage),
                "risk": float(risk),
                "accuracy": float(accuracy),
            }
        )
    return curve


def aurc(curve: Sequence[Dict[str, float]]) -> float:
    if len(curve) < 2:
        return 0.0

    sorted_curve = sorted(curve, key=lambda item: item["coverage"])
    xs = np.array([item["coverage"] for item in sorted_curve], dtype=float)
    ys = np.array([item["risk"] for item in sorted_curve], dtype=float)

    if hasattr(np, "trapezoid"):
        return float(np.trapezoid(ys, xs))

    area = 0.0
    for i in range(1, len(xs)):
        width = xs[i] - xs[i - 1]
        height = (ys[i] + ys[i - 1]) / 2.0
        area += width * height

    return float(area)


def runtime_metrics(predictions: Sequence[GraphOutput]) -> Dict[str, float]:
    latencies = [graph.latency_ms for graph in predictions if graph.latency_ms is not None]
    total_tokens = sum(graph.processed_tokens for graph in predictions)
    total_seconds = sum((graph.latency_ms or 0.0) / 1000.0 for graph in predictions)

    return {
        "latency_p50_ms": float(np.percentile(latencies, 50)) if latencies else 0.0,
        "latency_p95_ms": float(np.percentile(latencies, 95)) if latencies else 0.0,
        "throughput_tokens_per_second": total_tokens / total_seconds if total_seconds > 0 else 0.0,
    }


def bootstrap_confidence_interval(
    values: Sequence[float],
    n_samples: int = 1000,
    seed: int = DEFAULT_RANDOM_STATE,
    alpha: float = 0.05,
) -> Dict[str, float]:
    values = np.asarray(list(values), dtype=float)
    if len(values) == 0:
        return {"mean": 0.0, "lower": 0.0, "upper": 0.0}
    rng = np.random.default_rng(seed)
    samples = []
    for _ in range(n_samples):
        indices = rng.integers(0, len(values), len(values))
        samples.append(float(values[indices].mean()))
    lower = float(np.quantile(samples, alpha / 2))
    upper = float(np.quantile(samples, 1 - alpha / 2))
    return {"mean": float(values.mean()), "lower": lower, "upper": upper}


def graph_level_correctness(
    predictions: Sequence[GraphOutput],
    gold_graphs: Dict[str, GraphOutput],
) -> List[int]:
    correctness = []
    for predicted in predictions:
        gold = gold_graphs[predicted.case_id]
        correctness.append(int(tuple_set(predicted) == tuple_set(gold)))
    return correctness


def overall_metrics(
    predictions: Sequence[GraphOutput],
    gold_graphs: Dict[str, GraphOutput],
    baseline_violation_rate: Optional[float] = None,
) -> Dict[str, object]:
    span_scores = micro_macro_scores(predictions, gold_graphs, object_type="span")
    edge_scores = micro_macro_scores(predictions, gold_graphs, object_type="edge")
    tuple_acc = tuple_accuracy(predictions, gold_graphs)

    correctness = graph_level_correctness(predictions, gold_graphs)
    confidences = [graph.calibrated_confidence for graph in predictions]

    edge_vr = edge_violation_rate(predictions)
    graph_vr = graph_violation_rate(predictions)
    curve = selective_prediction_curve(confidences, correctness)
    metrics = {
        "span": span_scores,
        "edge": edge_scores,
        "tuple_accuracy": tuple_acc,
        "violation_rate_edge": edge_vr,
        "violation_rate_graph": graph_vr,
        "violation_reduction": violation_reduction(edge_vr, baseline_violation_rate) if baseline_violation_rate is not None else None,
        "ece": expected_calibration_error(confidences, correctness),
        "brier_score": brier_score(confidences, correctness),
        "aurc": aurc(curve),
        "runtime": runtime_metrics(predictions),
        "curve": curve,
    }
    return metrics


def save_metrics_json(metrics: Dict[str, object], output_path: str | Path) -> None:
    output_path = Path(output_path)
    output_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")


def plot_reliability_diagram(
    confidences: Sequence[float],
    correctness: Sequence[int],
    output_path: str | Path,
    n_bins: int = DEFAULT_NUM_ECE_BINS,
) -> None:
    output_path = Path(output_path)
    confidences = np.asarray(confidences, dtype=float)
    correctness = np.asarray(correctness, dtype=float)
    bins = np.linspace(0.0, 1.0, n_bins + 1)

    bin_centers = []
    bin_accuracies = []
    for index in range(n_bins):
        lower = bins[index]
        upper = bins[index + 1]
        mask = (confidences >= lower) & (confidences < upper if index < n_bins - 1 else confidences <= upper)
        if not np.any(mask):
            continue
        bin_centers.append((lower + upper) / 2)
        bin_accuracies.append(correctness[mask].mean())

    plt.figure(figsize=(6, 6))
    plt.plot([0, 1], [0, 1])
    plt.bar(bin_centers, bin_accuracies, width=1 / n_bins, align="center", alpha=0.7)
    plt.xlabel("Confidence")
    plt.ylabel("Accuracy")
    plt.title("Reliability Diagram")
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def plot_risk_coverage_curve(curve: Sequence[Dict[str, float]], output_path: str | Path) -> None:
    output_path = Path(output_path)
    coverages = [item["coverage"] for item in curve]
    risks = [item["risk"] for item in curve]

    plt.figure(figsize=(7, 5))
    plt.plot(coverages, risks)
    plt.xlabel("Coverage")
    plt.ylabel("Risk")
    plt.title("Risk-Coverage Curve")
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()


def kfold_indices(n_items: int, n_splits: int = 5, seed: int = DEFAULT_RANDOM_STATE) -> Iterable[Tuple[np.ndarray, np.ndarray]]:
    splitter = KFold(n_splits=n_splits, shuffle=True, random_state=seed)
    indices = np.arange(n_items)
    for train_index, test_index in splitter.split(indices):
        yield train_index, test_index