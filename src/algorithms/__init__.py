# -*- coding: utf-8 -*-
"""Pluggable similarity engines (P3): base contract + factory.

Checkers live in ``code/`` and ``text/`` subpackages (next batch); names
intentionally mirror ``tools.plagiarism.core.detector.SimilarityMethod``
values so the future similarity_service can map
``SimilarityMethod.X.value`` straight onto a factory key.
"""

from .base import BaseSimilarityChecker, ContentKind
from .factory import SimilarityCheckerFactory, register_checker

__all__ = [
    "BaseSimilarityChecker",
    "ContentKind",
    "SimilarityCheckerFactory",
    "register_checker",
]
