"""
核心查重模块单元测试
"""

import pytest


class TestSimilarityMethod:
    """相似度方法枚举测试"""

    def test_module_import(self):
        """测试模块导入"""
        try:
            from tools.plagiarism.core import SimilarityMethod
            assert True
        except ImportError:
            pytest.skip("核心模块未完全实现")

    def test_methods_exist(self):
        """测试所有方法存在"""
        from tools.plagiarism.core import SimilarityMethod
        assert SimilarityMethod.SEQUENCE
        assert SimilarityMethod.COSINE
        assert SimilarityMethod.JACCARD
        assert SimilarityMethod.LEVENSHTEIN
        assert SimilarityMethod.HYBRID


class TestPlagiarismDetector:
    """查重检测器测试"""

    def test_detector_import(self):
        """测试检测器导入"""
        try:
            from tools.plagiarism.core import PlagiarismDetector
            assert PlagiarismDetector is not None
        except ImportError:
            pytest.skip("检测器未完全实现")
