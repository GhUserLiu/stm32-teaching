"""
工具函数模块
Utility Functions Module

提供配置管理、模板处理等辅助功能
"""

from .config import PlagiarismConfig, SimilarityWeights, ThresholdConfig, FeatureConfig
from .template import TemplateFilter, TemplateExtractor, StructuredTemplateFilter

__all__ = [
    'PlagiarismConfig',
    'SimilarityWeights',
    'ThresholdConfig',
    'FeatureConfig',
    'TemplateFilter',
    'TemplateExtractor',
    'StructuredTemplateFilter',
]
