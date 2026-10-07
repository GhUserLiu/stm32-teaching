#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scan_project.py -- static architecture scanner for the STM32 teaching platform.

Traverses the repository with os.walk (pruned via EXCLUDE_DIRS), analyses every
first-party .py file with pathlib + ast, and prints:

  1. totals (files / lines / classes / functions)
  2. per-package distribution with a domain-keyword responsibility map
  3. largest modules (spaghetti-code candidates)
  4. domain keyword hits (task / grade / upload / compare / ...)
  5. persistence signals (ORM / sqlite imports)
  6. layering signals (gui / service / model / parser directory tokens)

Usage:
    conda run -n stm32_teaching python src/tools/scripts/scan_project.py
    conda run -n stm32_teaching python src/tools/scripts/scan_project.py --root <path> --json report.json
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ------------------------------------------------------------------ constants

# Directories that never contain first-party Python source.
EXCLUDE_DIRS = {
    ".git", ".claude", "__pycache__", ".venv", "venv", "node_modules",
    "build", "dist", "outputs", "models", ".idea", ".vscode",
    ".pytest_cache", ".mypy_cache", "htmlcov",
}

# Teaching-domain keywords used to map business responsibilities.
DOMAIN_KEYWORDS = (
    "task", "grade", "grading", "rubric", "upload", "submit", "submission",
    "compare", "similarity", "plagiar", "report", "score", "student",
    "teacher", "course", "keil", "hex", "preview", "export", "feedback",
)

# Imports that would indicate a real persistence layer exists.
ORM_MARKERS = (
    "sqlalchemy", "peewee", "django.db", "sqlite3", "sqlmodel",
    "pony.orm", "psycopg2", "pymysql",
)

# Directory-name tokens that hint at deliberate layering.
LAYER_HINTS = (
    "gui", "view", "views", "controller", "service", "services", "model",
    "models", "dao", "repository", "parser", "parsers", "schema", "schemas",
    "core", "util", "utils",
)

KEYWORD_SAMPLE_CAP = 5   # max samples printed per keyword
LARGEST_CAP = 12         # max rows in the largest-files table
PACKAGE_CAP = 18         # max rows in the package table

# -------------------------------------------------------------------- dataclass


@dataclass
class ModuleInfo:
    """Parsed summary of one first-party Python module."""

    rel: str                                   # repo-relative posix path
    lines: int = 0
    classes: List[Tuple[str, int]] = field(default_factory=list)
    functions: List[Tuple[str, int]] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    parse_error: bool = False

    @property
    def defs(self) -> List[Tuple[str, str, int]]:
        """All top-level definitions as (kind, name, lineno)."""
        return ([("class", n, ln) for n, ln in self.classes]
                + [("def", n, ln) for n, ln in self.functions])


# ----------------------------------------------------------------- traversal


def iter_py_files(root: Path):
    """Yield first-party .py files, pruning excluded directories in place."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in sorted(dirnames) if d not in EXCLUDE_DIRS]
        for fname in sorted(filenames):
            if fname.endswith(".py"):
                yield Path(dirpath) / fname


def parse_module(path: Path, root: Path) -> ModuleInfo:
    """Extract top-level classes / functions / imports via ast."""
    rel = path.relative_to(root).as_posix()
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ModuleInfo(rel=rel, parse_error=True)
    info = ModuleInfo(rel=rel, lines=source.count("\n") + 1)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        info.parse_error = True
        return info
    for node in tree.body:  # top-level only; class bodies stay opaque on purpose
        if isinstance(node, ast.ClassDef):
            info.classes.append((node.name, node.lineno))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            info.functions.append((node.name, node.lineno))
        elif isinstance(node, ast.Import):
            info.imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            info.imports.append(node.module)
    return info


# ---------------------------------------------------------------- aggregation


def package_of(rel: str) -> str:
    """Collapse a module path to at most 3 directory levels."""
    parts = rel.split("/")
    pkg_parts = parts[:-1]
    if len(pkg_parts) > 3:
        pkg_parts = pkg_parts[:3]
    return "/".join(pkg_parts) or "(root)"


def name_tokens(name: str) -> List[str]:
    """Split an identifier into lowercase alpha-numeric tokens."""
    return [t for t in re.split(r"[^a-z0-9]+", name.lower()) if t]


def build_keyword_hits(modules: List[ModuleInfo]) -> Dict[str, List[str]]:
    """Map each domain keyword to sampled 'path :: name' occurrences."""
    hits: Dict[str, List[str]] = {}
    for m in modules:
        stem = Path(m.rel).stem.lower()
        names = [stem] + [name.lower() for _, name, _ in m.defs]
        for kw in DOMAIN_KEYWORDS:
            for name in names:
                if kw in name:
                    hits.setdefault(kw, []).append(
                        "%s :: %s" % (m.rel, name))
                    break  # one sample per module per keyword is enough
    return hits


def build_package_table(modules: List[ModuleInfo]):
    """Aggregate per-package counts plus which domain keywords live there."""
    table: Dict[str, Dict[str, object]] = {}
    for m in modules:
        pkg = package_of(m.rel)
        row = table.setdefault(pkg, {
            "files": 0, "lines": 0, "classes": 0,
            "functions": 0, "keywords": set(),
        })
        row["files"] += 1
        row["lines"] += m.lines
        row["classes"] += len(m.classes)
        row["functions"] += len(m.functions)
        stem = Path(m.rel).stem.lower()
        for kw in DOMAIN_KEYWORDS:
            if (kw in stem
                    or any(kw in name.lower() for _, name, _ in m.defs)):
                row["keywords"].add(kw)
    rows = sorted(table.items(), key=lambda kv: -kv[1]["lines"])
    return rows


def build_layer_signals(modules: List[ModuleInfo]) -> Dict[str, List[str]]:
    """Find directory paths whose name tokens match layering hints."""
    signals: Dict[str, set] = {}
    for m in modules:
        parts = m.rel.split("/")
        for depth, part in enumerate(parts[:-1]):
            tokens = set(name_tokens(part))
            for hint in LAYER_HINTS:
                if hint in tokens:
                    signals.setdefault(hint, set()).add(
                        "/".join(parts[:depth + 1]))
    return {k: sorted(v)[:8] for k, v in sorted(signals.items())}


def build_orm_usage(modules: List[ModuleInfo]) -> List[str]:
    found = []
    for m in modules:
        for imp in m.imports:
            if any(marker in imp for marker in ORM_MARKERS):
                found.append("%s imports %s" % (m.rel, imp))
    return found


# ------------------------------------------------------------------- printing


def print_report(root: Path, modules: List[ModuleInfo]) -> None:
    total_lines = sum(m.lines for m in modules)
    n_classes = sum(len(m.classes) for m in modules)
    n_funcs = sum(len(m.functions) for m in modules)
    n_errors = sum(1 for m in modules if m.parse_error)

    print("=" * 78)
    print("STATIC ARCHITECTURE SCAN -- %s" % root)
    print("=" * 78)

    print("\n[1] TOTALS")
    print("    python files : %d" % len(modules))
    print("    total lines  : %d" % total_lines)
    print("    classes      : %d   (top-level)" % n_classes)
    print("    functions    : %d   (top-level)" % n_funcs)
    if modules:
        print("    avg file size: %.0f lines" % (total_lines / len(modules)))
    if n_errors:
        print("    parse errors : %d file(s) (counted, definitions skipped)"
              % n_errors)

    print("\n[2] PACKAGE DISTRIBUTION + RESPONSIBILITY KEYWORDS")
    print("    %-42s %5s %7s %6s %6s  %s"
          % ("package", "files", "lines", "class", "func", "keywords"))
    rows = build_package_table(modules)
    for pkg, row in rows[:PACKAGE_CAP]:
        kws = ",".join(sorted(row["keywords"])[:6]) or "-"
        print("    %-42s %5d %7d %6d %6d  %s"
              % (pkg, row["files"], row["lines"],
                 row["classes"], row["functions"], kws))
    if len(rows) > PACKAGE_CAP:
        print("    ... and %d more packages" % (len(rows) - PACKAGE_CAP))

    print("\n[3] LARGEST MODULES (spaghetti candidates)")
    for m in sorted(modules, key=lambda x: -x.lines)[:LARGEST_CAP]:
        flag = "  <-- REVIEW" if m.lines > 800 else ""
        print("    %6d lines  %s%s" % (m.lines, m.rel, flag))

    print("\n[4] DOMAIN KEYWORD HITS (sampled, max %d each)"
          % KEYWORD_SAMPLE_CAP)
    hits = build_keyword_hits(modules)
    for kw in DOMAIN_KEYWORDS:
        samples = hits.get(kw)
        if not samples:
            continue
        shown = samples[:KEYWORD_SAMPLE_CAP]
        more = len(samples) - len(shown)
        suffix = "  (+%d more)" % more if more > 0 else ""
        print("    %-11s [%3d] %s%s"
              % (kw, len(samples), "; ".join(shown), suffix))

    print("\n[5] PERSISTENCE SIGNALS (ORM / sqlite imports)")
    orm = build_orm_usage(modules)
    if orm:
        for line in orm:
            print("    %s" % line)
    else:
        print("    NONE -- no sqlalchemy/peewee/django/sqlite3 imports found")

    print("\n[6] LAYERING SIGNALS (directory-name tokens)")
    signals = build_layer_signals(modules)
    if signals:
        for hint, paths in signals.items():
            print("    %-12s %s" % (hint, ", ".join(paths)))
    else:
        print("    NONE -- no gui/service/model/parser style directories")

    print("\n" + "=" * 78)
    print("END OF SCAN")
    print("=" * 78)


# ----------------------------------------------------------------------- main


def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    default_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=default_root,
                        help="repository root (default: auto-detect)")
    parser.add_argument("--json", type=Path, default=None,
                        help="also write the raw result as JSON to this path")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    if not root.is_dir():
        print("error: root not found: %s" % root, file=sys.stderr)
        return 2

    modules = [parse_module(p, root) for p in iter_py_files(root)]
    print_report(root, modules)

    if args.json:
        payload = {
            "root": str(root),
            "totals": {
                "files": len(modules),
                "lines": sum(m.lines for m in modules),
                "classes": sum(len(m.classes) for m in modules),
                "functions": sum(len(m.functions) for m in modules),
                "parse_errors": sum(1 for m in modules if m.parse_error),
            },
            "packages": [
                {"package": pkg, **{k: (sorted(v) if isinstance(v, set) else v)
                                    for k, v in row.items()}}
                for pkg, row in build_package_table(modules)
            ],
            "largest_files": [
                {"path": m.rel, "lines": m.lines}
                for m in sorted(modules, key=lambda x: -x.lines)[:50]
            ],
            "keyword_hits": build_keyword_hits(modules),
            "orm_usage": build_orm_usage(modules),
            "layer_signals": build_layer_signals(modules),
        }
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8")
        print("\nJSON report written to %s" % args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
