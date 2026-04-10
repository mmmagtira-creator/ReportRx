from __future__ import annotations

import re
from typing import Dict, List, Sequence, Tuple


REACTION_PATTERNS: List[Tuple[str, str]] = [
    ("reaction_breathing_tl", r"\b(?:nahirapan(?:\s+ako)?\s+huminga|hirap(?:\s+ako)?\s+huminga)\b"),
    ("reaction_breathing_en", r"\b(?:difficulty breathing|trouble breathing|shortness of breath|throat tightness)\b"),
    ("reaction_rash_en", r"\b(?:rash|rashes)\b"),
    ("reaction_rash_tl", r"\b(?:pantal|namamantal)\b"),
    ("reaction_itch", r"\b(?:kati|itch(?:ing|y)?)\b"),
    ("reaction_dizziness", r"\b(?:nahilo|hilo|lightheaded|dizzy|dizziness)\b"),
    ("reaction_nausea", r"\b(?:nausea|nasusuka|nagsuka|vomit(?:ing)?)\b"),
    ("reaction_pain_tl", r"\b(?:sumakit|masakit)\b"),
    ("reaction_pain_en", r"\b(?:pain|headache|stomach pain)\b"),
    ("reaction_fever", r"\b(?:fever|lagnat)\b"),
    ("reaction_dry_mouth", r"\b(?:dry mouth)\b"),
    ("reaction_diarrhea", r"\b(?:diarrhea|pagtatae)\b"),
    ("reaction_fatigue", r"\b(?:pagod|fatigue)\b"),
]

EXPOSURE_CUE_PATTERNS: List[Tuple[str, str]] = [
    ("cue_uminom", r"\b(?:uminom|inom|take|took|using|used|nag[- ]?[a-zA-Z][\w-]*)\b"),
]

ONSET_PATTERNS: List[Tuple[str, str]] = [
    ("onset_elapsed_time", r"\b(?:after|after about|after around|pagkalipas(?:\s+ng)?|makalipas(?:\s+ang)?)\s+\d+\s*(?:hr|hrs|hour|hours|oras|minute|minutes|minuto|minutos)\b"),
    ("onset_bigla", r"\bbigla\b"),
    ("onset_later_on", r"\blater\s+on\b"),
    ("onset_eventually", r"\beventually\b"),
    ("onset_after_that", r"\bafter\s+that\b"),
    ("onset_maya_maya", r"\bmaya-?maya\b"),
    ("onset_hindi_naman_agad", r"\bhindi\s+naman\s+agad\b"),
    ("onset_ang_sumunod", r"\bang\s+sumunod\b"),
    ("onset_tapos_doon", r"\btapos\s+(?:doon|dun)\b"),
    ("onset_saka_doon", r"\bsaka\s+(?:doon|dun)\b"),
    ("onset_then_felt", r"\b(?:then|doon|saka)\s+(?:ko\s+)?(?:naramdaman|felt)\b"),
    ("onset_right_after", r"\bright\s+after\b"),
    ("onset_immediately_after", r"\bimmediately\s+after\b"),
]

ONSET_REGEXES = ONSET_PATTERNS

NEGATION_PATTERNS = [
    r"\bwalang\b",
    r"\bno\b",
    r"\bnot\b",
    r"\bhindi\b",
    r"\bnone\b",
    r"\bnever\b",
]


def find_pattern_spans(text: str, compiled_patterns: Sequence[Tuple[str, str]]) -> List[Dict[str, object]]:
    found: List[Dict[str, object]] = []
    for rule_name, pattern in compiled_patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            found.append(
                {
                    "text": match.group(0),
                    "start": match.start(),
                    "end": match.end(),
                    "rule": rule_name,
                }
            )
    return found


def sentence_window(text: str, start: int, end: int, window: int = 60) -> str:
    left = max(0, start - window)
    right = min(len(text), end + window)
    return text[left:right]


def has_local_negation(text: str, start: int, end: int) -> bool:
    window = sentence_window(text, start, end)
    return any(re.search(pattern, window, flags=re.IGNORECASE) for pattern in NEGATION_PATTERNS)