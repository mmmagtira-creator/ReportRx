"""Analytics helpers for ReportRx dashboard and report generation."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Tuple

from app.db import get_all_reports, get_reports

VIEW_TO_STATUS = {
    "all": None,
    "accepted": "Accepted",
    "needs_review": "Needs Review",
}

VIEW_LABELS = {
    "all": "All",
    "accepted": "Accepted",
    "needs_review": "Needs Review",
}


def _canonical_name(value: str) -> str:
    return " ".join(value.strip().split()).lower()


def _split_mentions(value: str) -> List[str]:
    return [
        part.strip()
        for part in str(value or "").split("|")
        if part.strip()
    ]


def _dedupe_mentions(values: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen = set()
    for value in values:
        key = _canonical_name(value)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(value.strip())
    return result


def _sorted_counter(counter: Counter, labels: Dict[str, str]) -> List[Dict[str, int | str]]:
    return [
        {"name": labels[key], "count": count}
        for key, count in sorted(counter.items(), key=lambda item: (-item[1], labels[item[0]].lower()))
    ]


def _top_chart_items(items: List[Dict[str, int | str]], limit: int = 6) -> List[Dict[str, int | str]]:
    if len(items) <= limit:
        return items
    top_items = items[:limit]
    other_count = sum(int(item["count"]) for item in items[limit:])
    if other_count > 0:
        top_items.append({"name": "Others", "count": other_count})
    return top_items


def get_view_label(view: str) -> str:
    if view not in VIEW_LABELS:
        raise ValueError("Invalid analytics view")
    return VIEW_LABELS[view]


def get_reports_for_view(view: str) -> List[Dict]:
    if view not in VIEW_TO_STATUS:
        raise ValueError("Invalid analytics view")
    status = VIEW_TO_STATUS[view]
    if status is None:
        return get_all_reports()
    return get_reports(status=status)


def build_analytics_summary(view: str) -> Dict:
    rows = get_reports_for_view(view)

    medicine_counter: Counter = Counter()
    reaction_counter: Counter = Counter()
    pair_counter: Counter = Counter()

    medicine_labels: Dict[str, str] = {}
    reaction_labels: Dict[str, str] = {}

    for row in rows:
        medicines = _dedupe_mentions(_split_mentions(row.get("drug_mention", "")))
        reactions = _dedupe_mentions(_split_mentions(row.get("reaction_mention", "")))

        canonical_medicines: List[Tuple[str, str]] = []
        canonical_reactions: List[Tuple[str, str]] = []

        for medicine in medicines:
            key = _canonical_name(medicine)
            if not key:
                continue
            medicine_labels.setdefault(key, medicine)
            medicine_counter[key] += 1
            canonical_medicines.append((key, medicine_labels[key]))

        for reaction in reactions:
            key = _canonical_name(reaction)
            if not key:
                continue
            reaction_labels.setdefault(key, reaction)
            reaction_counter[key] += 1
            canonical_reactions.append((key, reaction_labels[key]))

        for medicine_key, _ in canonical_medicines:
            for reaction_key, _ in canonical_reactions:
                pair_counter[(medicine_key, reaction_key)] += 1

    medicine_table = _sorted_counter(medicine_counter, medicine_labels)
    reaction_table = _sorted_counter(reaction_counter, reaction_labels)

    per_drug_pairs: Dict[str, List[Tuple[str, int]]] = defaultdict(list)
    for (medicine_key, reaction_key), count in pair_counter.items():
        per_drug_pairs[medicine_key].append((reaction_key, count))

    association_table: List[Dict[str, int | str]] = []
    strongest_pair_chart: List[Dict[str, int | str]] = []

    sorted_drug_keys = sorted(
        per_drug_pairs.keys(),
        key=lambda key: (
            -sum(count for _, count in per_drug_pairs[key]),
            medicine_labels[key].lower(),
        ),
    )

    for medicine_key in sorted_drug_keys:
        ranked_pairs = sorted(
            per_drug_pairs[medicine_key],
            key=lambda item: (-item[1], reaction_labels[item[0]].lower()),
        )
        top_reaction_key, top_count = ranked_pairs[0]
        association_table.append(
            {
                "drug_name": medicine_labels[medicine_key],
                "top_adr": reaction_labels[top_reaction_key],
                "count": top_count,
            }
        )
        strongest_pair_chart.append(
            {
                "drug_name": medicine_labels[medicine_key],
                "top_adr": reaction_labels[top_reaction_key],
                "count": top_count,
            }
        )

    medicine_chart = _top_chart_items(medicine_table)
    reaction_chart = _top_chart_items(reaction_table)
    association_chart = strongest_pair_chart[:8]

    return {
        "view": view,
        "view_label": get_view_label(view),
        "filtered_report_count": len(rows),
        "has_data": bool(medicine_table or reaction_table or association_table),
        "medicine_chart": medicine_chart,
        "medicine_table": medicine_table,
        "reaction_chart": reaction_chart,
        "reaction_table": reaction_table,
        "association_chart": association_chart,
        "association_table": association_table,
    }
