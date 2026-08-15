#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SimilarityCheckerFactory -- registry + construction for similarity engines.

Design goals (P3):
  * swap engines without touching call sites (factory pattern) -- including
    future external engines (jplag/moss adapters) that simply register
    under their own name;
  * fail fast on registration mistakes: duplicate names, missing ``name``,
    abstract classes -- silent registration bugs are how the legacy code
    ended up with enum values that dispatch to nothing;
  * modality-aware lookup: ``create_for_kind(ContentKind.CODE)`` returns
    the engines declared for that modality.

Nothing registers here yet by design -- the concrete adapters (difflib
sequence, TF-IDF, AST, ...) form the next batch and live in
``src/algorithms/code/`` and ``src/algorithms/text/``, each ending with::

    @register_checker
    class SequenceChecker(BaseSimilarityChecker):
        name = "sequence"     # mirrors SimilarityMethod.SEQUENCE.value
        ...

Registration happens at import time and is PROCESS-GLOBAL for the session:
the registry is a class-level dict shared by everything (GUI QThreads only
read it; sorted() snapshots make iteration safe). Tests must register with
``replace=True`` and unregister in teardown to stay isolated.
"""

from __future__ import annotations

import inspect
import warnings
from typing import Callable, Dict, List, Optional, Type

from .base import BaseSimilarityChecker, ContentKind


class SimilarityCheckerFactory:
    """Class-level registry of checker classes (no instances needed)."""

    _registry: Dict[str, Type[BaseSimilarityChecker]] = {}

    # ------------------------------------------------------------ register

    @classmethod
    def register(
        cls,
        checker_cls: Type[BaseSimilarityChecker],
        name: Optional[str] = None,
        *,
        replace: bool = False,
    ) -> Type[BaseSimilarityChecker]:
        """Register a checker class; usable directly as ``@register_checker``.

        Args:
            checker_cls: concrete BaseSimilarityChecker subclass
            name: override key (default: the class's ``name`` attribute)
            replace: allow overwriting an existing registration (tests)

        Returns:
            The class, unchanged -- so the decorator form keeps the name
            binding intact.
        """
        if not (inspect.isclass(checker_cls)
                and issubclass(checker_cls, BaseSimilarityChecker)):
            raise TypeError(
                "checker must be a BaseSimilarityChecker subclass, got %r"
                % (checker_cls,))
        if inspect.isabstract(checker_cls):
            raise TypeError(
                "cannot register abstract checker %r -- implement compare()"
                % checker_cls.__name__)

        key = (name or checker_cls.name or "").strip().lower()
        if not key:
            raise ValueError(
                "checker %s must set a non-empty `name` (or pass name=)"
                % checker_cls.__name__)
        if key in cls._registry and not replace:
            raise ValueError(
                "checker name %r already registered (%s); pass replace=True "
                "to override" % (key, cls._registry[key].__name__))
        # Explicit isinstance: enum `in` semantics for plain values differ
        # across Python versions (value-membership), so don't rely on them.
        if not isinstance(checker_cls.kind, ContentKind):
            raise ValueError(
                "checker %s has invalid kind %r" % (
                    checker_cls.__name__, checker_cls.kind))
        # CODE checkers without a preprocess override would run the default
        # whitespace collapse -- which swallows code after // line comments
        # (see base.collapse_whitespace). Warn loudly, do not reject.
        if (checker_cls.kind is ContentKind.CODE
                and checker_cls.preprocess is BaseSimilarityChecker.preprocess):
            warnings.warn(
                "checker %s is ContentKind.CODE but does not override "
                "preprocess(); the default strips newlines and swallows "
                "code after // comments" % checker_cls.__name__,
                UserWarning, stacklevel=2)

        cls._registry[key] = checker_cls
        return checker_cls

    @classmethod
    def unregister(cls, name: str) -> None:
        """Remove a registration (test isolation / plugin teardown)."""
        cls._registry.pop(name.strip().lower(), None)

    # ------------------------------------------------------------- create

    @classmethod
    def create(cls, name: str, **options) -> BaseSimilarityChecker:
        """Instantiate the registered checker ``name`` with engine options."""
        key = (name or "").strip().lower()
        if key not in cls._registry:
            raise KeyError(
                "unknown similarity checker %r; available: %s"
                % (name, ", ".join(sorted(cls._registry)) or "(none)"))
        return cls._registry[key](**options)

    @classmethod
    def create_for_kind(
        cls, kind: ContentKind, **options
    ) -> List[BaseSimilarityChecker]:
        """All engines usable for ``kind`` (its own kind + ANY).

        IMAGE is excluded from TEXT/CODE (and vice versa): image-pair
        detectors do not fit the compare(str, str) contract.
        """
        return [
            checker_cls(**options)
            for key, checker_cls in sorted(cls._registry.items())
            if cls._matches(checker_cls, kind)
        ]

    # -------------------------------------------------------------- query

    @classmethod
    def _matches(
        cls, checker_cls: Type[BaseSimilarityChecker], kind: ContentKind
    ) -> bool:
        """Modality matching rule: own kind or ANY -- except IMAGE.

        IMAGE on either side requires an exact match, so an image detector
        never leaks into TEXT/CODE engine lists and ANY engines are not
        offered for IMAGE work.
        """
        if (checker_cls.kind is ContentKind.IMAGE
                or kind is ContentKind.IMAGE):
            return checker_cls.kind is kind
        return checker_cls.kind is kind or checker_cls.kind is ContentKind.ANY

    @classmethod
    def names(cls, kind: Optional[ContentKind] = None) -> List[str]:
        """Registered names, optionally filtered by modality (incl. ANY)."""
        keys = sorted(cls._registry)
        if kind is None:
            return keys
        return [
            key for key in keys
            if cls._matches(cls._registry[key], kind)
        ]

    @classmethod
    def is_registered(cls, name: str) -> bool:
        return (name or "").strip().lower() in cls._registry

    @classmethod
    def clear(cls) -> None:
        """Drop all registrations (test isolation only)."""
        cls._registry.clear()


#: Decorator form: ``@register_checker`` on a checker class.
register_checker: Callable[
    [Type[BaseSimilarityChecker]], Type[BaseSimilarityChecker]
] = SimilarityCheckerFactory.register
