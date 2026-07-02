# -*- coding: utf-8 -*-
"""
语义相似度检测模块
Semantic Similarity Detection Module

用于检测改写后的抄袭，基于句子嵌入或TF-IDF
支持层次化检测和改写识别
"""

from .detector import (
    SemanticDetector,
    SemanticSimilarityResult,
    SemanticMethod
)

from .enhanced import (
    EnhancedSemanticDetector,
    ParaphraseType,
    ParaphraseMatch,
    StructureAnalysis
)

__all__ = [
    'SemanticDetector',
    'SemanticSimilarityResult',
    'SemanticMethod',
    'EnhancedSemanticDetector',
    'ParaphraseType',
    'ParaphraseMatch',
    'StructureAnalysis',
]
