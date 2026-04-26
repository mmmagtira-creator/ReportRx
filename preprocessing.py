from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, List, Tuple

from config import (
    ENGLISH_HINT_PREFIXES,
    PERSONAL_IDENTIFIER_PATTERNS,
    SHORTHAND_MAP,
    SYMTOM_TRIGGER_WORDS,
    TAGALOG_CUES,
    TAGALOG_PREFIXES,
)
from schema import Token
from stopwords_utils import load_english_stopwords, load_tagalog_stopwords


TOKEN_PATTERN = re.compile(r"\w+(?:-\w+)*|[^\w\s]", flags=re.UNICODE)
MULTISPACE_PATTERN = re.compile(r"\s+")
REPEATED_PUNCT_PATTERN = re.compile(r"([!?.,])\1+")
LETTER_STRETCH_PATTERN = re.compile(r"([A-Za-z])\1{2,}")


@dataclass
class PreprocessedText:
    raw_text: str
    normalized_text: str
    tokens: List[Token]
    notes: List[str]


def deidentify_text(text: str) -> str:
    clean_text = text
    for pattern in PERSONAL_IDENTIFIER_PATTERNS:
        clean_text = re.sub(pattern, "[REDACTED]", clean_text, flags=re.IGNORECASE)
    return clean_text


def normalize_text(text: str) -> Tuple[str, List[str]]:
    notes: List[str] = []
    clean = unicodedata.normalize("NFKC", text)
    if clean != text:
        notes.append("unicode_normalized")

    clean = REPEATED_PUNCT_PATTERN.sub(r"\1", clean)
    clean = MULTISPACE_PATTERN.sub(" ", clean).strip()
    clean = LETTER_STRETCH_PATTERN.sub(r"\1", clean)

    parts = []
    for chunk in clean.split():
        parts.append(SHORTHAND_MAP.get(chunk.lower(), chunk))
    normalized = " ".join(parts)

    return normalized, notes


def detect_language(token_text: str, english_stopwords: set[str], tagalog_stopwords: set[str]) -> str:
    text = token_text.lower()

    if re.fullmatch(r"[^\w]+", text):
        return "OTHER"

    if text in tagalog_stopwords or text in TAGALOG_CUES:
        return "TL"

    if text in english_stopwords:
        return "EN"

    if any(text.startswith(prefix) and len(text) > len(prefix) + 2 for prefix in TAGALOG_PREFIXES):
        return "TL"

    if any(text.startswith(prefix) and len(text) > len(prefix) + 2 for prefix in ENGLISH_HINT_PREFIXES):
        return "EN"

    if text in SYMTOM_TRIGGER_WORDS:
        if text in {"lightheaded", "nausea", "rash", "rashes", "itch", "itching", "pain", "tightness", "breathing"}:
            return "EN"
        return "TL"

    if re.search(r"[a-z]", text) and not re.search(r"[à-ÿ]", text):
        return "EN"

    return "OTHER"


def tokenize_with_offsets(normalized_text: str) -> List[Token]:
    english_stopwords = load_english_stopwords()
    tagalog_stopwords = load_tagalog_stopwords()
    tokens: List[Token] = []

    for match in TOKEN_PATTERN.finditer(normalized_text):
        original = match.group(0)
        lang = detect_language(original, english_stopwords, tagalog_stopwords)
        tokens.append(
            Token(
                text=original,
                start=match.start(),
                end=match.end(),
                lang=lang,
                normalized=original.lower(),
            )
        )
    return tokens


def preprocess_text(text: str) -> PreprocessedText:
    deidentified = deidentify_text(text)
    normalized, notes = normalize_text(deidentified)
    tokens = tokenize_with_offsets(normalized)
    return PreprocessedText(
        raw_text=text,
        normalized_text=normalized,
        tokens=tokens,
        notes=notes,
    )


def code_mix_ratio(tokens: List[Token]) -> float:
    language_tokens = [token for token in tokens if token.lang in {"EN", "TL"}]
    if not language_tokens:
        return 0.0
    en_count = sum(token.lang == "EN" for token in language_tokens)
    tl_count = sum(token.lang == "TL" for token in language_tokens)
    return min(en_count, tl_count) / max(1, len(language_tokens))


def token_table(tokens: List[Token]) -> List[Dict[str, str | int]]:
    return [
        {
            "text": token.text,
            "start": token.start,
            "end": token.end,
            "lang": token.lang,
            "normalized": token.normalized,
        }
        for token in tokens
    ]