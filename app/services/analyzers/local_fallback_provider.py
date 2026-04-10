"""Local primary provider – hybrid of thesis reaction/onset model + curated drug matching."""

from __future__ import annotations

import logging
import re
import sys
from typing import List, Optional, Tuple

from app.config import THESIS_CODE_ROOT
from app.services.analyzers.base import AnalysisResult, BaseAnalyzer

logger = logging.getLogger("reportrx.local")

# Make sure the thesis root is importable
_thesis_root_str = str(THESIS_CODE_ROOT)
if _thesis_root_str not in sys.path:
    sys.path.insert(0, _thesis_root_str)

# ── Curated pharmaceutical drug list ────────────────────────────────────
# Brand names common in PH pharmacovigilance + generics from thesis data
_DRUG_LIST: List[Tuple[str, float]] = [
    # (pattern, match_confidence)
    # Generic names
    ("amoxicillin", 0.95),
    ("paracetamol", 0.95),
    ("mefenamic acid", 0.95),
    ("cetirizine", 0.95),
    ("ibuprofen", 0.95),
    ("metformin", 0.92),
    ("amlodipine", 0.92),
    ("losartan", 0.92),
    ("omeprazole", 0.92),
    ("aspirin", 0.92),
    ("loperamide", 0.90),
    ("salbutamol", 0.90),
    ("azithromycin", 0.90),
    ("ciprofloxacin", 0.90),
    ("metoprolol", 0.90),
    ("prednisone", 0.90),
    ("doxycycline", 0.90),
    ("tramadol", 0.90),
    ("clindamycin", 0.90),
    ("diclofenac", 0.90),
    ("naproxen", 0.90),
    ("ranitidine", 0.90),
    ("clopidogrel", 0.90),
    ("atorvastatin", 0.90),
    ("simvastatin", 0.90),
    ("carbocisteine", 0.90),
    ("phenylephrine", 0.88),
    ("chlorphenamine", 0.88),
    ("diphenhydramine", 0.88),
    ("hydroxychloroquine", 0.88),
    ("co-amoxiclav", 0.90),
    # Brand names (PH-common)
    ("biogesic", 0.93),
    ("neozep", 0.93),
    ("bioflu", 0.93),
    ("solmux", 0.93),
    ("decolgen", 0.93),
    ("kremil-s", 0.90),
    ("diatabs", 0.90),
    ("medicol", 0.93),
    ("alaxan", 0.93),
    ("dolfenal", 0.93),
    ("flanax", 0.90),
    ("ponstan", 0.90),
    ("tempra", 0.90),
    ("advil", 0.90),
    ("tylenol", 0.90),
    ("robitussin", 0.88),
    ("tuseran", 0.88),
    ("lagundi", 0.80),
    ("ascof", 0.85),
    ("cough syrup", 0.80),
    ("lozenges", 0.75),
    ("sinovac", 0.92),
    ("pfizer", 0.88),
    ("moderna", 0.88),
    ("astrazeneca", 0.88),
    ("janssen", 0.88),
]

# ── Reaction terms (Taglish + English) ──────────────────────────────────
_REACTION_LIST: List[Tuple[str, float]] = [
    # Tagalog
    ("nahilo", 0.90), ("hilo", 0.85), ("sumakit", 0.90),
    ("sumakit ang ulo", 0.95), ("sumakit ang tiyan", 0.95),
    ("sumakit ang katawan", 0.92), ("nasusuka", 0.92),
    ("nagsuka", 0.92), ("pantal", 0.90), ("nagka-pantal", 0.92),
    ("kati", 0.85), ("makati", 0.85), ("nagka-rash", 0.92),
    ("lagnat", 0.90), ("nilagnat", 0.90), ("pagtatae", 0.90),
    ("hirap huminga", 0.95), ("namamaga", 0.88), ("manhid", 0.85),
    ("nanghihina", 0.88), ("pagod", 0.78), ("pananakit", 0.88),
    ("pamamaga", 0.88), ("pamumula", 0.85), ("pamamanhid", 0.88),
    ("nangingitim", 0.85), ("ubo", 0.78), ("sipon", 0.75),
    # English
    ("rash", 0.90), ("nausea", 0.90), ("vomiting", 0.92),
    ("headache", 0.90), ("dizziness", 0.90), ("fever", 0.85),
    ("diarrhea", 0.90), ("lightheaded", 0.88),
    ("dry mouth", 0.88), ("hives", 0.90), ("itching", 0.88),
    ("difficulty breathing", 0.95), ("swelling", 0.88),
    ("abdominal pain", 0.92), ("chest pain", 0.95),
    ("throat tightness", 0.95), ("fatigue", 0.80),
    ("drowsiness", 0.82), ("insomnia", 0.82),
    ("numbness", 0.85), ("tingling", 0.82),
    ("loose stool", 0.85), ("cramps", 0.82),
    ("blurred vision", 0.88), ("palpitations", 0.90),
]

# ── Onset patterns ──────────────────────────────────────────────────────
_ONSET_PATTERNS = [
    (r"maya-?maya", 0.90), (r"hindi naman agad", 0.85),
    (r"ang sumunod", 0.80), (r"tapos\s+doon", 0.80),
    (r"later\s+on", 0.88), (r"later", 0.80),
    (r"bigla", 0.85), (r"biglaan", 0.88),
    (r"eventually", 0.82), (r"after\s+a\s+while", 0.85),
    (r"hindi\s+nagtagal", 0.85), (r"pagkatapos", 0.80),
    (r"kinabukasan", 0.82), (r"after\s+\d+\s+(?:hours?|mins?|minutes?|days?)", 0.90),
    (r"within\s+\d+\s+(?:hours?|mins?|minutes?|days?)", 0.90),
    (r"noong\s+gabi", 0.80), (r"kagabi", 0.78),
]


class LocalFallbackProvider(BaseAnalyzer):
    """
    Hybrid local provider:
    - Drug detection via curated pharmaceutical list (avoids false positives like 'tubig')
    - Reaction + onset detection via thesis model patterns with keyword fallback
    - Granular confidence computed from individual match quality
    """

    async def analyze(self, text: str) -> Optional[AnalysisResult]:
        try:
            return self._extract(text)
        except Exception as exc:
            logger.debug("Local extractor failed: %s", exc)
            return None

    def _extract(self, text: str) -> AnalysisResult:
        # ── 1. Drug matching (curated list only) ────────────────────
        drugs, drug_confs = self._match_drugs(text)

        # ── 2. Reaction detection (thesis model first, keyword fallback) ─
        reactions, reaction_confs = self._match_reactions(text)

        # ── 3. Onset detection ──────────────────────────────────────
        onsets, onset_confs = self._match_onsets(text)

        # ── 4. Compute granular confidence ──────────────────────────
        raw_confidence = self._compute_confidence(
            drug_confs, reaction_confs, onset_confs,
            has_drugs=len(drugs) > 0,
            has_reactions=len(reactions) > 0,
            has_onsets=len(onsets) > 0,
        )

        return AnalysisResult(
            drug_mention=" | ".join(drugs),
            reaction_mention=" | ".join(reactions),
            onset=" | ".join(onsets) if onsets else "",
            raw_confidence=round(raw_confidence, 6),
        )

    # ── Drug matching ───────────────────────────────────────────────────
    @staticmethod
    def _match_drugs(text: str) -> Tuple[List[str], List[float]]:
        text_lower = text.lower()
        found: List[str] = []
        confs: List[float] = []
        seen: set = set()
        for drug, conf in _DRUG_LIST:
            if drug in text_lower and drug not in seen:
                seen.add(drug)
                # Use the original-case version from the text
                idx = text_lower.index(drug)
                original = text[idx : idx + len(drug)]
                found.append(original)
                confs.append(conf)
        return found, confs

    # ── Reaction matching (thesis model + keywords) ─────────────────────
    def _match_reactions(self, text: str) -> Tuple[List[str], List[float]]:
        # Try thesis model first
        try:
            return self._thesis_reactions(text)
        except Exception:
            pass

        # Keyword fallback
        text_lower = text.lower()
        found: List[str] = []
        confs: List[float] = []
        seen: set = set()
        for rxn, conf in _REACTION_LIST:
            if rxn in text_lower and rxn not in seen:
                seen.add(rxn)
                found.append(rxn)
                confs.append(conf)
        return found, confs

    @staticmethod
    def _thesis_reactions(text: str) -> Tuple[List[str], List[float]]:
        from preprocessing import preprocess_text  # type: ignore
        from extractor import find_reaction_spans  # type: ignore

        preprocessed = preprocess_text(text)
        spans = find_reaction_spans(preprocessed)

        if not spans:
            raise ValueError("No spans found, falling through")

        texts = [s.text for s in spans]
        confs = [s.confidence for s in spans]
        return texts, confs

    # ── Onset matching ──────────────────────────────────────────────────
    @staticmethod
    def _match_onsets(text: str) -> Tuple[List[str], List[float]]:
        # Try thesis model first
        try:
            from preprocessing import preprocess_text  # type: ignore
            from extractor import find_onset_spans  # type: ignore

            preprocessed = preprocess_text(text)
            spans = find_onset_spans(preprocessed)
            if spans:
                return [s.text for s in spans], [s.confidence for s in spans]
        except Exception:
            pass

        # Keyword fallback
        text_lower = text.lower()
        found: List[str] = []
        confs: List[float] = []
        for pat, conf in _ONSET_PATTERNS:
            m = re.search(pat, text_lower)
            if m:
                found.append(m.group(0))
                confs.append(conf)
        return found, confs

    # ── Confidence computation ──────────────────────────────────────────
    @staticmethod
    def _compute_confidence(
        drug_confs: List[float],
        reaction_confs: List[float],
        onset_confs: List[float],
        has_drugs: bool,
        has_reactions: bool,
        has_onsets: bool,
    ) -> float:
        """
        Compute granular confidence from individual match scores.
        Mirrors the thesis model's aggregate_graph_confidence logic
        but tuned for the web app's three extraction channels.
        """

        if not has_drugs and not has_reactions:
            return 0.10  # Nothing found

        # Average confidence per channel
        avg_drug = sum(drug_confs) / len(drug_confs) if drug_confs else 0.0
        avg_rxn = sum(reaction_confs) / len(reaction_confs) if reaction_confs else 0.0
        avg_onset = sum(onset_confs) / len(onset_confs) if onset_confs else 0.0

        # Weighted combination: drug + reaction are most important
        if has_drugs and has_reactions:
            # Full extraction — weight drug and reaction heavily
            base = 0.45 * avg_drug + 0.40 * avg_rxn
            if has_onsets:
                base += 0.15 * avg_onset
            else:
                # Slight penalty for missing onset
                base *= 0.92
        elif has_drugs and not has_reactions:
            # Drug found but no reaction — less confident
            base = 0.35 * avg_drug
            if has_onsets:
                base += 0.10 * avg_onset
        elif has_reactions and not has_drugs:
            # Reaction found but no drug — less confident
            base = 0.30 * avg_rxn
            if has_onsets:
                base += 0.10 * avg_onset
        else:
            base = 0.10

        # Clamp to [0.05, 0.98]
        return max(0.05, min(0.98, base))
