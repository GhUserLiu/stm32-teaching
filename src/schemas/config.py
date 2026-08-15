#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unified configuration schemas and loader (pydantic v2).

Single typed configuration entry for the P1 refactor. Absorbs the three
overlapping legacy sources --

  * src/tools/auto_grading/config.py      (AutoGradingConfig dataclass defaults)
  * src/tools/plagiarism/utils/config.py  (PlagiarismConfig dataclass defaults)
  * data/config/teaching/config.yaml      (GUI-side advisory yaml, partially dead)

-- into one file (config/base.yaml) validated at load time.

Load chain (later wins):
    config/base.yaml  <-  config/<env>.yaml  <-  APP_* environment variables

Env var convention: ``APP_<SECTION>__<FIELD>`` (double underscore = nesting)::

    APP_TEACHING__SEMESTER=2026-秋季
    APP_GRADING__TOOLCHAIN__KEIL_ENABLED=true

Every model uses ``extra="forbid"``: a typo'd key fails fast instead of being
silently ignored -- the exact failure mode that left the legacy config files
dead (see data/config/plagiarism/default_config.json, zero callers).
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

# repo-root/config  (src/schemas/config.py -> parents[2] = repo root)
CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"

ENV_PREFIX = "APP_"
ENV_SEP = "__"


class _Strict(BaseModel):
    """Base model: unknown keys are rejected, never silently ignored."""

    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------- models


class SimilarityWeights(_Strict):
    """Blend weights for the four similarity dimensions (must sum to 1)."""

    text: float = Field(0.5, ge=0, le=1)
    code: float = Field(0.3, ge=0, le=1)
    structure: float = Field(0.1, ge=0, le=1)
    semantic: float = Field(0.1, ge=0, le=1)

    @model_validator(mode="after")
    def _sums_to_one(self) -> "SimilarityWeights":
        total = self.text + self.code + self.structure + self.semantic
        if not 0.99 <= total <= 1.01:
            raise ValueError(
                "plagiarism.weights must sum to 1.0, got %.3f" % total)
        return self


class ThresholdSettings(_Strict):
    """Similarity thresholds on the 0-100 scale."""

    suspicious: float = Field(60, ge=0, le=100)
    high_similarity: float = Field(70, ge=0, le=100)
    plagiarism: float = Field(85, ge=0, le=100)
    paraphrase_min: float = Field(50, ge=0, le=100)
    paraphrase_max: float = Field(85, ge=0, le=100)
    code_similar: float = Field(85, ge=0, le=100)
    paragraph_similar: float = Field(80, ge=0, le=100)

    @model_validator(mode="after")
    def _ordered(self) -> "ThresholdSettings":
        if not (self.suspicious <= self.high_similarity <= self.plagiarism):
            raise ValueError(
                "require suspicious <= high_similarity <= plagiarism "
                "(got %s <= %s <= %s)" % (self.suspicious,
                                          self.high_similarity,
                                          self.plagiarism))
        if self.paraphrase_min >= self.paraphrase_max:
            raise ValueError("require paraphrase_min < paraphrase_max")
        return self


class FeatureSettings(_Strict):
    """Feature toggles for the plagiarism pipeline."""

    enable_template_filter: bool = True
    enable_semantic_detection: bool = True
    semantic_method: str = Field("auto", pattern="^(auto|tfidf|embedding)$")
    prefer_embedding: bool = False
    enable_jieba: bool = True
    enable_code_obfuscation: bool = True
    enable_ai_detection: bool = False
    ai_detection_threshold: float = Field(0.7, ge=0, le=1)
    enable_image_similarity: bool = True


class PlagiarismSettings(_Strict):
    weights: SimilarityWeights = SimilarityWeights()
    thresholds: ThresholdSettings = ThresholdSettings()
    features: FeatureSettings = FeatureSettings()


class ClassInfo(_Strict):
    """One teaching class (班级)."""

    code: str
    students_file: Optional[str] = None
    submission_dir: str = "submissions/"
    group_file: Optional[str] = None


class ExperimentInfo(_Strict):
    """One practice task / experiment (实验)."""

    name: str
    code: str
    rubric_path: str
    template_path: Optional[str] = None
    due_date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    description: str = ""


class TeachingSettings(_Strict):
    """Semester / classes / experiments registry."""

    semester: str = Field(..., pattern=r"^\d{4}-.+$")  # e.g. 2026-春季
    classes: Dict[str, ClassInfo] = Field(default_factory=dict)
    experiments: Dict[str, ExperimentInfo] = Field(default_factory=dict)


class PathSettings(_Strict):
    """Root paths only; derived layout stays in tools/common/path_config.py."""

    teaching_dir: Path = Path("data/teaching")
    templates_dir: Path = Path("data/templates")
    rubrics_dir: Path = Path("data/rubrics")


class ToolchainSettings(_Strict):
    """Cross-compilation toolchain (make/arm-none-eabi-gcc, optional Keil)."""

    gcc_enabled: bool = True
    make_path: str = "make"
    arm_none_eabi_prefix: str = "arm-none-eabi-"
    keil_enabled: bool = False
    keil_uv4_path: Optional[str] = None  # e.g. r"C:\Keil_v5\UV4\UV4.exe"
    build_timeout: int = Field(60, ge=1, le=3600)


class ProjectSettings(_Strict):
    """STM32 project whitelist, mirrors the Makefile whitelist."""

    allowed_projects: List[str] = Field(default_factory=lambda: [
        "01-turn-signal", "07-car-gear", "_template", "Test6"])
    project_types: Dict[str, str] = Field(default_factory=lambda: {
        "01-turn-signal": "simple",
        "07-car-gear": "cubemx",
        "_template": "simple",
        "Test6": "simple",
    })


class SecuritySettings(_Strict):
    """Submission intake limits (aligned with tools/security/zip_validator)."""

    max_zip_size_mb: int = Field(100, ge=1)
    max_file_count: int = Field(1000, ge=1)
    allowed_extensions: List[str] = Field(default_factory=lambda: [
        ".c", ".h", ".cpp", ".hpp", ".zip",
        ".docx", ".doc", ".pdf", ".png", ".jpg"])
    allow_absolute_paths: bool = False
    allow_parent_references: bool = False


class GradeBand(_Strict):
    """One letter-grade band, e.g. A: 90-100."""

    label: str
    min: float = Field(ge=0, le=100)
    max: float = Field(ge=0, le=100)

    @model_validator(mode="after")
    def _min_le_max(self) -> "GradeBand":
        if self.min > self.max:
            raise ValueError("grade band requires min <= max")
        return self


class ScoringSettings(_Strict):
    enable_semantic_scoring: bool = True
    quality_weight: float = Field(0.2, ge=0, le=1)
    aggregation_method: str = Field(
        "weighted", pattern="^(weighted|max|min|average)$")
    scale: Dict[str, GradeBand] = Field(default_factory=dict)


class GradingSettings(_Strict):
    toolchain: ToolchainSettings = ToolchainSettings()
    project: ProjectSettings = ProjectSettings()
    security: SecuritySettings = SecuritySettings()
    scoring: ScoringSettings = ScoringSettings()


class OutputSettings(_Strict):
    default_format: str = Field("excel", pattern="^(excel|pdf|html)$")
    detailed_report: bool = True
    include_feedback: bool = True
    language: str = "zh-CN"


class WorkflowSettings(_Strict):
    enable_resume: bool = True
    state_file: str = ".workflow_state.json"
    enable_parallel: bool = True
    max_parallel_tasks: int = Field(4, ge=1, le=32)


class LoggingSettings(_Strict):
    level: str = Field("INFO", pattern="^(DEBUG|INFO|WARNING|ERROR)$")
    file: str = "teaching_manager.log"
    console: bool = True
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class AppSettings(_Strict):
    """Root settings object for the whole platform."""

    env: str = "base"
    teaching: TeachingSettings
    paths: PathSettings = PathSettings()
    plagiarism: PlagiarismSettings = PlagiarismSettings()
    grading: GradingSettings = GradingSettings()
    output: OutputSettings = OutputSettings()
    workflow: WorkflowSettings = WorkflowSettings()
    logging: LoggingSettings = LoggingSettings()

    # ---- convenience helpers (pure, no IO) ----

    def semester_dir(self, project_root: Path) -> Path:
        """data/teaching/<semester> for the configured project root."""
        return Path(project_root) / self.paths.teaching_dir / self.teaching.semester


# --------------------------------------------------------------------- loader


def _deep_merge(base: Dict, overlay: Dict) -> Dict:
    """Recursively merge ``overlay`` onto ``base`` (overlay wins)."""
    out = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _read_yaml(path: Path) -> Dict:
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("%s must contain a YAML mapping at top level" % path)
    return data


def _coerce(raw: str):
    """Convert an env-var string to bool/int/float when unambiguous."""
    try:
        return yaml.safe_load(raw)
    except yaml.YAMLError:
        return raw


def _apply_env_overrides(data: Dict) -> None:
    """Apply ``APP_<SECTION>__<FIELD>`` env vars onto the merged dict."""
    for key, raw in os.environ.items():
        if not key.startswith(ENV_PREFIX) or ENV_SEP not in key:
            continue
        parts = [p.lower() for p in key[len(ENV_PREFIX):].split(ENV_SEP) if p]
        if len(parts) < 2:
            continue
        node = data
        for part in parts[:-1]:
            if not isinstance(node.get(part), dict):
                node[part] = {}
            node = node[part]
        node[parts[-1]] = _coerce(raw)


def load_settings(env: Optional[str] = None,
                  config_dir: Optional[Path] = None) -> AppSettings:
    """Load and validate: base.yaml <- <env>.yaml <- APP_* env vars.

    Raises ``pydantic.ValidationError`` on unknown keys or violated
    constraints -- callers get a hard failure, never a silent default.
    """
    env = env or os.environ.get("APP_ENV", "base")
    config_dir = Path(config_dir) if config_dir else CONFIG_DIR

    # .env is loaded opportunistically when python-dotenv is installed
    try:
        from dotenv import load_dotenv
        load_dotenv(config_dir.parent / ".env")
    except ImportError:
        pass

    data = _read_yaml(config_dir / "base.yaml")
    overlay = _read_yaml(config_dir / ("%s.yaml" % env))
    if overlay:
        data = _deep_merge(data, overlay)
    _apply_env_overrides(data)
    data["env"] = env
    return AppSettings.model_validate(data)


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """Cached process-wide settings; call reload_settings() after changes."""
    return load_settings()


def reload_settings(env: Optional[str] = None) -> AppSettings:
    """Clear the cache and reload (optionally into a different env)."""
    get_settings.cache_clear()
    return load_settings(env) if env else get_settings()
