#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CODE-modality checkers: logic-level similarity for C / STM32 code.

Why a dedicated code engine (diagnosis items C / 查重引擎优化):
  * the legacy pipeline ran difflib on RAW code -- register/HAL init
    boilerplate dominates and inflates every pair's score, so thresholds
    cannot be tuned per modality;
  * comments and formatting differences mask real logic copying in the
    other direction.

Design (both engines are NEW -- no legacy parity constraint; behavior is
pinned by tests/unit/test_code_checkers.py):

``code_token``
    Comment-stripped, literal-masked C token stream compared via the
    legacy difflib engine (composable). Resistant to: comment changes,
    reformatting, string/number value tweaks (``500`` vs ``1000`` both
    tokenize to ``NUM``). NOT resistant to identifier renaming -- by
    design: HAL_/GPIO_ names carry signal for register-level copying.

``code_template``
    Same token similarity, but assignment-skeleton / HAL boilerplate is
    removed line-by-line FIRST (reusing
    tools.plagiarism.nlp.template_filter.AdvancedTemplateFilter -- single
    source of truth for that logic), so the score reflects student-written
    logic only. Template content arrives via the ``template_code`` engine
    option; the similarity_service will load it from experiment config.

Tokenizer notes (deliberate heuristics, documented):
  * preprocessor lines (``#include`` / ``#define`` ...) are dropped before
    tokenizing -- pure boilerplate for similarity purposes;
  * string literals -> ``STR``, char literals -> ``CHR``, numeric literals
    -> ``NUM`` (mask_strings=True default);
  * the scanner is string-aware: ``printf("// not a comment")`` keeps its
    string intact;
  * both checkers override ``preprocess`` (ContentKind.CODE contract -- the
    base whitespace-collapse would swallow code after ``//`` comments).
"""

from __future__ import annotations

import re
from typing import List

from algorithms.base import BaseSimilarityChecker, ContentKind
from algorithms.factory import register_checker
from tools.plagiarism.core.algorithms import sequence_similarity

# One master scanner: whitespace / comments / strings / chars / numbers /
# identifiers / multi-char operators / punctuation, longest-first where it
# matters. Block comments match without DOTALL via (?:[^*]|\*(?!/))*.
_TOKEN_SCANNER = re.compile(r'''
    (?P<ws>\s+)
  | (?P<comment>//[^\n]*|/\*(?:[^*]|\*(?!/))*\*/)
  | (?P<string>"(?:\\.|[^"\\\n])*")
  | (?P<char>'(?:\\.|[^'\\\n])')
  | (?P<number>0[xX][0-9a-fA-F]+[uUlL]*|(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?[fFuUlL]*)
  | (?P<ident>[A-Za-z_]\w*)
  | (?P<op><<=|>>=|->|\+\+|--|<<|>>|<=|>=|==|!=|&&|\|\||\+=|-=|\*=|/=|%=|&=|\^=|\|=)
  | (?P<punct>[{}\[\]();,.?:!~<>=+\-*/%&|^])
''', re.VERBOSE)


def strip_preprocessor(code: str) -> str:
    """Drop lines starting with '#' (after leading whitespace)."""
    return "\n".join(
        line for line in code.splitlines()
        if not line.lstrip().startswith("#"))


def tokenize_c(code: str, mask_strings: bool = True) -> List[str]:
    """Tokenize C source; comments/whitespace vanish, literals may mask."""
    code = strip_preprocessor(code)
    tokens: List[str] = []
    for match in _TOKEN_SCANNER.finditer(code):
        kind = match.lastgroup
        if kind in ("ws", "comment"):
            continue
        if kind == "string":
            tokens.append("STR" if mask_strings else match.group())
        elif kind == "char":
            tokens.append("CHR" if mask_strings else match.group())
        elif kind == "number":
            tokens.append("NUM" if mask_strings else match.group())
        else:
            tokens.append(match.group())
    return tokens


def normalized_token_string(code: str, mask_strings: bool = True) -> str:
    """Space-joined token stream -- the preprocess output of both checkers."""
    return " ".join(tokenize_c(code, mask_strings=mask_strings))


@register_checker
class CodeTokenChecker(BaseSimilarityChecker):
    """Logic-level C code similarity (comments/formatting/literal-proof)."""

    name = "code_token"
    kind = ContentKind.CODE
    description = "代码 token 相似度（去注释/预处理行，字面量屏蔽，difflib 序列比）"

    def __init__(self, mask_strings: bool = True, **options):
        super().__init__(**options)
        self._mask = mask_strings

    def preprocess(self, code: str) -> str:
        # CODE contract: must NOT use the whitespace-collapsing default
        # (it would swallow code after // line comments).
        return normalized_token_string(code, mask_strings=self._mask)

    def compare(self, left: str, right: str) -> float:
        return sequence_similarity(left, right)


@register_checker
class TemplateCodeChecker(BaseSimilarityChecker):
    """code_token + assignment-template/boilerplate removal first.

    Reuses AdvancedTemplateFilter (line-splitting, n-gram containment >=
    threshold) as the single source of template-filtering truth. The
    filter silently drops a trailing sentence without a separator, so a
    newline is appended before filtering to neutralize that quirk.
    """

    name = "code_template"
    kind = ContentKind.CODE
    description = "模板/HAL 样板先行剔除 + 代码 token 相似度（学生自写逻辑比对）"

    def __init__(self, template_code: str = "", strictness: float = 0.7,
                 mask_strings: bool = True, **options):
        super().__init__(**options)
        self._mask = mask_strings
        self._filter = None
        if template_code:
            # Lazy import: pulls the nlp package graph (jieba et al.) only
            # when a template is actually supplied.
            from tools.plagiarism.nlp.template_filter import (
                create_robust_template_filter)
            self._filter = create_robust_template_filter(
                template_code, strictness)

    def preprocess(self, code: str) -> str:
        if self._filter is not None:
            code = self._filter.filter(code + "\n").filtered_text
        return normalized_token_string(code, mask_strings=self._mask)

    def compare(self, left: str, right: str) -> float:
        return sequence_similarity(left, right)
