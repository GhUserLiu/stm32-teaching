"""
代码分析模块
Code Analysis Module

提供代码质量分析和相似度检测
"""

from .code_analyzer import CodeAnalyzer
from .code_quality_analyzer import CodeQualityAnalyzer
from .simplified_code_checker import SimplifiedCodeChecker

__all__ = [
    'CodeAnalyzer',
    'CodeQualityAnalyzer',
    'SimplifiedCodeChecker',
]
