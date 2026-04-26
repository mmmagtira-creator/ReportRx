from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List

import pandas as pd

from config import COLUMN_ALIASES
from schema import GraphOutput


def find_column(df: pd.DataFrame, aliases: List[str]) -> str | None:
    for alias in aliases:
        if alias in df.columns:
            return alias
    return None


def read_csv_robust(csv_path: str | Path) -> pd.DataFrame:
    csv_path = Path(csv_path)

    encodings_to_try = [
        "utf-8",
        "utf-8-sig",
        "cp1252",
        "latin1",
    ]

    last_error = None
    for encoding in encodings_to_try:
        try:
            return pd.read_csv(csv_path, encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
            continue

    try:
        return pd.read_csv(csv_path, encoding="latin1", engine="python")
    except Exception as exc:
        last_error = exc

    raise RuntimeError(
        f"Failed to read CSV file: {csv_path}. "
        f"Tried encodings: {', '.join(encodings_to_try)} and latin1 with python engine."
    ) from last_error


def load_dataset(csv_path: str | Path) -> pd.DataFrame:
    df = read_csv_robust(csv_path)

    normalized = {}
    for internal_name, aliases in COLUMN_ALIASES.items():
        actual = find_column(df, aliases)
        if actual is not None:
            normalized[internal_name] = df[actual]
        else:
            normalized[internal_name] = pd.Series([None] * len(df), index=df.index)

    out = pd.DataFrame(normalized)

    if "case_id" not in out.columns:
        out.insert(0, "case_id", [f"case_{i + 1:05d}" for i in range(len(out))])

    if "reporting_channel" in out.columns:
        out["reporting_channel"] = out["reporting_channel"].fillna("")
    if "date_logged" in out.columns:
        out["date_logged"] = out["date_logged"].fillna("")
    if "text_report" in out.columns:
        out["text_report"] = out["text_report"].fillna("").astype(str)

    return out


def export_predictions_csv(graphs: Iterable[GraphOutput], output_path: str | Path) -> None:
    rows = []
    for graph in graphs:
        exposures = [span.text for span in graph.spans.values() if span.label == "Exposure"]
        reactions = [span.text for span in graph.spans.values() if span.label == "Reaction"]
        onsets = [span.text for span in graph.spans.values() if span.label == "Onset"]

        rows.append(
            {
                "case_id": graph.case_id,
                "text_report": graph.raw_text,
                "normalized_text": graph.normalized_text,
                "drug_mention": " | ".join(exposures),
                "reaction_mention": " | ".join(reactions),
                "onset": " | ".join(onsets),
                "confidence": graph.calibrated_confidence,
                "raw_confidence": graph.raw_confidence,
                "status": graph.status,
                "validation_errors": " | ".join(graph.validation_errors),
                "latency_ms": graph.latency_ms,
                "processed_tokens": graph.processed_tokens,
            }
        )

    pd.DataFrame(rows).to_csv(output_path, index=False, encoding="utf-8-sig")


def export_predictions_jsonl(graphs: Iterable[GraphOutput], output_path: str | Path) -> None:
    output_path = Path(output_path)
    with output_path.open("w", encoding="utf-8") as handle:
        for graph in graphs:
            handle.write(json.dumps(graph.as_dict(), ensure_ascii=False) + "\n")


def load_gold_graphs(jsonl_path: str | Path) -> Dict[str, dict]:
    gold = {}
    with Path(jsonl_path).open("r", encoding="utf-8") as handle:
        for line in handle:
            item = json.loads(line)
            gold[item["case_id"]] = item
    return gold