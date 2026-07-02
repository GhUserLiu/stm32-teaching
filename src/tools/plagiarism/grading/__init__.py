"""
评分系统模块
Grading System Module

提供基于 Rubric 的评分功能
"""

# 单一、完整的延迟导入分发器（避免循环导入）。
# 历史 bug：曾存在两个 __getattr__，后者遮蔽前者，且均未导出
# CriterionScore / CategoryScore / KeywordMatcher / apply_plagiarism_penalty /
# PlagiarismThresholds 等，导致 enhanced_grading_system、nlp.enhanced_grading 导入即崩。
_GRAADING_NAMES = {
    'RubricLoader', 'RubricGrader', 'GradingResult', 'CriterionScore',
    'CategoryScore', 'KeywordMatcher', 'SectionDetector', 'batch_grade',
    'load_rubric_for_experiment', 'apply_plagiarism_penalty',
    'PlagiarismThresholds', 'batch_grade_with_plagiarism_check',
    '_calculate_grade_from_percentage', 'EnhancedRubricGrader',
}


def __getattr__(name):
    if name in _GRAADING_NAMES:
        from . import grading as _g
        return getattr(_g, name)
    if name in ('EnhancedGradingSystem', 'EnhancedGradingEngine'):
        from .enhanced_grading import EnhancedGradingEngine
        return EnhancedGradingEngine
    if name == 'GradingValidator':
        from .grading_validator import GradingValidator
        return GradingValidator
    if name == 'GradingSystem':  # 别名
        from .grading import RubricGrader
        return RubricGrader
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    'RubricLoader', 'RubricGrader', 'GradingResult', 'CriterionScore',
    'CategoryScore', 'KeywordMatcher', 'SectionDetector',
    'batch_grade', 'load_rubric_for_experiment',
    'apply_plagiarism_penalty', 'PlagiarismThresholds',
    'batch_grade_with_plagiarism_check', 'EnhancedRubricGrader',
    'EnhancedGradingSystem', 'EnhancedGradingEngine',
    'GradingValidator', 'GradingSystem',
]
