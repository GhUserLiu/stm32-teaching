#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Common module for STM32F407 teaching tools

提供共享的工具类、配置和路径管理
"""

from .path_config import (
    ExperimentPaths,
    TeachingPaths,
    get_teaching_paths,
    get_experiment_paths,
    get_results_dir,
    get_reports_dir,
    get_feedback_dir,
    DIRECTORY_STRUCTURE
)

from .file_io import (
    atomic_write_json,
    atomic_write_text,
)

__all__ = [
    'ExperimentPaths',
    'TeachingPaths',
    'get_teaching_paths',
    'get_experiment_paths',
    'get_results_dir',
    'get_reports_dir',
    'get_feedback_dir',
    'DIRECTORY_STRUCTURE',
    'atomic_write_json',
    'atomic_write_text',
]
