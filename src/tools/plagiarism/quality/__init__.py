"""
质量评估模块
Quality Assessment Module

提供实验报告质量评估功能
"""

import sys

# 导入时可能因为 NumPy 问题失败，添加错误处理
try:
    from .quality import (
        QualityDimension,
        QualityScore,
        AssessmentResult,
        TechnicalValidator,
        EnhancedQualityAssessor
    )
except (ImportError, RuntimeError) as e:
    print(f"[WARNING] Failed to import quality module: {e}", file=sys.stderr)
    # 定义空类以避免 AttributeError
    class QualityDimension: pass
    class QualityScore: pass
    class AssessmentResult: pass
    class TechnicalValidator: pass
    class EnhancedQualityAssessor: pass

try:
    from .adaptive_threshold import AdaptiveThresholdEngine
except (ImportError, RuntimeError) as e:
    print(f"[WARNING] Failed to import adaptive_threshold: {e}", file=sys.stderr)
    class AdaptiveThresholdEngine: pass

try:
    from .technical_checks import (
        TechnicalChecker,
        ExperimentType,
        CheckResult,
        ContentStructureChecker,
        CodeSnippetChecker,
        ThinkingQuestionsChecker
    )
except (ImportError, RuntimeError) as e:
    print(f"[WARNING] Failed to import technical_checks: {e}", file=sys.stderr)
    class TechnicalChecker: pass
    class ExperimentType: pass
    class CheckResult: pass
    class ContentStructureChecker: pass
    class CodeSnippetChecker: pass
    class ThinkingQuestionsChecker: pass

__all__ = [
    # 质量评估
    'QualityDimension',
    'QualityScore',
    'AssessmentResult',
    'TechnicalValidator',
    'EnhancedQualityAssessor',
    # 自适应阈值
    'AdaptiveThresholdEngine',
    # 技术检查
    'TechnicalChecker',
    'ExperimentType',
    'CheckResult',
    'ContentStructureChecker',
    'CodeSnippetChecker',
    'ThinkingQuestionsChecker',
]
