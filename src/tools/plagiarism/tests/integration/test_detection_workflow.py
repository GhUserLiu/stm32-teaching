"""
查重检测集成测试
"""

import pytest
from tools.plagiarism.core import PlagiarismDetector, SimilarityMethod


class TestDetectionWorkflow:
    """检测工作流集成测试"""
    
    def test_basic_detection(self, sample_submission):
        """测试基础检测流程"""
        detector = PlagiarismDetector(
            method=SimilarityMethod.HYBRID,
            threshold=60.0
        )

        submissions = {
            '001': sample_submission,
            '002': {
                **sample_submission,
                'student_id': '002',
                'name': '李四'
            }
        }

        # detect 返回 (results_by_student, suspicious_results, threshold_report)
        results_by_student, suspicious_results, _ = detector.detect(submissions)
        assert results_by_student is not None
        assert suspicious_results is not None

    def test_cross_group_detection(self, sample_submission):
        """测试跨组检测"""
        detector = PlagiarismDetector(
            method=SimilarityMethod.HYBRID,
            threshold=60.0,
            group_info={'001': 'A', '002': 'B'}
        )

        submissions = {
            '001': sample_submission,
            '002': {**sample_submission, 'student_id': '002'}
        }

        # detect 返回 (results_by_student, suspicious_results, threshold_report)
        results_by_student, suspicious_results, _ = detector.detect(submissions)

        # 验证跨组标记 - 检查所有学生的结果
        for student_id, results in results_by_student.items():
            for result in results:
                if result.similar_to in detector.group_info:
                    if detector.group_info.get(result.student_id) != detector.group_info.get(result.similar_to):
                        assert result.is_cross_group == True
