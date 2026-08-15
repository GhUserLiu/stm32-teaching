#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Split-engine similarity orchestration (P3 finale).

Replaces the legacy single-blended-pipeline arrangement for NEW callers:
report prose and source code go through DIFFERENT factory engines with
DIFFERENT thresholds, instead of being concatenated into one string and
blended 0.6/0.4 (the arrangement the 2026-08 diagnosis flagged).

Key properties:
  * modality split -- TEXT uses the text engine (default 'tfidf', corpus
    IDF via prepare()), CODE uses the code engine (default 'code_template',
    assignment boilerplate removed first when template_code is supplied);
  * thresholds come from the unified settings (config/base.yaml ->
    schemas.get_settings()); nothing is hardcoded here. Code bands sit
    higher than text bands: register-level/HAL init code is legitimately
    similar across students, so the code suspicious line uses
    high_similarity (70) and the confirmed line uses code_similar (85),
    while text uses suspicious/high_similarity/plagiarism (60/70/85);
  * verdicts are PER MODALITY (never blended): overall_similarity is
    max(text, code) purely for display sorting/compatibility;
  * output is legacy-compatible: detect() returns the same 3-tuple shape
    as PlagiarismDetector.detect (all_results dict of SimilarityResult
    lists, suspicious list, report dict), so GUI payload building, tables
    and exports work unchanged;
  * the legacy PlagiarismDetector.detect path is untouched (behavior
    equivalence for existing users; this service is opt-in).
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Sequence, Tuple

import algorithms.code  # noqa: F401  (registration side effect)
import algorithms.text  # noqa: F401  (registration side effect)
from algorithms.factory import SimilarityCheckerFactory
from schemas import get_settings
from tools.plagiarism.core.detector import (
    SimilarityMethod,
    SimilarityResult,
)


def verdict_for(score: float, bands: Sequence[Tuple[str, float]]):
    """Highest band whose bound the score meets, else None.

    ``bands`` is ordered high-severity first, e.g.
    [("plagiarism", 85), ("high", 70), ("suspicious", 60)].
    """
    for label, bound in bands:
        if score >= bound:
            return label
    return None


class SimilarityService:
    """Orchestrates TEXT and CODE engines separately over one corpus."""

    def __init__(
        self,
        settings=None,
        text_engine: str = "tfidf",
        code_engine: str = "code_template",
        engine_options: Optional[Dict[str, Dict]] = None,
    ):
        """
        Args:
            settings: AppSettings (default: get_settings())
            text_engine / code_engine: factory registry names
            engine_options: per-engine kwargs, e.g.
                {"code": {"template_code": "<assignment skeleton>"}}
        """
        self._settings = settings or get_settings()
        self._text_engine = text_engine
        self._code_engine = code_engine
        self._engine_options = engine_options or {}

    # ------------------------------------------------------------ bands

    @property
    def text_bands(self) -> List[Tuple[str, float]]:
        t = self._settings.plagiarism.thresholds
        return [("plagiarism", t.plagiarism),
                ("high", t.high_similarity),
                ("suspicious", t.suspicious)]

    @property
    def code_bands(self) -> List[Tuple[str, float]]:
        # Register/HAL-init code is legitimately similar across students:
        # the code suspicious line is raised to high_similarity.
        t = self._settings.plagiarism.thresholds
        return [("plagiarism", t.code_similar),
                ("suspicious", t.high_similarity)]

    # ------------------------------------------------------------ detect

    def detect(
        self,
        submissions: Dict[str, Dict],
        log: Optional[Callable[[str], None]] = None,
    ) -> Tuple[Dict[str, List[SimilarityResult]], List[SimilarityResult], Dict]:
        """Pairwise split-engine detection over one merged corpus.

        Args:
            submissions: student_id -> {"name", "text" (report prose),
                "code" (source text, optional), "class" (optional, ignored)}
            log: optional progress callback

        Returns:
            (all_results, suspicious, mode_report) -- same shapes as
            PlagiarismDetector.detect so downstream consumers are unchanged.
        """
        log = log or (lambda _msg: None)
        ids = [sid for sid in submissions
               if (submissions[sid].get("text") or "").strip()
               or (submissions[sid].get("code") or "").strip()]
        all_results: Dict[str, List[SimilarityResult]] = {sid: [] for sid in ids}
        suspicious: List[SimilarityResult] = []
        if len(ids) < 2:
            return all_results, suspicious, self._mode_report(0, 0)

        texts = [(submissions[sid].get("text") or "") for sid in ids]
        codes = [(submissions[sid].get("code") or "") for sid in ids]

        text_checker = SimilarityCheckerFactory.create(
            self._text_engine, **self._engine_options.get("text", {}))
        code_checker = SimilarityCheckerFactory.create(
            self._code_engine, **self._engine_options.get("code", {}))

        log("分引擎比对：%s(text) + %s(code)，语料 %d 份"
            % (self._text_engine, self._code_engine, len(ids)))

        non_empty_texts = [t for t in texts if t.strip()]
        if non_empty_texts:
            text_checker.prepare(non_empty_texts)
        non_empty_codes = [c for c in codes if c.strip()]
        if non_empty_codes:
            code_checker.prepare(non_empty_codes)

        text_matrix = text_checker.compare_matrix(texts)
        code_matrix = code_checker.compare_matrix(codes)

        t_bands = self.text_bands
        c_bands = self.code_bands
        flagged = 0
        total_pairs = 0
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                total_pairs += 1
                text_sim = text_matrix[i][j]
                code_sim = code_matrix[i][j]
                text_verdict = verdict_for(text_sim, t_bands)
                code_verdict = verdict_for(code_sim, c_bands)
                is_suspicious = bool(text_verdict or code_verdict)
                if is_suspicious:
                    flagged += 1
                result = SimilarityResult(
                    student_id=ids[i],
                    similar_to=ids[j],
                    overall_similarity=max(text_sim, code_sim),
                    text_similarity=text_sim,
                    code_similarity=code_sim,
                    structure_similarity=0.0,   # not measured in this mode
                    method=SimilarityMethod.HYBRID,   # shape-only; see metadata
                    is_suspicious=is_suspicious,
                    metadata={
                        "mode": "split-engines",
                        "engines": {"text": self._text_engine,
                                    "code": self._code_engine},
                        "text_verdict": text_verdict,
                        "code_verdict": code_verdict,
                    },
                )
                all_results[ids[i]].append(result)
                all_results[ids[j]].append(result)
                if is_suspicious:
                    suspicious.append(result)

        log("分引擎完成：%d 对，命中 %d（阈值 text %s / code %s）"
            % (total_pairs, flagged,
               "/".join(str(b) for _, b in t_bands),
               "/".join(str(b) for _, b in c_bands)))
        return all_results, suspicious, self._mode_report(total_pairs, flagged)

    def _mode_report(self, total_pairs: int, flagged: int) -> Dict:
        t = self._settings.plagiarism.thresholds
        return {
            "mode": "split-engines",
            "engines": {"text": self._text_engine,
                        "code": self._code_engine},
            "thresholds": {
                "text": {"suspicious": t.suspicious,
                         "high": t.high_similarity,
                         "plagiarism": t.plagiarism},
                "code": {"suspicious": t.high_similarity,
                         "plagiarism": t.code_similar},
            },
            "pairs_total": total_pairs,
            "flagged": flagged,
        }
