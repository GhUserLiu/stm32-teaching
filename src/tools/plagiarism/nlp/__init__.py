# -*- coding: utf-8 -*-
"""
增强NLP模块
Enhanced NLP Module

提供高级NLP功能来优化查重和评分系统
"""

from .enhanced_matcher import EnhancedKeywordMatcher, FuzzyMatcher, MatchMethod
from .template_filter import AdvancedTemplateFilter, FilterMethod
from .code_analyzer_nlp import CodeASTAnalyzer
from .nlp_integration import (
    NLPEngine, NLPEngineConfig, create_nlp_enhanced_detector, get_preset
)

__all__ = [
    'EnhancedKeywordMatcher',
    'FuzzyMatcher',
    'MatchMethod',
    'AdvancedTemplateFilter',
    'FilterMethod',
    'CodeASTAnalyzer',
    'NLPEngine',
    'NLPEngineConfig',
    'create_nlp_enhanced_detector',
    'get_preset'
]
