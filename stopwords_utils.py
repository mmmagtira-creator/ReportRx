from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Set

import nltk

from config import TAGALOG_STOPWORDS_PATH


FALLBACK_ENGLISH_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "but", "by", "for",
    "from", "had", "has", "have", "he", "her", "hers", "him", "his", "i", "in",
    "is", "it", "its", "me", "my", "of", "on", "or", "our", "ours", "she", "that",
    "the", "their", "them", "they", "this", "to", "was", "we", "were", "with", "you",
    "your", "yours",
}


@lru_cache(maxsize=1)
def load_english_stopwords() -> Set[str]:
    try:
        from nltk.corpus import stopwords as nltk_stopwords
        return set(nltk_stopwords.words("english"))
    except LookupError:
        try:
            nltk.download("stopwords", quiet=True)
            from nltk.corpus import stopwords as nltk_stopwords
            return set(nltk_stopwords.words("english"))
        except Exception:
            return set(FALLBACK_ENGLISH_STOPWORDS)
    except Exception:
        return set(FALLBACK_ENGLISH_STOPWORDS)


@lru_cache(maxsize=1)
def load_tagalog_stopwords(path: str | None = None) -> Set[str]:
    stop_path = Path(path) if path else TAGALOG_STOPWORDS_PATH
    if not stop_path.exists():
        raise FileNotFoundError(f"Tagalog stopword file not found: {stop_path}")
    words = {
        line.strip().lower()
        for line in stop_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    return words


def combined_stopwords() -> Set[str]:
    return load_english_stopwords().union(load_tagalog_stopwords())


PROTECTED_CUES = {
    "after", "before", "oras", "hour", "hours", "kagabi", "kanina", "kahapon",
    "morning", "night", "umaga", "hapon", "gabi", "tiyan", "sikmura", "hilo",
    "pantal", "kati", "rash", "nausea", "vomit", "lagnat", "ubo", "sakit",
}