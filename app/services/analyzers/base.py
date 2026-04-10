"""Abstract base class for all analysis providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class AnalysisResult:
    """Normalised output from any analysis provider."""

    drug_mention: str = ""
    reaction_mention: str = ""
    onset: str = ""
    raw_confidence: float = 0.0

    def is_empty(self) -> bool:
        return not self.drug_mention and not self.reaction_mention


class BaseAnalyzer(ABC):
    """Every provider must implement `analyze`."""

    @abstractmethod
    async def analyze(self, text: str) -> Optional[AnalysisResult]:
        """Analyse raw ADR text and return structured result, or None on failure."""
        ...
