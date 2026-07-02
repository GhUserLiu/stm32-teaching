#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
自动化批阅系统
Auto Grading System for STM32 Teaching Projects

提供统一的自动化批阅功能，包括：
- 编译检查
- 代码质量分析
- 报告评分
- 综合反馈生成

主要组件：
- BuildChecker: 编译检查器
- SubmissionProcessor: 提交处理器
- AutoGradingEngine: 整合评分引擎
- AutoGradingFacade: 统一入口
"""

from .config import AutoGradingConfig
from .submission_organizer import SubmissionOrganizer, OrganizationResult, StudentInfo
from .submission_normalizer import SubmissionNormalizer, NormalizeResult
from .source_state import SourceState, SourceStateClassifier
from .build_checker import BuildChecker, BuildResult, BuildStatus
from .submission_processor import SubmissionProcessor, ProcessedSubmission, ProjectInfo
from .grading_engine import AutoGradingEngine, GradingResult, CategoryScore
from .facade import AutoGradingFacade

__all__ = [
    # 配置
    "AutoGradingConfig",
    # 提交整理
    "SubmissionOrganizer",
    "OrganizationResult",
    "StudentInfo",
    # 提交规整（消除多余包装层目录嵌套）
    "SubmissionNormalizer",
    "NormalizeResult",
    # 源码工程状态分类（格式问题的具体原因/改进方法）
    "SourceState",
    "SourceStateClassifier",
    # 编译检查
    "BuildChecker",
    "BuildResult",
    "BuildStatus",
    # 提交处理
    "SubmissionProcessor",
    "ProcessedSubmission",
    "ProjectInfo",
    # 评分引擎
    "AutoGradingEngine",
    "GradingResult",
    "CategoryScore",
    # 统一入口
    "AutoGradingFacade",
]

__version__ = "2.4.0"
__author__ = "STM32F407 Teaching Team"

# 注意：__all__ 仅在上面定义一次。此前此处存在重复定义（覆盖了上面的完整版本，
# 导致 SubmissionOrganizer/OrganizationResult/StudentInfo/CategoryScore 等无法导出），已删除。
