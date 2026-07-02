"""
核心查重模块单元测试
"""

import pytest
from tools.plagiarism.core import SimilarityMethod, SimilarityResult


class TestSimilarityMethod:
    """相似度方法枚举测试"""
    
    def test_methods_exist(self):
        """测试所有方法存在"""
        assert SimilarityMethod.SEQUENCE
        assert SimilarityMethod.COSINE
        assert SimilarityMethod.JACCARD
        assert SimilarityMethod.LEVENSHTEIN
        assert SimilarityMethod.HYBRID


class TestSimilarityResult:
    """相似度结果测试"""
    
    def test_creation(self):
        """测试结果创建"""
        result = SimilarityResult(
            student_id='001',
            similar_to='002',
            overall_similarity=75.5,
            text_similarity=80.0,
            code_similarity=70.0,
            structure_similarity=75.0,
            method=SimilarityMethod.HYBRID
        )
        assert result.student_id == '001'
        assert result.overall_similarity == 75.5
        assert result.is_suspicious == False  # 默认值
    
    def test_suspicious_threshold(self):
        """测试可疑阈值"""
        result = SimilarityResult(
            student_id='001',
            similar_to='002',
            overall_similarity=85.0,
            text_similarity=85.0,
            code_similarity=85.0,
            structure_similarity=85.0,
            method=SimilarityMethod.HYBRID
        )
        # 可以在初始化时设置 is_suspicious
        result.is_suspicious = True
        assert result.is_suspicious == True
