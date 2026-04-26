from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import pandas as pd

from config import COLUMN_ALIASES
from schema import GraphOutput


def normalize_header(text: str) -> str:
    text = unicodedata.normalize("NFKC", str(text))
    text = text.replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip().lower()
    text = text.replace("“", '"').replace("”", '"').replace("’", "'")
    return text


def find_column(df: pd.DataFrame, aliases: List[str]) -> str | None:
    exact_map = {col: col for col in df.columns}
    normalized_map = {normalize_header(col): col for col in df.columns}

    for alias in aliases:
        if alias in exact_map:
            return exact_map[alias]

    for alias in aliases:
        normalized_alias = normalize_header(alias)
        if normalized_alias in normalized_map:
            return normalized_map[normalized_alias]

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


def debug_column_mapping(df: pd.DataFrame) -> List[Tuple[str, str | None]]:
    mappings: List[Tuple[str, str | None]] = []
    for internal_name, aliases in COLUMN_ALIASES.items():
        matched = find_column(df, aliases)
        mappings.append((internal_name, matched))
    return mappings


def load_dataset(csv_path: str | Path, verbose: bool = False) -> pd.DataFrame:
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

    if verbose:
        print("\nDetected column mapping:")
        for internal_name, matched in debug_column_mapping(df):
            print(f"  {internal_name:20s} -> {matched}")
        print(f"\nLoaded rows: {len(out)}")
        if "text_report" in out.columns:
            non_empty = (out["text_report"].str.strip() != "").sum()
            print(f"Non-empty text_report rows: {non_empty}")

    return out


def export_predictions_csv(graphs: Iterable[GraphOutput], output_path: str | Path) -> None:
    rows = []
    for graph in graphs:
        exposures = [span.text for span in graph.spans.values() if span.label == "Exposure"]
        reactions = [span.text for span in graph.spans.values() if span.label == "Reaction"]
        onsets = [span.text for span in graph.spans.values() if span.label == "Onset"]
        channels = [span.text for span in graph.spans.values() if span.label == "ReportingChannel"]

        rows.append(
            {
                "case_id": graph.case_id,
                "text_report": graph.raw_text,
                "normalized_text": graph.normalized_text,
                "drug_mention": " | ".join(exposures),
                "reaction_mention": " | ".join(reactions),
                "onset": " | ".join(onsets),
                "reporting_channel": " | ".join(channels),
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