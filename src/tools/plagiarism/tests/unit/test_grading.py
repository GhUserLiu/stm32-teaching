"""
评分系统单元测试
"""

import pytest
from tools.plagiarism.grading import GradingSystem


class TestGradingSystem:
    """评分系统测试"""
    
    def test_init(self, sample_rubric):
        """测试初始化"""
        system = GradingSystem(rubric=sample_rubric)
        assert system is not None
    
    def test_grade_submission(self, sample_rubric, sample_submission):
        """测试评分"""
        system = GradingSystem(rubric=sample_rubric)
        result = system.grade(
            student_id=sample_submission['student_id'],
            name=sample_submission['name'],
            text=sample_submission['content']
        )
        assert result is not None
        assert hasattr(result, 'total_score') or 'total_score' in result


class TestRubricValidation:
    """评分标准验证测试"""
    
    def test_valid_rubric(self, sample_rubric):
        """测试有效评分标准"""
        assert 'criteria' in sample_rubric
        assert len(sample_rubric['criteria']) > 0
        assert all('id' in c and 'name' in c and 'max_points' in c 
                   for c in sample_rubric['criteria'])
    
    def test_rubric_points_total(self, sample_rubric):
        """测试总分计算"""
        total = sum(c['max_points'] for c in sample_rubric['criteria'])
        assert total == 100  # 假设总分100
