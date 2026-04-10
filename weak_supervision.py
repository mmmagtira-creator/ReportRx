from __future__ import annotations

import math
import re
from typing import Dict, List

from config import DEFAULT_SOURCE_CHANNEL


EXAMPLE_PATTERN = re.compile(
    r"^(?P<base>.*?)\(\s*example\s*:\s*(?P<examples>.*?)\s*\)\s*$",
    flags=re.IGNORECASE,
)


def is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True

    text = str(value).strip()
    return text == "" or text.lower() in {"nan", "none", "null"}


def split_top_level_commas(text: str) -> List[str]:
    items: List[str] = []
    buffer: List[str] = []
    depth = 0

    for char in text:
        if char == "(":
            depth += 1
            buffer.append(char)
        elif char == ")":
            depth = max(0, depth - 1)
            buffer.append(char)
        elif char == "," and depth == 0:
            item = "".join(buffer).strip()
            if item:
                items.append(item)
            buffer = []
        else:
            buffer.append(char)

    tail = "".join(buffer).strip()
    if tail:
        items.append(tail)

    return items


def parse_checkbox_list(value: object) -> List[str]:
    if is_missing(value):
        return []
    return split_top_level_commas(str(value).strip())


def clean_alias(text: str) -> str:
    cleaned = text.strip().lower()
    cleaned = re.sub(r"^other\s*:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip(" \t\r\n,;:/")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def extract_medicine_aliases(item: str) -> List[str]:
    text = clean_alias(item)
    if not text:
        return []

    aliases: List[str] = []
    match = EXAMPLE_PATTERN.match(text)

    if match:
        base = clean_alias(match.group("base"))
        if base:
            aliases.append(base)

        raw_examples = match.group("examples")
        example_parts = re.split(r"[,/;]|\bor\b", raw_examples, flags=re.IGNORECASE)
        for example in example_parts:
            alias = clean_alias(example)
            if alias:
                aliases.append(alias)
    else:
        aliases.append(text)

    deduplicated: List[str] = []
    seen = set()
    for alias in aliases:
        if alias not in seen:
            seen.add(alias)
            deduplicated.append(alias)

    return deduplicated


def medicine_candidates_from_row(row: Dict[str, object]) -> List[str]:
    candidates: List[str] = []

    for item in parse_checkbox_list(row.get("medicine_checkbox")):
        candidates.extend(extract_medicine_aliases(item))

    other_medications = row.get("other_medications")
    if not is_missing(other_medications):
        for part in re.split(r"[,/;]|\band\b", str(other_medications), flags=re.IGNORECASE):
            alias = clean_alias(part)
            if alias:
                candidates.append(alias)

    deduplicated: List[str] = []
    seen = set()
    for candidate in candidates:
        if candidate not in seen:
            seen.add(candidate)
            deduplicated.append(candidate)

    return sorted(deduplicated)


def reporting_channel_from_row(row: Dict[str, object]) -> str:
    value = row.get("reporting_channel")
    if is_missing(value):
        return DEFAULT_SOURCE_CHANNEL
    return str(value).strip().lower()


def weak_reaction_presence_label(row: Dict[str, object]) -> int:
    text_value = row.get("text_report")
    text = "" if is_missing(text_value) else str(text_value).lower()

    triggers = [
        "sumakit",
        "nahilo",
        "nagsuka",
        "vomit",
        "vomiting",
        "rash",
        "pantal",
        "kati",
        "lagnat",
        "fever",
        "nasusuka",
        "nausea",
        "diarrhea",
        "pagtatae",
        "hirap huminga",
        "throat tightness",
        "dry mouth",
        "lightheaded",
    ]
    return int(any(trigger in text for trigger in triggers))