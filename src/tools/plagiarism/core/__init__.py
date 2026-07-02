"""
查重检测核心模块
Core Plagiarism Detection Module

提供文本/代码相似度检测的核心功能
"""

from .detector import (
    PlagiarismDetector,
    SimilarityResult,
    SimilarityMethod,
    TextPreprocessor
)

from .multi_class_detector import (
    MultiClassDetector,
    MultiClassDetectionResult,
    ClassDetectionResult,
    create_multi_class_config
)

__all__ = [
    # 基础检测
    'PlagiarismDetector',
    'SimilarityResult',
    'SimilarityMethod',
    'TextPreprocessor',
    # 多班级检测
    'MultiClassDetector',
    'MultiClassDetectionResult',
    'ClassDetectionResult',
    'create_multi_class_config',
]
