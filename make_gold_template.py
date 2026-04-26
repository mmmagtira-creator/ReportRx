from __future__ import annotations

import argparse
import json
from pathlib import Path

from io_utils import load_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a starter gold annotation file from the survey CSV.")
    parser.add_argument("--input-csv", required=True, help="Path to the raw survey CSV.")
    parser.add_argument("--output-jsonl", required=True, help="Path to the output annotation starter JSONL.")
    args = parser.parse_args()

    df = load_dataset(args.input_csv)
    output_path = Path(args.output_jsonl)

    with output_path.open("w", encoding="utf-8") as handle:
        for row in df.to_dict(orient="records"):
            item = {
                "case_id": row["case_id"],
                "raw_text": row.get("text_report", ""),
                "normalized_text": row.get("text_report", ""),
                "spans": {},
                "edges": [],
                "notes": "Fill spans with exact character offsets and add typed edges.",
            }
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()