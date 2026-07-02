#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
功能面板模块
Functional Panels Module

包含各个功能模块的面板：
- GradingPanel: 自动评分面板
- PlagiarismPanel: 查重检测面板
- FeedbackPanel: 反馈生成面板
"""

from .grading_panel import GradingPanel
from .plagiarism_panel import PlagiarismPanel
from .feedback_panel import FeedbackPanel

__all__ = [
    'GradingPanel',
    'PlagiarismPanel',
    'FeedbackPanel'
]
