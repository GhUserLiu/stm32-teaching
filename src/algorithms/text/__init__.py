# -*- coding: utf-8 -*-
"""Text / legacy-string similarity adapters.

Importing this package registers every adapter (import-time registration,
process-global -- see algorithms.factory).
"""

from .legacy_string_checkers import (  # noqa: F401
    CosineChecker,
    HybridChecker,
    JaccardChecker,
    LevenshteinChecker,
    NgramChecker,
    SequenceChecker,
)
from .tfidf_checker import TfidfChecker  # noqa: F401

__all__ = [
    "SequenceChecker",
    "CosineChecker",
    "JaccardChecker",
    "LevenshteinChecker",
    "HybridChecker",
    "NgramChecker",
    "TfidfChecker",
]
