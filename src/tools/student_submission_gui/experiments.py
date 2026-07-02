#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
实验清单（学生端）

从教师端 path_helper 导入，保持单一数据源：
- load_experiments()  读 data/config/teaching/config.yaml，回退内置清单
- experiment_choices() [(id, name), ...] 供下拉框
- match_experiment(text) 从文件名/文本自动匹配实验 id

教师端 path_helper 仅依赖 tools.common.path_config（无 PyQt），导入安全。
"""

from tools.teaching_management_gui.path_helper import (  # noqa: F401
    load_experiments,
    experiment_choices,
    match_experiment,
)

__all__ = ["load_experiments", "experiment_choices", "match_experiment"]
