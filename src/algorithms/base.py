#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BaseSimilarityChecker -- the pluggable similarity-engine contract (P3).

Why this exists (2026-08 architecture diagnosis):
  * code similarity and report-text similarity flow through ONE blended
    pipeline (0.6/0.4 weights), so engines cannot be tuned per modality --
    register-level / HAL-init code needs different thresholds than prose;
  * four half-wired assets exist (ngram_similarity, ImageDetector phash,
    EnhancedSemanticDetector, and the CODE_OBFUSCATION / SEMANTIC_HYBRID
    enum values that have no dispatch branch at all);
  * similarity thresholds/weights are hardcoded in three separate places.

Contract rules (implementations MUST follow):
  1. Score scale is ALWAYS 0-100 float -- the project convention, matching
     every existing algorithm in tools/plagiarism/core/algorithms.py and the
     threshold config (60/70/85). Base-provided paths clamp AND map NaN to
     0.0; engines should not rely on that safety net.
  2. Modality is explicit: every checker declares a ContentKind. The
     (future) similarity_service asks the factory for TEXT engines and CODE
     engines separately -- this is the "code logic vs report prose" split.
     IMAGE is its own world (see ContentKind) and is never served for
     TEXT/CODE lookups.
  3. Empty/blank input yields 0.0 and never raises. ENFORCED CENTRALLY by
     score()/compare_pairs()/compare_matrix() after preprocessing (mirrors
     the legacy guard in compute_similarity); compare() itself only ever
     sees non-empty prepared text.
  4. Batch is first-class: the historical bug was O(pairs) re-tokenization
     in per-pair cosine (full-class runs hung 30+ min until cosine_matrix
     vectorized it). Every base-provided batch path preprocesses each
     document exactly once; tokenizing/vectorized engines override
     compare_matrix() wholesale.
  5. Checkers are stateless between calls; heavy resources (embedding
     models) load lazily -- NEVER in __init__, because create_for_kind()
     constructs every matching engine and must stay cheap. Per-corpus
     state (IDF tables) belongs in ``prepare()``, driven by the orchestrator
     with the whole corpus up front. NOTE: after prepare(corpus), scores
     become corpus-relative (TF-IDF needs IDF); without prepare, engines
     must still return valid 0-100 scores (legacy fallback behavior).
  6. Thresholds and penalty policies do NOT live here -- they belong to the
     similarity_service / config layer. A checker only measures.

Known extension point (documented, deliberately NOT implemented yet):
  rich detail results -- matched segments, paraphrase flags, structure
  analysis (SemanticDetector/EnhancedSemanticDetector return objects, not
  floats). If the similarity_service ends up needing them, add an optional
  ``compare_detail()`` hook returning a dict; the scalar contract above
  stays the primary interface.

Adapters for the existing implementations (difflib sequence, TF-IDF, ...)
land in ``code/`` and ``text/`` subpackages and register via the factory.
"""

from __future__ import annotations

import abc
import math
import re
from enum import Enum
from typing import ClassVar, Dict, List, Optional, Sequence, Tuple


class ContentKind(Enum):
    """Which modality a checker serves.

    IMAGE exists so image-pair detectors (perceptual hash) have a home
    without polluting TEXT/CODE lookups; they do not fit compare(str, str)
    and will get their own comparison entry points in a later batch.
    """

    TEXT = "text"   # report prose
    CODE = "code"   # C source / user logic sections
    IMAGE = "image"  # docx-embedded figures (phash) -- exact-match lookups only
    ANY = "any"     # modality-agnostic (legacy string algorithms)


def clamp_score(value: float) -> float:
    """Clamp to the canonical [0, 100] score scale; NaN maps to 0.0.

    Public on purpose: compare_matrix overriders must reuse it (a bare
    ``min/max`` clamp lets NaN through as a perfect score).
    """
    value = float(value)
    if math.isnan(value):
        return 0.0
    return max(0.0, min(100.0, value))


def collapse_whitespace(text: str) -> str:
    """Default normalization: remove all whitespace.

    Mirrors ``compute_similarity`` in tools/plagiarism/core/algorithms.py
    (``re.sub(r'\\s+', '', ...)``) so legacy adapters keep byte-identical
    behavior through the default ``preprocess``.

    HAZARD for ContentKind.CODE: removing newlines swallows everything
    after a ``//`` line comment into one comment (``int x; // a\\ny = 2;``
    loses ``y = 2``). CODE engines MUST override ``preprocess``; the
    factory emits a registration warning when they do not.
    """
    return re.sub(r"\s+", "", text)


class BaseSimilarityChecker(abc.ABC):
    """Abstract base for every similarity engine.

    Subclasses set the ``name`` / ``kind`` / ``description`` class attrs and
    implement ``compare``. They register themselves via
    ``@register_checker`` (see factory.py); names should mirror
    ``SimilarityMethod`` enum values where a legacy method is being adapted
    ('sequence', 'cosine', ...) so enum-to-factory mapping stays trivial.
    """

    #: Registry key. Unique, lowercase, non-empty; set by subclasses.
    name: ClassVar[str] = ""
    #: Modality this checker serves.
    kind: ClassVar[ContentKind] = ContentKind.ANY
    #: One-line human description (shown in GUI lists / logs).
    description: ClassVar[str] = ""

    def __init__(self, **options):
        """Uniform construction: free-form engine options via kwargs.

        The factory passes user options through; engines read what they
        know and ignore the rest (unknown options are stored, not rejected
        -- unlike the config layer, engine options are not a typo surface
        the user edits by hand).
        """
        self.options = dict(options)

    # ------------------------------------------------------------- core API

    @abc.abstractmethod
    def compare(self, left: str, right: str) -> float:
        """Similarity of two PRE-PROCESSED, non-empty documents, 0-100.

        Called by ``score``/batch paths after ``preprocess``; raw user
        input never reaches this method. Contract: scale 0-100, never
        raises on ordinary input (base paths clamp and map NaN to 0.0).
        """

    def preprocess(self, text: str) -> str:
        """Normalize one document before comparison.

        Default: collapse all whitespace (legacy behavior; see the hazard
        note on collapse_whitespace -- CODE engines override this, and the
        factory warns at registration time when they forget).
        Called exactly once per document per batch on every base-provided
        path -- never per pair.
        """
        return collapse_whitespace(text)

    def _score_prepared(self, left: str, right: str) -> float:
        """Score two already-preprocessed docs: central empty guard + clamp."""
        if not left or not right:
            return 0.0
        return clamp_score(self.compare(left, right))

    def compare_detail(self, left: str, right: str) -> Optional[dict]:
        """Optional rich-result hook (details beyond the scalar score).

        Default None (scalar-only engines). Engines with rich outputs --
        matched segments, paraphrase flags, structure analysis -- return a
        dict. Convention: key 'score' mirrors score() on the 0-100 scale;
        everything else is engine-specific evidence consumed by the
        similarity_service. Implementations must mirror score()'s
        semantics: preprocess each side once, empty input -> {'score': 0.0},
        never raise.

        Added up front (adopted 2026-08) so the semantic/enhanced adapters
        can carry their rich objects without breaking the scalar contract.
        """
        return None

    def score(self, left: str, right: str) -> float:
        """Public pairwise entry: preprocess both sides once, then score.

        Empty/whitespace-only input returns 0.0 (central legacy guarantee).
        """
        return self._score_prepared(self.preprocess(left), self.preprocess(right))

    # ------------------------------------------------------------- batch API

    def prepare(self, corpus: Sequence[str]) -> None:
        """Optional per-corpus setup (IDF tables, embedding caches).

        The orchestrator calls this once with the FULL corpus before any
        compare/matrix call. Default: no-op. See contract rule 5 for the
        corpus-relative scoring note.
        """

    def compare_pairs(self, pairs: Sequence[Tuple[str, str]]) -> List[float]:
        """Scores aligned with ``pairs``, preprocessing each distinct
        document exactly once (memoized), never per pair.

        Note: bypasses ``score()`` to share preprocessing; engines that
        override ``score()`` semantics should override this too.
        """
        cache: Dict[str, str] = {}

        def _prepared(text: str) -> str:
            if text not in cache:
                cache[text] = self.preprocess(text)
            return cache[text]

        return [
            self._score_prepared(_prepared(left), _prepared(right))
            for left, right in pairs
        ]

    def compare_matrix(self, texts: Sequence[str]) -> List[List[float]]:
        """Full n x n score matrix.

        Default: preprocess each document ONCE (the historical perf bug was
        re-tokenizing per pair), O(n^2) compare calls, symmetric, diagonal
        100.0 -- or 0.0 for a document that preprocesses to empty (an
        empty doc cannot be similar even to itself, matching rule 3).
        Vectorized engines (TF-IDF cosine_matrix et al.) override this
        wholesale and must keep the same guarantees: symmetric, scale
        clamped via ``clamp_score`` (NaN -> 0.0), and the diagonal SET
        explicitly like the default does (float rounding can make a
        self-cosine 99.999...; do not compute it).
        """
        n = len(texts)
        prepared = [self.preprocess(t) for t in texts]
        matrix: List[List[float]] = [[0.0] * n for _ in range(n)]
        for i in range(n):
            matrix[i][i] = 100.0 if prepared[i] else 0.0
            for j in range(i + 1, n):
                value = self._score_prepared(prepared[i], prepared[j])
                matrix[i][j] = value
                matrix[j][i] = value
        return matrix

    # ------------------------------------------------------------- reporting

    def __repr__(self) -> str:  # pragma: no cover - debugging nicety
        return "<%s name=%r kind=%s>" % (
            type(self).__name__, self.name, self.kind.value)
