from __future__ import annotations

import re
from typing import Dict, List, Sequence, Tuple


REACTION_PATTERNS: List[Tuple[str, str]] = [
    # Exact high-frequency gold-aligned reaction phrases
    ("reaction_exact_sumakit_konti_tiyan", r"\b(?P<span>sumakit\s+ng\s+konti\s+ang\s+tiyan\s+ko)\b"),
    ("reaction_exact_sumakit_sikmura", r"\b(?P<span>sumakit\s+talaga\s+ang\s+sikmura\s+ko)\b"),
    ("reaction_exact_masakit_ulo", r"\b(?P<span>masakit\s+ang\s+ulo)\b"),
    ("reaction_exact_parang_umiikot", r"\b(?P<span>parang\s+umiikot)\b"),
    ("reaction_exact_sobrang_kati", r"\b(?P<span>sobrang\s+kati)\b"),
    ("reaction_exact_slight_nausea", r"\b(?P<span>slight\s+nausea)\b"),
    ("reaction_exact_rash_leeg_braso", r"\b(?P<span>rash\s+sa\s+leeg\s+at\s+braso)\b"),
    ("reaction_exact_antok_na_antok", r"\b(?P<span>antok\s+na\s+antok)\b"),
    ("reaction_exact_parang_nanghihina", r"\b(?P<span>parang\s+nanghihina)\b"),
    ("reaction_exact_mild_headache", r"\b(?P<span>mild\s+headache)\b"),
    ("reaction_exact_hirap_huminga", r"\b(?P<span>hirap\s+huminga)\b"),
    ("reaction_exact_nahirapan_ako_huminga", r"\b(?P<span>nahirapan\s+ako\s+huminga)\b"),
    ("reaction_exact_throat_tightness", r"\b(?P<span>throat\s+tightness)\b"),
    ("reaction_exact_nanikip_dibdib", r"\b(?P<span>nanikip\s+dibdib\s+ko)\b"),
    ("reaction_exact_namaga_labi", r"\b(?P<span>namaga\s+ang\s+labi)\b"),
    ("reaction_exact_parang_nahihirapan_ako", r"\b(?P<span>parang\s+nahihirapan\s+ako)\b"),

    # Single-token or compact reactions that appear often in the gold set
    ("reaction_lightheaded", r"\b(?P<span>lightheaded)\b"),
    ("reaction_dry_mouth", r"\b(?P<span>dry\s+mouth)\b"),
    ("reaction_palpitations", r"\b(?P<span>palpitations)\b"),
    ("reaction_masama_pakiramdam", r"\b(?P<span>masama\s+pakiramdam)\b"),
    ("reaction_pantal", r"\b(?P<span>pantal)\b"),
    ("reaction_namamantal", r"\b(?P<span>namamantal)\b"),
    ("reaction_hives", r"\b(?P<span>hives)\b"),
    ("reaction_nahilo", r"\b(?P<span>nahilo)\b"),
    ("reaction_hilo", r"\b(?P<span>hilo)\b"),
    ("reaction_pagod", r"\b(?P<span>pagod)\b"),
    ("reaction_nasusuka", r"\b(?P<span>nasusuka)\b"),
    ("reaction_loose_stool", r"\b(?P<span>loose\s+stool)\b"),
    ("reaction_cramps", r"\b(?P<span>cramps)\b"),
    ("reaction_nanginginig", r"\b(?P<span>nanginginig)\b"),
    ("reaction_dehydration", r"\b(?P<span>dehydration)\b"),
    ("reaction_sobrang_pagsusuka", r"\b(?P<span>sobrang\s+pagsusuka)\b"),

    # General fallbacks for broader coverage
    ("reaction_breathing_tl", r"\b(?:nahirapan(?:\s+ako)?\s+huminga|hirap(?:\s+ako)?\s+huminga)\b"),
    ("reaction_breathing_en", r"\b(?:difficulty\s+breathing|trouble\s+breathing|shortness\s+of\s+breath|throat\s+tightness)\b"),
    ("reaction_rash_en", r"\b(?:rash|rashes)\b"),
    ("reaction_rash_tl", r"\b(?:pantal|namamantal)\b"),
    ("reaction_itch", r"\b(?:kati|itch(?:ing|y)?)\b"),
    ("reaction_dizziness", r"\b(?:nahilo|hilo|lightheaded|dizzy|dizziness)\b"),
    ("reaction_nausea", r"\b(?:nausea|nasusuka|nagsuka|vomit(?:ing)?)\b"),
    ("reaction_pain_tl", r"\b(?:sumakit|masakit)\b"),
    ("reaction_pain_en", r"\b(?:pain|headache|stomach\s+pain)\b"),
    ("reaction_fever", r"\b(?:fever|lagnat)\b"),
    ("reaction_diarrhea", r"\b(?:diarrhea|pagtatae)\b"),
    ("reaction_fatigue", r"\b(?:pagod|fatigue)\b"),
]

EXPOSURE_CUE_PATTERNS: List[Tuple[str, str]] = [
    ("cue_uminom", r"\b(?:uminom|inom|take|took|using|used|nag[- ]?[a-zA-Z][\w-]*)\b"),
]

ONSET_PATTERNS: List[Tuple[str, str]] = [
    # Exact discourse-style onset cues from the gold set
    ("onset_pagkalipas_ng_konti", r"\b(?P<span>pagkalipas\s+ng\s+konti)\b"),
    ("onset_after_that", r"\b(?P<span>after\s+that)\b"),
    ("onset_mga_ilang_oras_after", r"\b(?P<span>mga\s+ilang\s+oras\s+after)\b"),
    ("onset_tapos_doon", r"\b(?P<span>tapos\s+(?:doon|dun))\b"),
    ("onset_hindi_naman_agad", r"\b(?P<span>hindi\s+naman\s+agad)\b"),
    ("onset_ang_sumunod", r"\b(?P<span>ang\s+sumunod)\b"),
    ("onset_maya_maya", r"\b(?P<span>maya-?maya)\b"),
    ("onset_hindi_nagtagal", r"\b(?P<span>hindi\s+nagtagal)\b"),
    ("onset_bigla", r"\b(?P<span>bigla)\b"),
    ("onset_later_on", r"\b(?P<span>later\s+on)\b"),
    ("onset_pagkaraan_nun", r"\b(?P<span>pagkaraan\s+nun)\b"),
    ("onset_pagdaan_ng_kaunti", r"\b(?P<span>pagdaan\s+ng\s+kaunti)\b"),
    ("onset_after_a_while", r"\b(?P<span>after\s+a\s+while)\b"),
    ("onset_eventually", r"\b(?P<span>eventually)\b"),

    # Conservative fallback elapsed-time cues
    ("onset_after_num", r"\b(?P<span>after\s+(?:mga\s+)?\d+\s*(?:hr|hrs|hour|hours|oras|min|mins|minute|minutes|minuto|minutos))\b"),
    ("onset_num_after", r"\b(?P<span>(?:mga\s+)?\d+\s*(?:hr|hrs|hour|hours|oras|min|mins|minute|minutes|minuto|minutos)\s+after)\b"),
]

ONSET_REGEXES = ONSET_PATTERNS

REPORTING_CHANNEL_PATTERNS: List[Tuple[str, str]] = [
    ("channel_health_worker", r"\b(?P<span>health\s+worker)\b"),
    ("channel_clinic_er", r"\b(?P<span>clinic\/ER)\b"),
]

NEGATION_PATTERNS = [
    r"\bwalang\b",
    r"\bwale\b",
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
            if "span" in match.re.groupindex and match.group("span") is not None:
                span_text = match.group("span")
                start = match.start("span")
                end = match.end("span")
            else:
                span_text = match.group(0)
                start = match.start()
                end = match.end()

            found.append(
                {
                    "text": span_text,
                    "start": start,
                    "end": end,
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