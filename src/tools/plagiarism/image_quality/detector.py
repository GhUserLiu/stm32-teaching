# -*- coding: utf-8 -*-
"""
图片质量评估器
Image Quality Assessor

主评估器，整合所有质量指标和验证功能
"""

import numpy as np
from PIL import Image
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .metrics import QualityMetrics
from .content_analyzer import ContentAnalyzer, ImageType
from .validators import LabReportValidator


@dataclass
class ImageQualityResult:
    """图片质量评估结果"""
    image_path: str                  # 图片路径
    technical_score: float            # 技术质量 0-100
    content_score: float              # 内容质量 0-100
    overall_quality: float            # 整体质量 0-100
    image_type: ImageType             # 图片类型
    issues: List[str] = field(default_factory=list)     # 问题列表
    suggestions: List[str] = field(default_factory=list) # 改进建议
    metrics: Dict = field(default_factory=dict)          # 详细指标


@dataclass
class BatchAssessmentResult:
    """批量评估结果"""
    results: List[ImageQualityResult]
    summary: Dict


class ImageQualityAssessor:
    """图片质量评估器"""

    # 质量权重配置
    QUALITY_WEIGHTS = {
        'sharpness': 0.30,        # 清晰度权重
        'brightness': 0.15,       # 亮度权重
        'contrast': 0.15,         # 对比度权重
        'resolution': 0.10,       # 分辨率权重
        'content_type': 0.15,     # 内容类型权重
        'validity': 0.15,         # 有效性权重
    }

    # 质量等级
    QUALITY_GRADES = {
        (90, 100): '优秀',
        (75, 89): '良好',
        (60, 74): '及格',
        (40, 59): '需改进',
        (0, 39): '不合格'
    }

    def __init__(self, strict_mode: bool = False):
        """
        初始化评估器

        Args:
            strict_mode: 是否使用严格模式（更高标准）
        """
        self.strict_mode = strict_mode
        self.metrics_calculator = QualityMetrics()
        self.content_analyzer = ContentAnalyzer()
        self.validator = LabReportValidator()

    def assess(
        self,
        image_path: str,
        expected_type: Optional[ImageType] = None,
        context: Optional[Dict] = None
    ) -> ImageQualityResult:
        """
        评估图片质量

        Args:
            image_path: 图片路径
            expected_type: 期望的图片类型（可选）
            context: 上下文信息（实验类型、要求等）

        Returns:
            图片质量评估结果
        """
        # 加载图片
        try:
            image = Image.open(image_path)
        except Exception as e:
            return ImageQualityResult(
                image_path=image_path,
                technical_score=0.0,
                content_score=0.0,
                overall_quality=0.0,
                image_type=ImageType.UNKNOWN,
                issues=[f"无法加载图片: {e}"],
                suggestions=["请检查图片文件是否损坏"],
                metrics={}
            )

        # 计算技术质量指标
        technical_metrics = self.metrics_calculator.calculate_all_metrics(image)

        # 分析内容类型
        content_type = self.content_analyzer.analyze_type(image)

        # 检测空白
        blank_result = self.content_analyzer.detect_blank(image)

        # 计算技术质量分数
        technical_score = self._calculate_technical_score(
            technical_metrics,
            blank_result
        )

        # 计算内容质量分数
        content_score = self._calculate_content_score(
            content_type,
            blank_result,
            expected_type
        )

        # 验证特定类型
        issues = []
        suggestions = []
        validation_result = None

        if expected_type:
            validation_result = self._validate_by_type(
                image,
                expected_type,
                content_type.image_type
            )
            issues.extend(validation_result.get('issues', []))
            suggestions.extend(validation_result.get('suggestions', []))

        # 根据检测结果添加问题和建议
        auto_issues = self._generate_auto_issues(
            technical_metrics,
            content_type,
            blank_result
        )
        issues.extend(auto_issues['issues'])
        suggestions.extend(auto_issues['suggestions'])

        # 计算整体质量
        overall_quality = (
            technical_score * 0.6 +
            content_score * 0.4
        )

        # 确定图片类型
        image_type = content_type.image_type

        # 结果只含度量数据、不再持有 image 对象，关闭以释放文件句柄（批量循环下避免 Windows 文件锁/句柄泄漏）
        image.close()

        return ImageQualityResult(
            image_path=image_path,
            technical_score=round(technical_score, 1),
            content_score=round(content_score, 1),
            overall_quality=round(overall_quality, 1),
            image_type=image_type,
            issues=list(set(issues)),  # 去重
            suggestions=list(set(suggestions)),  # 去重
            metrics={
                'technical': {
                    'sharpness': technical_metrics['sharpness'].score,
                    'brightness': technical_metrics['brightness'].score,
                    'contrast': technical_metrics['contrast'].score,
                    'resolution': technical_metrics['resolution'].score,
                    'noise': technical_metrics['noise'],
                },
                'content': {
                    'type': image_type.value,
                    'type_confidence': content_type.confidence,
                    'is_blank': blank_result.is_blank,
                    'blank_ratio': blank_result.blank_ratio,
                },
                'validation': validation_result or {}
            }
        )

    def batch_assess(
        self,
        image_paths: List[str],
        expected_type: Optional[ImageType] = None
    ) -> BatchAssessmentResult:
        """
        批量评估图片质量

        Args:
            image_paths: 图片路径列表
            expected_type: 期望的图片类型

        Returns:
            批量评估结果
        """
        results = []

        for image_path in image_paths:
            result = self.assess(image_path, expected_type)
            results.append(result)

        # 生成汇总
        summary = self._generate_summary(results)

        return BatchAssessmentResult(
            results=results,
            summary=summary
        )

    def assess_images_in_text(
        self,
        text: str,
        base_dir: Path,
        expected_type: Optional[ImageType] = None
    ) -> List[ImageQualityResult]:
        """
        评估文本中的图片

        Args:
            text: 文本内容
            base_dir: 基础目录
            expected_type: 期望的图片类型

        Returns:
            评估结果列表
        """
        # 从文本中提取图片路径
        import re
        image_patterns = [
            r'!\[.*?\]\(([^)]+)\)',           # Markdown
            r'<img[^>]+src=["\']([^"\']+)["\']',  # HTML
        ]

        image_paths = []
        for pattern in image_patterns:
            matches = re.findall(pattern, text)
            image_paths.extend(matches)

        # 转换为绝对路径
        abs_paths = []
        for path in image_paths:
            path_obj = Path(path)
            if not path_obj.is_absolute():
                path_obj = base_dir / path_obj
            if path_obj.exists():
                abs_paths.append(str(path_obj))

        # 批量评估
        return self.batch_assess(abs_paths, expected_type)

    def _calculate_technical_score(
        self,
        metrics: Dict,
        blank_result
    ) -> float:
        """计算技术质量分数"""
        if blank_result.is_blank:
            return 0.0

        weights = ImageQualityAssessor.QUALITY_WEIGHTS

        score = (
            metrics['sharpness'].score * weights['sharpness'] +
            metrics['brightness'].score * weights['brightness'] +
            metrics['contrast'].score * weights['contrast'] +
            metrics['resolution'].score * weights['resolution']
        ) / (weights['sharpness'] + weights['brightness'] +
             weights['contrast'] + weights['resolution'])

        return score

    def _calculate_content_score(
        self,
        content_type,
        blank_result,
        expected_type: Optional[ImageType]
    ) -> float:
        """计算内容质量分数"""
        score = 50.0  # 基础分

        # 类型置信度加分
        score += content_type.confidence * 30

        # 类型匹配加分
        if expected_type and content_type.image_type == expected_type:
            score += 20
        elif expected_type:
            score -= 10

        # 空白检测扣分
        if blank_result.is_blank:
            score = 0.0
        elif blank_result.blank_ratio > 0.7:
            score -= 20

        return max(0, min(100, score))

    def _validate_by_type(
        self,
        image: Image.Image,
        expected_type: ImageType,
        actual_type: ImageType
    ) -> Dict:
        """根据类型进行验证"""
        result = {'issues': [], 'suggestions': []}

        if expected_type == ImageType.CIRCUIT:
            validation = self.validator.validate_circuit_diagram(image)
            if not validation.is_valid:
                result['issues'].extend(validation.issues)
            result['suggestions'].extend(validation.issues)

        elif expected_type == ImageType.PHOTO:
            validation = self.validator.validate_experiment_photo(image)
            if not validation.is_valid:
                result['issues'].extend(validation.issues)
            result['suggestions'].extend(validation.issues)

        elif expected_type == ImageType.CHART:
            validation = self.validator.validate_waveform_chart(image)
            if not validation.is_valid:
                result['issues'].extend(validation.issues)
            result['suggestions'].extend(validation.issues)

        return result

    def _generate_auto_issues(
        self,
        metrics: Dict,
        content_type,
        blank_result
    ) -> Dict:
        """自动生成问题和建议"""
        issues = []
        suggestions = []

        # 清晰度问题
        if metrics['sharpness'].score < 40:
            issues.append("图片清晰度不足")
            suggestions.append("建议使用更高分辨率的图片或重新拍摄")

        # 亮度问题
        if metrics['brightness'].is_too_dark:
            issues.append("图片过暗")
            suggestions.append("建议调整拍摄环境光照或使用图片编辑工具调整亮度")
        elif metrics['brightness'].is_too_bright:
            issues.append("图片过亮")
            suggestions.append("建议降低曝光或调整亮度")

        # 对比度问题
        if metrics['contrast'].score < 40:
            issues.append("图片对比度较低")
            suggestions.append("建议使用图片编辑工具提高对比度")

        # 分辨率问题
        if not metrics['resolution'].is_adequate:
            issues.append("图片分辨率不足")
            suggestions.append("建议使用更高分辨率的图片（至少640x480）")

        # 内容类型问题
        if content_type.image_type == ImageType.BLANK:
            issues.append("图片为空白或基本无内容")
            suggestions.append("请检查图片是否正确上传")

        elif content_type.image_type == ImageType.SCREENSHOT:
            issues.append("图片可能是截图而非实验照片")
            suggestions.append("建议使用实际拍摄的实验照片")

        return {'issues': issues, 'suggestions': suggestions}

    def _generate_summary(self, results: List[ImageQualityResult]) -> Dict:
        """生成汇总统计"""
        if not results:
            return {}

        total = len(results)
        avg_technical = sum(r.technical_score for r in results) / total
        avg_content = sum(r.content_score for r in results) / total
        avg_overall = sum(r.overall_quality for r in results) / total

        # 质量分布
        grade_distribution = {}
        for r in results:
            grade = self._get_quality_grade(r.overall_quality)
            grade_distribution[grade] = grade_distribution.get(grade, 0) + 1

        # 类型分布
        type_distribution = {}
        for r in results:
            it = r.image_type.value
            type_distribution[it] = type_distribution.get(it, 0) + 1

        # 问题统计
        issue_count = sum(len(r.issues) for r in results)

        return {
            'total_images': total,
            'average_technical_score': round(avg_technical, 1),
            'average_content_score': round(avg_content, 1),
            'average_overall_quality': round(avg_overall, 1),
            'grade_distribution': grade_distribution,
            'type_distribution': type_distribution,
            'total_issues': issue_count,
            'images_with_issues': sum(1 for r in results if r.issues)
        }

    def _get_quality_grade(self, score: float) -> str:
        """获取质量等级"""
        for (min_score, max_score), grade in sorted(
            ImageQualityAssessor.QUALITY_GRADES.items(),
            key=lambda x: x[0]
        ):
            if min_score <= score <= max_score:
                return grade
        return '未知'

    def compare_images(
        self,
        image_path1: str,
        image_path2: str
    ) -> Dict:
        """
        比较两张图片的质量

        Args:
            image_path1: 图片1路径
            image_path2: 图片2路径

        Returns:
            比较结果
        """
        result1 = self.assess(image_path1)
        result2 = self.assess(image_path2)

        return {
            'image1': {
                'quality': result1.overall_quality,
                'grade': self._get_quality_grade(result1.overall_quality)
            },
            'image2': {
                'quality': result2.overall_quality,
                'grade': self._get_quality_grade(result2.overall_quality)
            },
            'comparison': {
                'better': 1 if result1.overall_quality > result2.overall_quality else 2,
                'difference': abs(result1.overall_quality - result2.overall_quality)
            }
        }
