# -*- coding: utf-8 -*-
"""
图片相似度检测模块
Image Similarity Detection Module

使用感知哈希检测图片相似度
"""

from .detector import ImageDetector, ImageSimilarityResult, HashType

__all__ = [
    'ImageDetector',
    'ImageSimilarityResult',
    'HashType',
]
